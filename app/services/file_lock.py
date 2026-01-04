"""File-based locking for shared resources.

Principle 4: File-Based Locking
Use file locks to prevent concurrent access to shared resources.
Database locks are unreliable (especially SQLite). Distributed locks need infrastructure.
File locks are simple, portable, and work.

Usage:
    with FileLock("jobs.lock"):
        jobs = claim_pending_jobs()

    # Or with timeout:
    with FileLock("critical.lock", timeout=30):
        do_critical_work()
"""

import os
import time
from pathlib import Path
from typing import Optional
from contextlib import contextmanager
import structlog

try:
    import portalocker
    PORTALOCKER_AVAILABLE = True
except ImportError:
    PORTALOCKER_AVAILABLE = False

logger = structlog.get_logger()


class LockAcquisitionError(Exception):
    """Raised when a lock cannot be acquired within the timeout."""
    pass


class FileLock:
    """
    Cross-platform file-based locking mechanism.

    Provides exclusive access to shared resources using file locks.
    Implements context manager protocol for easy use with 'with' statement.

    Attributes:
        lock_path: Path to the lock file
        timeout: Maximum seconds to wait for lock acquisition
        check_interval: Seconds between lock acquisition attempts
    """

    # Default directory for lock files
    DEFAULT_LOCK_DIR = ".locks"

    def __init__(
        self,
        name: str,
        lock_dir: Optional[str] = None,
        timeout: float = 30.0,
        check_interval: float = 0.1,
    ):
        """
        Initialize a file lock.

        Args:
            name: Name of the lock (will create {name}.lock file)
            lock_dir: Directory for lock files (default: .locks in cwd)
            timeout: Max seconds to wait for lock (default: 30)
            check_interval: Seconds between acquisition attempts (default: 0.1)
        """
        if not PORTALOCKER_AVAILABLE:
            raise ImportError(
                "portalocker is required for file locking. "
                "Install with: pip install portalocker"
            )

        self.name = name
        self.timeout = timeout
        self.check_interval = check_interval

        # Set up lock directory
        if lock_dir:
            self.lock_dir = Path(lock_dir)
        else:
            self.lock_dir = Path.cwd() / self.DEFAULT_LOCK_DIR

        # Ensure lock directory exists
        self.lock_dir.mkdir(parents=True, exist_ok=True)

        # Lock file path
        self.lock_path = self.lock_dir / f"{name}.lock"

        # Internal state
        self._file = None
        self._acquired = False

    def __enter__(self):
        """Acquire the lock on context entry."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release the lock on context exit."""
        self.release()
        return False  # Don't suppress exceptions

    def acquire(self) -> bool:
        """
        Acquire the file lock.

        Blocks until lock is acquired or timeout is reached.

        Returns:
            True if lock was acquired

        Raises:
            LockAcquisitionError: If lock cannot be acquired within timeout
        """
        if self._acquired:
            logger.warning("Lock already acquired", lock=self.name)
            return True

        start_time = time.monotonic()
        last_error = None

        logger.debug("Attempting to acquire lock", lock=self.name, timeout=self.timeout)

        while True:
            try:
                # Open the lock file (create if doesn't exist)
                self._file = open(self.lock_path, 'w')

                # Try to acquire exclusive lock (non-blocking)
                portalocker.lock(
                    self._file,
                    portalocker.LOCK_EX | portalocker.LOCK_NB
                )

                # Write PID for debugging
                self._file.write(f"{os.getpid()}\n")
                self._file.flush()

                self._acquired = True
                logger.info(
                    "Lock acquired",
                    lock=self.name,
                    pid=os.getpid(),
                    elapsed=round(time.monotonic() - start_time, 3),
                )
                return True

            except portalocker.LockException as e:
                last_error = e
                # Lock held by another process

                # Clean up failed attempt
                if self._file:
                    try:
                        self._file.close()
                    except Exception:
                        pass
                    self._file = None

                # Check timeout
                elapsed = time.monotonic() - start_time
                if elapsed >= self.timeout:
                    break

                # Wait and retry
                time.sleep(self.check_interval)

            except Exception as e:
                # Unexpected error
                if self._file:
                    try:
                        self._file.close()
                    except Exception:
                        pass
                    self._file = None

                logger.error("Lock acquisition failed", lock=self.name, error=str(e))
                raise LockAcquisitionError(f"Failed to acquire lock {self.name}: {e}")

        # Timeout reached
        logger.warning(
            "Lock acquisition timed out",
            lock=self.name,
            timeout=self.timeout,
        )
        raise LockAcquisitionError(
            f"Could not acquire lock {self.name} within {self.timeout}s"
        )

    def release(self) -> bool:
        """
        Release the file lock.

        Returns:
            True if lock was released, False if wasn't held
        """
        if not self._acquired or not self._file:
            logger.debug("Lock not held, nothing to release", lock=self.name)
            return False

        try:
            # Unlock the file
            portalocker.unlock(self._file)

            # Close the file
            self._file.close()
            self._file = None
            self._acquired = False

            logger.info("Lock released", lock=self.name, pid=os.getpid())
            return True

        except Exception as e:
            logger.error("Error releasing lock", lock=self.name, error=str(e))
            # Try to clean up anyway
            if self._file:
                try:
                    self._file.close()
                except Exception:
                    pass
            self._file = None
            self._acquired = False
            return False

    @property
    def is_locked(self) -> bool:
        """Check if this lock instance holds the lock."""
        return self._acquired

    def __del__(self):
        """Ensure lock is released on garbage collection."""
        if self._acquired:
            try:
                self.release()
            except Exception:
                pass


