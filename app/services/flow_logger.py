"""JSONL flow logging for debugging and tracing.

Principle 7: Flow Logging
Every operation produces a step-by-step trace in JSONL format.
When something fails at 3 AM, you need to know exactly what happened.
Regular logs are scattered. Flow logs are coherent narratives.

Format:
    {"ts": "2026-01-04T10:00:00Z", "flow_id": "job-123", "step": 0, "action": "start", "status": "pending"}
    {"ts": "2026-01-04T10:00:01Z", "flow_id": "job-123", "step": 1, "action": "submit", "status": "submitted", "request_id": "req-456"}
    {"ts": "2026-01-04T10:00:30Z", "flow_id": "job-123", "step": 2, "action": "poll", "status": "running", "progress": 45}
    {"ts": "2026-01-04T10:01:00Z", "flow_id": "job-123", "step": 3, "action": "complete", "status": "success", "output_url": "..."}

Debugging: cat flow_logs/job-123.jsonl | jq .

Usage:
    with FlowLogger("job", job_id) as flow:
        flow.log_step("start", "pending")
        result = do_work()
        flow.log_step("complete", "success", output=result)

    # Or manual lifecycle:
    flow = FlowLogger("pipeline", pipeline_id)
    flow.start()
    flow.log_step("execute", "running")
    flow.end()
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from contextlib import contextmanager
import structlog

try:
    import orjson

    ORJSON_AVAILABLE = True
except ImportError:
    ORJSON_AVAILABLE = False

logger = structlog.get_logger()


class FlowLogger:
    """
    JSONL flow logger for operation tracing.

    Creates a coherent narrative of an operation's lifecycle,
    enabling easy debugging of failures.

    Attributes:
        flow_type: Type of flow (e.g., "job", "pipeline")
        flow_id: Unique identifier for this flow
        output_dir: Directory for flow log files
    """

    DEFAULT_OUTPUT_DIR = "flow_logs"
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB before rotation

    def __init__(
        self,
        flow_type: str,
        flow_id: str,
        output_dir: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize flow logger.

        Args:
            flow_type: Type of flow (e.g., "job", "pipeline")
            flow_id: Unique identifier for this flow
            output_dir: Directory for log files
            context: Default context included in all entries
        """
        self.flow_type = flow_type
        self.flow_id = str(flow_id)
        self.step = 0
        self._file = None
        self._closed = False
        self._default_context = context or {}

        # Set up output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path.cwd() / self.DEFAULT_OUTPUT_DIR

        # Ensure directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Log file path
        self.log_file = self.output_dir / f"{flow_type}-{flow_id}.jsonl"

    def __enter__(self):
        """Context manager entry - log start."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - log end or error."""
        if exc_type is not None:
            self.log_error(exc_val, error_type=exc_type.__name__)
        else:
            self.end()
        return False  # Don't suppress exceptions

    def start(self) -> "FlowLogger":
        """Log flow start."""
        self._open_file()
        self.log_step("start", "pending")
        return self

    def end(self, status: str = "completed"):
        """Log flow end."""
        self.log_step("end", status)
        self._close_file()

    def _open_file(self):
        """Open log file for appending."""
        if self._file is not None:
            return

        # Check file size for rotation
        if self.log_file.exists():
            size = self.log_file.stat().st_size
            if size > self.MAX_FILE_SIZE_BYTES:
                self._rotate_file()

        self._file = open(self.log_file, "a", encoding="utf-8")

    def _close_file(self):
        """Close log file."""
        if self._file is not None:
            self._file.flush()
            self._file.close()
            self._file = None
            self._closed = True

    def _rotate_file(self):
        """Rotate log file when too large."""
        if self.log_file.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated = self.log_file.with_suffix(f".{timestamp}.jsonl")
            self.log_file.rename(rotated)
            logger.info("Rotated flow log", old=self.log_file, new=rotated)

    def _serialize(self, entry: dict) -> str:
        """Serialize entry to JSON string."""
        if ORJSON_AVAILABLE:
            return orjson.dumps(entry).decode("utf-8")
        return json.dumps(entry, default=str)

    def log_step(
        self,
        action: str,
        status: str,
        **context,
    ):
        """
        Log a step in the flow.

        Args:
            action: Action being performed (e.g., "submit", "poll", "complete")
            status: Current status (e.g., "pending", "running", "success")
            **context: Additional context data
        """
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "flow_type": self.flow_type,
            "flow_id": self.flow_id,
            "step": self.step,
            "action": action,
            "status": status,
            **self._default_context,
            **context,
        }

        self._write_entry(entry)
        self.step += 1

    def log_error(
        self,
        error: Exception,
        error_type: Optional[str] = None,
        **context,
    ):
        """
        Log an error in the flow.

        Args:
            error: The exception that occurred
            error_type: Optional error type name
            **context: Additional context data
        """
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "flow_type": self.flow_type,
            "flow_id": self.flow_id,
            "step": self.step,
            "action": "error",
            "status": "failed",
            "error_type": error_type or type(error).__name__,
            "error_message": str(error),
            **self._default_context,
            **context,
        }

        self._write_entry(entry)
        self.step += 1

    def log_progress(
        self,
        progress_pct: float,
        message: Optional[str] = None,
        **context,
    ):
        """
        Log progress update.

        Args:
            progress_pct: Progress percentage (0-100)
            message: Optional progress message
            **context: Additional context data
        """
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "flow_type": self.flow_type,
            "flow_id": self.flow_id,
            "step": self.step,
            "action": "progress",
            "status": "running",
            "progress_pct": round(progress_pct, 2),
            **self._default_context,
            **context,
        }

        if message:
            entry["message"] = message

        self._write_entry(entry)
        # Don't increment step for progress updates

    def log_retry(
        self,
        attempt: int,
        max_attempts: int,
        delay_seconds: float,
        error: Optional[str] = None,
    ):
        """
        Log a retry attempt.

        Args:
            attempt: Current attempt number
            max_attempts: Maximum attempts
            delay_seconds: Delay before next attempt
            error: Error that triggered retry
        """
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "flow_type": self.flow_type,
            "flow_id": self.flow_id,
            "step": self.step,
            "action": "retry",
            "status": "retrying",
            "attempt": attempt,
            "max_attempts": max_attempts,
            "delay_seconds": round(delay_seconds, 2),
            **self._default_context,
        }

        if error:
            entry["error"] = error

        self._write_entry(entry)
        self.step += 1

    def log_result(
        self,
        result_type: str,
        result_value: Any,
        **context,
    ):
        """
        Log a result/output.

        Args:
            result_type: Type of result (e.g., "video_url", "image_urls")
            result_value: The result value
            **context: Additional context data
        """
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "flow_type": self.flow_type,
            "flow_id": self.flow_id,
            "step": self.step,
            "action": "result",
            "status": "success",
            "result_type": result_type,
            "result": result_value,
            **self._default_context,
            **context,
        }

        self._write_entry(entry)
        self.step += 1

    def _write_entry(self, entry: dict):
        """Write an entry to the log file."""
        if self._closed:
            logger.warning(
                "Attempting to write to closed flow log",
                flow_id=self.flow_id,
            )
            return

        self._open_file()

        try:
            line = self._serialize(entry) + "\n"
            self._file.write(line)
            self._file.flush()
        except Exception as e:
            logger.error("Failed to write flow log entry", error=str(e))

    def add_context(self, **context):
        """Add default context to be included in all entries."""
        self._default_context.update(context)

    def __del__(self):
        """Ensure file is closed on garbage collection."""
        self._close_file()


