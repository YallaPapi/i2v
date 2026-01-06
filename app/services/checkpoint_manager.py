"""Write-ahead logging checkpoint system for crash recovery.

Principle 3: State Persistence
Every state change is written to disk before proceeding.
If it's not persisted, it didn't happen.

Pattern: Write-Ahead Logging
1. Write checkpoint before starting operation
2. Execute operation
3. Write checkpoint after completing operation
4. On startup, find incomplete checkpoints and resume

Usage:
    checkpoint = CheckpointManager("jobs")

    # Before starting work
    checkpoint.write(job_id, status="started")

    # Do work
    result = execute(job)

    # After completion
    checkpoint.write(job_id, status="completed", result=result)

    # On startup - recover interrupted jobs
    for entry in checkpoint.read_incomplete():
        if entry.status == "started":
            requeue(entry.job_id)
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Iterator
from dataclasses import dataclass, field, asdict
from threading import Lock
import structlog

try:
    import orjson

    ORJSON_AVAILABLE = True
except ImportError:
    ORJSON_AVAILABLE = False

try:
    from atomicwrites import atomic_write

    ATOMICWRITES_AVAILABLE = True
except ImportError:
    ATOMICWRITES_AVAILABLE = False

from app.services.file_lock import FileLock

logger = structlog.get_logger()


@dataclass
class CheckpointEntry:
    """A single checkpoint entry."""

    id: str
    status: str
    timestamp: str
    step: int = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CheckpointEntry":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            status=data["status"],
            timestamp=data["timestamp"],
            step=data.get("step", 0),
            result=data.get("result"),
            error=data.get("error"),
            context=data.get("context", {}),
        )


class CheckpointManager:
    """
    Write-ahead logging checkpoint manager for crash recovery.

    Maintains a JSONL file of checkpoint entries that allows
    recovery of interrupted operations after a crash.

    Attributes:
        name: Name of this checkpoint set (e.g., "jobs", "pipelines")
        checkpoint_dir: Directory containing checkpoint files
    """

    DEFAULT_CHECKPOINT_DIR = ".checkpoints"

    def __init__(
        self,
        name: str,
        checkpoint_dir: Optional[str] = None,
        use_locking: bool = True,
    ):
        """
        Initialize checkpoint manager.

        Args:
            name: Name of the checkpoint set
            checkpoint_dir: Directory for checkpoint files
            use_locking: Whether to use file locking for writes
        """
        self.name = name
        self.use_locking = use_locking
        self._lock = Lock()  # Thread lock for in-process safety

        # Set up checkpoint directory
        if checkpoint_dir:
            self.checkpoint_dir = Path(checkpoint_dir)
        else:
            self.checkpoint_dir = Path.cwd() / self.DEFAULT_CHECKPOINT_DIR

        # Ensure directory exists
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Checkpoint file paths
        self.checkpoint_file = self.checkpoint_dir / f"{name}.jsonl"
        self.index_file = self.checkpoint_dir / f"{name}.index.json"

        # In-memory index of latest status per ID
        self._index: Dict[str, CheckpointEntry] = {}
        self._load_index()

    def _load_index(self):
        """Load or rebuild the index from checkpoint file."""
        # Try loading cached index first
        if self.index_file.exists():
            try:
                with open(self.index_file, "r") as f:
                    data = json.load(f)
                    for id, entry_data in data.items():
                        self._index[id] = CheckpointEntry.from_dict(entry_data)
                logger.debug(
                    "Loaded checkpoint index", name=self.name, count=len(self._index)
                )
                return
            except Exception as e:
                logger.warning("Failed to load index, rebuilding", error=str(e))

        # Rebuild index from checkpoint file
        self._rebuild_index()

    def _rebuild_index(self):
        """Rebuild index by scanning checkpoint file."""
        self._index.clear()

        if not self.checkpoint_file.exists():
            return

        try:
            with open(self.checkpoint_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entry = CheckpointEntry.from_dict(data)
                        self._index[entry.id] = entry
                    except Exception as e:
                        logger.warning("Skipping corrupt checkpoint line", error=str(e))

            # Save rebuilt index
            self._save_index()
            logger.info(
                "Rebuilt checkpoint index", name=self.name, count=len(self._index)
            )

        except Exception as e:
            logger.error("Failed to rebuild index", error=str(e))

    def _save_index(self):
        """Save index to file for fast loading."""
        try:
            data = {id: entry.to_dict() for id, entry in self._index.items()}
            with open(self.index_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning("Failed to save index", error=str(e))

    def _serialize(self, entry: CheckpointEntry) -> str:
        """Serialize entry to JSON string."""
        if ORJSON_AVAILABLE:
            return orjson.dumps(entry.to_dict()).decode("utf-8")
        return json.dumps(entry.to_dict())

    def write(
        self,
        id: str,
        status: str,
        step: int = 0,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        **context,
    ) -> CheckpointEntry:
        """
        Write a checkpoint entry.

        Args:
            id: Unique identifier (e.g., job_id)
            status: Current status (e.g., "started", "completed", "failed")
            step: Step number in multi-step operations
            result: Optional result data
            error: Optional error message
            **context: Additional context to store

        Returns:
            The written checkpoint entry
        """
        entry = CheckpointEntry(
            id=str(id),
            status=status,
            timestamp=datetime.now(timezone.utc).isoformat(),
            step=step,
            result=result,
            error=error,
            context=context,
        )

        line = self._serialize(entry) + "\n"

        with self._lock:
            try:
                # Use file locking for multi-process safety
                if self.use_locking:
                    with FileLock(f"checkpoint_{self.name}", timeout=10):
                        self._append_line(line)
                else:
                    self._append_line(line)

                # Update in-memory index
                self._index[entry.id] = entry

                logger.debug(
                    "Checkpoint written",
                    name=self.name,
                    id=id,
                    status=status,
                    step=step,
                )

            except Exception as e:
                logger.error("Failed to write checkpoint", id=id, error=str(e))
                raise

        return entry

    def _append_line(self, line: str):
        """Append a line to the checkpoint file."""
        if ATOMICWRITES_AVAILABLE and os.name != "nt":
            # Use atomic append on Unix
            with atomic_write(self.checkpoint_file, mode="a", overwrite=False) as f:
                f.write(line)
        else:
            # Standard append (still safe for single process)
            with open(self.checkpoint_file, "a") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())  # Ensure written to disk

    def read(self, id: str) -> Optional[CheckpointEntry]:
        """
        Read the latest checkpoint for an ID.

        Args:
            id: The ID to look up

        Returns:
            Latest checkpoint entry or None if not found
        """
        return self._index.get(str(id))

    def read_all(self) -> Dict[str, CheckpointEntry]:
        """
        Read all checkpoints (latest per ID).

        Returns:
            Dict mapping ID to latest checkpoint entry
        """
        return dict(self._index)

    def read_incomplete(self) -> List[CheckpointEntry]:
        """
        Find all incomplete checkpoints for recovery.

        Returns entries where status is "started" or "running",
        indicating the operation was interrupted.

        Returns:
            List of incomplete checkpoint entries
        """
        incomplete = []
        for entry in self._index.values():
            if entry.status in ("started", "running", "in_progress"):
                incomplete.append(entry)

        logger.info(
            "Found incomplete checkpoints",
            name=self.name,
            count=len(incomplete),
        )
        return incomplete

    def read_by_status(self, status: str) -> List[CheckpointEntry]:
        """
        Find all checkpoints with a specific status.

        Args:
            status: Status to filter by

        Returns:
            List of matching checkpoint entries
        """
        return [e for e in self._index.values() if e.status == status]

    def recover(self) -> List[str]:
        """
        Recover interrupted operations.

        Returns list of IDs that need to be reprocessed.

        Returns:
            List of IDs to requeue
        """
        incomplete = self.read_incomplete()
        ids_to_recover = []

        for entry in incomplete:
            # Mark as needing recovery
            self.write(
                id=entry.id,
                status="recovering",
                step=entry.step,
                context=entry.context,
                original_status=entry.status,
            )
            ids_to_recover.append(entry.id)

        logger.info(
            "Marked entries for recovery",
            name=self.name,
            count=len(ids_to_recover),
        )
        return ids_to_recover

    def mark_complete(
        self,
        id: str,
        result: Optional[Dict[str, Any]] = None,
        **context,
    ) -> CheckpointEntry:
        """
        Convenience method to mark an operation as complete.

        Args:
            id: Operation ID
            result: Optional result data
            **context: Additional context

        Returns:
            The checkpoint entry
        """
        current = self.read(id)
        step = current.step + 1 if current else 1

        return self.write(
            id=id,
            status="completed",
            step=step,
            result=result,
            **context,
        )

    def mark_failed(
        self,
        id: str,
        error: str,
        **context,
    ) -> CheckpointEntry:
        """
        Convenience method to mark an operation as failed.

        Args:
            id: Operation ID
            error: Error message
            **context: Additional context

        Returns:
            The checkpoint entry
        """
        current = self.read(id)
        step = current.step + 1 if current else 1

        return self.write(
            id=id,
            status="failed",
            step=step,
            error=error,
            **context,
        )

    def compact(self) -> int:
        """
        Compact checkpoint file by removing superseded entries.

        Keeps only the latest entry per ID.

        Returns:
            Number of entries removed
        """
        if not self.checkpoint_file.exists():
            return 0

        # Read all entries
        all_entries = []
        with open(self.checkpoint_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        all_entries.append(json.loads(line))
                    except Exception:
                        pass

        # Keep only latest per ID
        latest = {}
        for entry in all_entries:
            latest[entry["id"]] = entry

        removed = len(all_entries) - len(latest)

        if removed > 0:
            # Rewrite checkpoint file
            with FileLock(f"checkpoint_{self.name}", timeout=30):
                with open(self.checkpoint_file, "w") as f:
                    for entry in latest.values():
                        line = json.dumps(entry) + "\n"
                        f.write(line)

                # Update index
                self._rebuild_index()

            logger.info(
                "Compacted checkpoint file",
                name=self.name,
                removed=removed,
                remaining=len(latest),
            )

        return removed

    def clear(self):
        """Clear all checkpoints. Use with caution."""
        with self._lock:
            if self.checkpoint_file.exists():
                self.checkpoint_file.unlink()
            if self.index_file.exists():
                self.index_file.unlink()
            self._index.clear()
            logger.warning("Cleared all checkpoints", name=self.name)

    def iter_history(self, id: str) -> Iterator[CheckpointEntry]:
        """
        Iterate through all historical entries for an ID.

        Args:
            id: The ID to look up

        Yields:
            All checkpoint entries for this ID in chronological order
        """
        id = str(id)
        if not self.checkpoint_file.exists():
            return

        with open(self.checkpoint_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("id") == id:
                        yield CheckpointEntry.from_dict(data)
                except Exception:
                    continue


# Singleton instances for common use cases
job_checkpoint = CheckpointManager("jobs")
pipeline_checkpoint = CheckpointManager("pipelines")