@contextmanager
def file_lock(name: str, timeout: float = 30.0, lock_dir: Optional[str] = None):
    """
    Context manager for file locking.

    Usage:
        with file_lock("jobs"):
            claim_jobs()

    Args:
        name: Lock name
        timeout: Max seconds to wait for lock
        lock_dir: Directory for lock files

    Yields:
        The FileLock instance
    """
    lock = FileLock(name, lock_dir=lock_dir, timeout=timeout)
    try:
        lock.acquire()
        yield lock
    finally:
        lock.release()


class JobLock:
    """
    Specialized lock for job claiming operations.

    Provides atomic job claiming to prevent multiple workers
    from claiming the same jobs.

    Usage:
        with JobLock() as lock:
            jobs = claim_pending_jobs(limit=5, worker_id=MY_ID)
    """

    def __init__(self, lock_dir: Optional[str] = None, timeout: float = 30.0):
        """
        Initialize job lock.

        Args:
            lock_dir: Directory for lock files
            timeout: Max seconds to wait for lock
        """
        self._lock = FileLock(
            name="jobs",
            lock_dir=lock_dir,
            timeout=timeout,
        )

    def __enter__(self):
        """Acquire job lock."""
        self._lock.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release job lock."""
        self._lock.release()
        return False


class PipelineLock:
    """
    Specialized lock for pipeline execution.

    Prevents concurrent execution of the same pipeline.

    Usage:
        with PipelineLock(pipeline_id=123):
            execute_pipeline(123)
    """

    def __init__(
        self,
        pipeline_id: int,
        lock_dir: Optional[str] = None,
        timeout: float = 60.0,
    ):
        """
        Initialize pipeline lock.

        Args:
            pipeline_id: ID of the pipeline to lock
            lock_dir: Directory for lock files
            timeout: Max seconds to wait for lock
        """
        self._lock = FileLock(
            name=f"pipeline_{pipeline_id}",
            lock_dir=lock_dir,
            timeout=timeout,
        )
        self.pipeline_id = pipeline_id

    def __enter__(self):
        """Acquire pipeline lock."""
        self._lock.acquire()
        logger.info("Pipeline locked", pipeline_id=self.pipeline_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release pipeline lock."""
        self._lock.release()
        logger.info("Pipeline unlocked", pipeline_id=self.pipeline_id)
        return False