@contextmanager
def flow_log(
    flow_type: str,
    flow_id: str,
    output_dir: Optional[str] = None,
    **context,
):
    """
    Context manager for flow logging.

    Usage:
        with flow_log("job", job_id) as flow:
            flow.log_step("process", "running")
            result = do_work()
            flow.log_result("output", result)

    Args:
        flow_type: Type of flow
        flow_id: Unique identifier
        output_dir: Directory for log files
        **context: Default context for all entries

    Yields:
        FlowLogger instance
    """
    flow = FlowLogger(flow_type, flow_id, output_dir=output_dir, context=context)
    try:
        flow.start()
        yield flow
        flow.end("success")
    except Exception as e:
        flow.log_error(e)
        flow.end("failed")
        raise


class JobFlowLogger(FlowLogger):
    """Specialized flow logger for job operations."""

    def __init__(self, job_id: str, model: Optional[str] = None, **context):
        if model:
            context["model"] = model
        super().__init__("job", job_id, context=context)

    def log_submit(self, request_id: str, **context):
        """Log job submission."""
        self.log_step("submit", "submitted", request_id=request_id, **context)

    def log_poll(self, poll_status: str, **context):
        """Log polling result."""
        self.log_step("poll", poll_status, **context)

    def log_complete(self, video_url: Optional[str] = None, **context):
        """Log job completion."""
        self.log_step("complete", "success", video_url=video_url, **context)


class PipelineFlowLogger(FlowLogger):
    """Specialized flow logger for pipeline operations."""

    def __init__(self, pipeline_id: int, mode: Optional[str] = None, **context):
        if mode:
            context["mode"] = mode
        super().__init__("pipeline", str(pipeline_id), context=context)

    def log_step_start(self, step_id: int, step_type: str, **context):
        """Log step start."""
        self.log_step(
            f"step_{step_id}_start",
            "running",
            step_id=step_id,
            step_type=step_type,
            **context,
        )

    def log_step_complete(self, step_id: int, outputs_count: int = 0, **context):
        """Log step completion."""
        self.log_step(
            f"step_{step_id}_complete",
            "completed",
            step_id=step_id,
            outputs_count=outputs_count,
            **context,
        )

    def log_step_failed(self, step_id: int, error: str, **context):
        """Log step failure."""
        self.log_step(
            f"step_{step_id}_failed",
            "failed",
            step_id=step_id,
            error=error,
            **context,
        )


# Convenience function to read and parse flow logs
def read_flow_log(
    flow_type: str,
    flow_id: str,
    output_dir: Optional[str] = None,
) -> list:
    """
    Read and parse a flow log file.

    Args:
        flow_type: Type of flow
        flow_id: Flow identifier
        output_dir: Directory containing logs

    Returns:
        List of log entries as dictionaries
    """
    if output_dir:
        log_dir = Path(output_dir)
    else:
        log_dir = Path.cwd() / FlowLogger.DEFAULT_OUTPUT_DIR

    log_file = log_dir / f"{flow_type}-{flow_id}.jsonl"

    if not log_file.exists():
        return []

    entries = []
    with open(log_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    return entries
