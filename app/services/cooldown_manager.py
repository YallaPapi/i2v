"""Cooldown management for failure tracking and backoff.

Principle 8: Cooldown and Rate Limiting
Track failures per entity. Increase backoff with consecutive failures.
Hammering a failing endpoint wastes resources and can get you blocked.

Cooldown Schedule:
    failures=1: 60 seconds (1 minute)
    failures=2: 300 seconds (5 minutes)
    failures=3: 900 seconds (15 minutes)
    failures=4: 3600 seconds (1 hour)
    failures=5+: 86400 seconds (1 day)

Usage:
    cooldown = CooldownManager()

    # Check if entity can be processed
    if cooldown.should_process(entity_id):
        try:
            result = process(entity)
            cooldown.record_success(entity_id)
        except Exception as e:
            cooldown.record_failure(entity_id)
            raise

    # Get all entities past their cooldown
    eligible = cooldown.get_eligible(entity_ids)

    # Get cooldown status for an entity
    status = cooldown.get_status(entity_id)
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from threading import Lock
import structlog

logger = structlog.get_logger()


@dataclass
class CooldownState:
    """State for a single entity's cooldown tracking."""

    entity_id: str
    consecutive_failures: int = 0
    last_failure_at: Optional[str] = None
    last_success_at: Optional[str] = None
    cooldown_until: Optional[str] = None
    total_failures: int = 0
    total_successes: int = 0
    last_error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CooldownState":
        """Create from dictionary."""
        return cls(**data)

    def is_in_cooldown(self) -> bool:
        """Check if entity is currently in cooldown."""
        if not self.cooldown_until:
            return False

        try:
            cooldown_dt = datetime.fromisoformat(
                self.cooldown_until.replace("Z", "+00:00")
            )
            return datetime.now(timezone.utc) < cooldown_dt
        except Exception:
            return False

    def get_remaining_cooldown_seconds(self) -> float:
        """Get remaining cooldown time in seconds."""
        if not self.cooldown_until:
            return 0.0

        try:
            cooldown_dt = datetime.fromisoformat(
                self.cooldown_until.replace("Z", "+00:00")
            )
            remaining = (cooldown_dt - datetime.now(timezone.utc)).total_seconds()
            return max(0.0, remaining)
        except Exception:
            return 0.0


class CooldownManager:
    """
    Manages cooldown periods for entities after failures.

    Tracks consecutive failures per entity and applies increasing
    cooldown periods to prevent hammering failing endpoints.

    Attributes:
        COOLDOWN_SCHEDULE: List of cooldown durations in seconds
        persist_path: Optional path for persistence
    """

    # Cooldown schedule in seconds: 1m, 5m, 15m, 1h, 1d
    COOLDOWN_SCHEDULE = [60, 300, 900, 3600, 86400]

    # Max consecutive failures before permanent cooldown
    MAX_CONSECUTIVE_FAILURES = 10

    def __init__(
        self,
        name: str = "default",
        persist_dir: Optional[str] = None,
        auto_persist: bool = True,
    ):
        """
        Initialize cooldown manager.

        Args:
            name: Name for this cooldown manager (for persistence)
            persist_dir: Directory for persistence files
            auto_persist: Whether to auto-save state changes
        """
        self.name = name
        self.auto_persist = auto_persist
        self._states: Dict[str, CooldownState] = {}
        self._lock = Lock()

        # Set up persistence
        if persist_dir:
            self.persist_dir = Path(persist_dir)
        else:
            self.persist_dir = Path.cwd() / ".cooldowns"

        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.persist_path = self.persist_dir / f"{name}_cooldowns.json"

        # Load existing state
        self._load_state()

    def _load_state(self):
        """Load state from persistence file."""
        if not self.persist_path.exists():
            return

        try:
            with open(self.persist_path, "r") as f:
                data = json.load(f)

            for entity_id, state_data in data.items():
                self._states[entity_id] = CooldownState.from_dict(state_data)

            logger.debug(
                "Loaded cooldown state",
                name=self.name,
                count=len(self._states),
            )
        except Exception as e:
            logger.warning("Failed to load cooldown state", error=str(e))

    def _save_state(self):
        """Save state to persistence file."""
        if not self.auto_persist:
            return

        try:
            data = {
                entity_id: state.to_dict() for entity_id, state in self._states.items()
            }
            with open(self.persist_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save cooldown state", error=str(e))

    def _get_cooldown_duration(self, consecutive_failures: int) -> int:
        """Get cooldown duration based on failure count."""
        if consecutive_failures <= 0:
            return 0

        index = min(consecutive_failures - 1, len(self.COOLDOWN_SCHEDULE) - 1)
        return self.COOLDOWN_SCHEDULE[index]

    def _get_or_create_state(self, entity_id: str) -> CooldownState:
        """Get existing state or create new one."""
        if entity_id not in self._states:
            self._states[entity_id] = CooldownState(entity_id=entity_id)
        return self._states[entity_id]

    def should_process(self, entity_id: str) -> bool:
        """
        Check if an entity should be processed (not in cooldown).

        Args:
            entity_id: The entity identifier

        Returns:
            True if entity can be processed, False if in cooldown
        """
        with self._lock:
            state = self._states.get(entity_id)

            if state is None:
                return True

            is_cooling = state.is_in_cooldown()

            if is_cooling:
                remaining = state.get_remaining_cooldown_seconds()
                logger.debug(
                    "Entity in cooldown",
                    entity_id=entity_id,
                    remaining_seconds=round(remaining, 1),
                    consecutive_failures=state.consecutive_failures,
                )

            return not is_cooling

    def record_failure(
        self,
        entity_id: str,
        error: Optional[str] = None,
    ) -> CooldownState:
        """
        Record a failure for an entity and set cooldown.

        Args:
            entity_id: The entity identifier
            error: Optional error message to record

        Returns:
            Updated cooldown state
        """
        with self._lock:
            state = self._get_or_create_state(entity_id)

            # Increment failure counts
            state.consecutive_failures += 1
            state.total_failures += 1
            state.last_failure_at = datetime.now(timezone.utc).isoformat()

            if error:
                state.last_error = error[:500]  # Truncate long errors

            # Calculate and set cooldown
            cooldown_seconds = self._get_cooldown_duration(state.consecutive_failures)
            cooldown_until = datetime.now(timezone.utc) + timedelta(
                seconds=cooldown_seconds
            )
            state.cooldown_until = cooldown_until.isoformat()

            logger.info(
                "Failure recorded, cooldown set",
                entity_id=entity_id,
                consecutive_failures=state.consecutive_failures,
                cooldown_seconds=cooldown_seconds,
                cooldown_until=state.cooldown_until,
            )

            self._save_state()
            return state

    def record_success(self, entity_id: str) -> CooldownState:
        """
        Record a success for an entity and reset cooldown.

        Args:
            entity_id: The entity identifier

        Returns:
            Updated cooldown state
        """
        with self._lock:
            state = self._get_or_create_state(entity_id)

            # Reset consecutive failures but keep total
            previous_failures = state.consecutive_failures
            state.consecutive_failures = 0
            state.total_successes += 1
            state.last_success_at = datetime.now(timezone.utc).isoformat()
            state.cooldown_until = None
            state.last_error = None

            if previous_failures > 0:
                logger.info(
                    "Success recorded, cooldown cleared",
                    entity_id=entity_id,
                    previous_consecutive_failures=previous_failures,
                    total_successes=state.total_successes,
                )
            else:
                logger.debug(
                    "Success recorded",
                    entity_id=entity_id,
                    total_successes=state.total_successes,
                )

            self._save_state()
            return state

    def get_status(self, entity_id: str) -> Optional[CooldownState]:
        """
        Get the cooldown status for an entity.

        Args:
            entity_id: The entity identifier

        Returns:
            CooldownState or None if entity has no tracking
        """
        with self._lock:
            return self._states.get(entity_id)

    def get_eligible(self, entity_ids: List[str]) -> List[str]:
        """
        Filter a list of entity IDs to only those past their cooldown.

        Args:
            entity_ids: List of entity IDs to check

        Returns:
            List of entity IDs that can be processed
        """
        eligible = []

        with self._lock:
            for entity_id in entity_ids:
                state = self._states.get(entity_id)

                if state is None or not state.is_in_cooldown():
                    eligible.append(entity_id)

        logger.debug(
            "Filtered eligible entities",
            total=len(entity_ids),
            eligible=len(eligible),
            in_cooldown=len(entity_ids) - len(eligible),
        )

        return eligible

    def get_next_eligible_time(self, entity_id: str) -> Optional[datetime]:
        """
        Get when an entity will be eligible for processing.

        Args:
            entity_id: The entity identifier

        Returns:
            datetime when eligible, or None if already eligible
        """
        with self._lock:
            state = self._states.get(entity_id)

            if state is None or not state.is_in_cooldown():
                return None

            try:
                return datetime.fromisoformat(
                    state.cooldown_until.replace("Z", "+00:00")
                )
            except Exception:
                return None

    def clear_cooldown(self, entity_id: str) -> bool:
        """
        Manually clear cooldown for an entity.

        Args:
            entity_id: The entity identifier

        Returns:
            True if cooldown was cleared, False if not in cooldown
        """
        with self._lock:
            state = self._states.get(entity_id)

            if state is None:
                return False

            if not state.is_in_cooldown():
                return False

            state.cooldown_until = None
            state.consecutive_failures = 0

            logger.info("Cooldown manually cleared", entity_id=entity_id)
            self._save_state()
            return True

    def clear_all_cooldowns(self):
        """Clear all cooldowns. Use with caution."""
        with self._lock:
            for state in self._states.values():
                state.cooldown_until = None
                state.consecutive_failures = 0

            logger.warning("All cooldowns cleared", count=len(self._states))
            self._save_state()

    def get_all_in_cooldown(self) -> List[CooldownState]:
        """
        Get all entities currently in cooldown.

        Returns:
            List of CooldownState for entities in cooldown
        """
        with self._lock:
            return [state for state in self._states.values() if state.is_in_cooldown()]

    def get_stats(self) -> dict:
        """
        Get overall cooldown statistics.

        Returns:
            Dict with statistics
        """
        with self._lock:
            total = len(self._states)
            in_cooldown = sum(1 for s in self._states.values() if s.is_in_cooldown())
            total_failures = sum(s.total_failures for s in self._states.values())
            total_successes = sum(s.total_successes for s in self._states.values())

            return {
                "total_entities": total,
                "in_cooldown": in_cooldown,
                "available": total - in_cooldown,
                "total_failures": total_failures,
                "total_successes": total_successes,
                "success_rate": (
                    total_successes / (total_failures + total_successes)
                    if (total_failures + total_successes) > 0
                    else 1.0
                ),
            }

    def prune_old_entries(self, max_age_days: int = 30):
        """
        Remove entries that haven't been updated recently.

        Args:
            max_age_days: Maximum age in days for entries
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        cutoff_str = cutoff.isoformat()

        with self._lock:
            to_remove = []

            for entity_id, state in self._states.items():
                # Check last activity time
                last_activity = state.last_success_at or state.last_failure_at

                if last_activity and last_activity < cutoff_str:
                    to_remove.append(entity_id)

            for entity_id in to_remove:
                del self._states[entity_id]

            if to_remove:
                logger.info(
                    "Pruned old cooldown entries",
                    removed=len(to_remove),
                    remaining=len(self._states),
                )
                self._save_state()


# Singleton instances for common use cases
job_cooldown = CooldownManager("jobs")
model_cooldown = CooldownManager("models")
api_cooldown = CooldownManager("api")


class ModelCooldownManager(CooldownManager):
    """Specialized cooldown manager for AI models.

    Tracks failures per model to back off from failing models
    while continuing to use working ones.
    """

    def __init__(self):
        super().__init__(name="models")

    def should_use_model(self, model: str) -> bool:
        """Check if a model should be used based on cooldown."""
        return self.should_process(model)

    def model_failed(self, model: str, error: Optional[str] = None):
        """Record a model failure."""
        return self.record_failure(model, error)

    def model_succeeded(self, model: str):
        """Record a model success."""
        return self.record_success(model)

    def get_available_models(self, models: List[str]) -> List[str]:
        """Get models that are not in cooldown."""
        return self.get_eligible(models)


class JobCooldownManager(CooldownManager):
    """Specialized cooldown manager for job processing.

    Tracks failures per job to avoid repeatedly processing
    jobs that consistently fail.
    """

    def __init__(self):
        super().__init__(name="jobs")

    def should_process_job(self, job_id: str) -> bool:
        """Check if a job should be processed based on cooldown."""
        return self.should_process(str(job_id))

    def job_failed(self, job_id: str, error: Optional[str] = None):
        """Record a job processing failure."""
        return self.record_failure(str(job_id), error)

    def job_succeeded(self, job_id: str):
        """Record a job processing success."""
        return self.record_success(str(job_id))

    def get_processable_jobs(self, job_ids: List[str]) -> List[str]:
        """Get jobs that are not in cooldown."""
        return self.get_eligible([str(jid) for jid in job_ids])
