"""Centralized retry logic with exponential backoff and jitter.

Principle 6: Retry with Exponential Backoff
Failed operations are retried with increasing delays, up to a maximum.
Transient failures are common. Immediate retries often fail again.
Backing off gives systems time to recover.

Formula: delay = min(base * (multiplier ^ attempt) + jitter, max_delay)

Usage:
    retry_manager = RetryManager()

    # Using execute_with_retry
    result = await retry_manager.execute_with_retry(
        operation=fetch_data,
        config=RetryConfig(max_attempts=3),
    )

    # Using decorator
    @retry(max_attempts=3, on=[ErrorType.NETWORK, ErrorType.TRANSIENT])
    async def fetch_data():
        return await client.get("/data")
"""

import asyncio
import random
import functools
from dataclasses import dataclass, field
from typing import Callable, TypeVar, Optional, List, Set, Any, Awaitable, Union
import structlog

from app.services.error_classifier import ErrorClassifier, ErrorType, ClassifiedError, error_classifier

logger = structlog.get_logger()

T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 300.0  # 5 minutes max
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.1  # 10% jitter
    retryable_errors: Set[ErrorType] = field(default_factory=lambda: {
        ErrorType.NETWORK,
        ErrorType.RATE_LIMIT,
        ErrorType.TRANSIENT,
    })

    def should_retry(self, error_type: ErrorType) -> bool:
        """Check if an error type should be retried."""
        return error_type in self.retryable_errors


@dataclass
class RetryResult:
    """Result of a retry operation."""
    success: bool
    value: Any = None
    error: Optional[Exception] = None
    attempts: int = 0
    total_delay_seconds: float = 0.0
    classified_error: Optional[ClassifiedError] = None


class RetryManager:
    """
    Centralized retry manager with exponential backoff and error classification.

    Provides intelligent retry logic that:
    - Classifies errors before deciding to retry
    - Uses exponential backoff with jitter
    - Respects max attempts and delay limits
    - Logs retry attempts for debugging
    """

    def __init__(self, classifier: Optional[ErrorClassifier] = None):
        """
        Initialize retry manager.

        Args:
            classifier: Error classifier instance (uses default if not provided)
        """
        self.classifier = classifier or error_classifier

    def calculate_delay(
        self,
        attempt: int,
        config: RetryConfig,
        classified_error: Optional[ClassifiedError] = None,
    ) -> float:
        """
        Calculate delay before next retry attempt.

        Args:
            attempt: Current attempt number (1-based)
            config: Retry configuration
            classified_error: Classified error for customization

        Returns:
            Delay in seconds
        """
        # Use error-specific base delay if available
        if classified_error:
            base = classified_error.base_delay_seconds
        else:
            base = config.base_delay_seconds

        # Exponential backoff: base * multiplier^(attempt-1)
        delay = base * (config.exponential_base ** (attempt - 1))

        # Add jitter to prevent thundering herd
        if config.jitter:
            jitter_amount = delay * config.jitter_factor
            delay += random.uniform(-jitter_amount, jitter_amount)

        # Cap at max delay
        delay = min(delay, config.max_delay_seconds)

        # Ensure non-negative
        return max(0.0, delay)

    async def execute_with_retry(
        self,
        operation: Callable[[], Awaitable[T]],
        config: Optional[RetryConfig] = None,
        context: Optional[dict] = None,
    ) -> RetryResult:
        """
        Execute an async operation with retry logic.

        Args:
            operation: Async callable to execute
            config: Retry configuration (uses defaults if not provided)
            context: Optional context for error classification

        Returns:
            RetryResult with success status and value or error
        """
        config = config or RetryConfig()
        attempts = 0
        total_delay = 0.0
        last_error: Optional[Exception] = None
        last_classified: Optional[ClassifiedError] = None

        while attempts < config.max_attempts:
            attempts += 1

            try:
                logger.debug(
                    "Executing operation",
                    attempt=attempts,
                    max_attempts=config.max_attempts,
                )

                result = await operation()

                logger.debug(
                    "Operation succeeded",
                    attempt=attempts,
                    total_delay=round(total_delay, 2),
                )

                return RetryResult(
                    success=True,
                    value=result,
                    attempts=attempts,
                    total_delay_seconds=total_delay,
                )

            except Exception as e:
                last_error = e
                last_classified = self.classifier.classify(e, context)

                logger.warning(
                    "Operation failed",
                    attempt=attempts,
                    max_attempts=config.max_attempts,
                    error_type=last_classified.error_type.name,
                    retryable=last_classified.retryable,
                    error=str(e)[:100],
                )

                # Check if we should retry
                if not config.should_retry(last_classified.error_type):
                    logger.info(
                        "Error not retryable, failing immediately",
                        error_type=last_classified.error_type.name,
                    )
                    break

                # Check if we've exhausted attempts
                if attempts >= config.max_attempts:
                    logger.warning(
                        "Max attempts exhausted",
                        attempts=attempts,
                        total_delay=round(total_delay, 2),
                    )
                    break

                # Calculate and apply delay
                delay = self.calculate_delay(attempts, config, last_classified)
                total_delay += delay

                logger.info(
                    "Retrying after delay",
                    attempt=attempts,
                    next_attempt=attempts + 1,
                    delay_seconds=round(delay, 2),
                )

                await asyncio.sleep(delay)

        # All retries exhausted or non-retryable error
        return RetryResult(
            success=False,
            error=last_error,
            attempts=attempts,
            total_delay_seconds=total_delay,
            classified_error=last_classified,
        )

    def execute_sync_with_retry(
        self,
        operation: Callable[[], T],
        config: Optional[RetryConfig] = None,
        context: Optional[dict] = None,
    ) -> RetryResult:
        """
        Execute a sync operation with retry logic.

        Args:
            operation: Callable to execute
            config: Retry configuration
            context: Optional context for error classification

        Returns:
            RetryResult with success status and value or error
        """
        import time

        config = config or RetryConfig()
        attempts = 0
        total_delay = 0.0
        last_error: Optional[Exception] = None
        last_classified: Optional[ClassifiedError] = None

        while attempts < config.max_attempts:
            attempts += 1

            try:
                result = operation()
                return RetryResult(
                    success=True,
                    value=result,
                    attempts=attempts,
                    total_delay_seconds=total_delay,
                )

            except Exception as e:
                last_error = e
                last_classified = self.classifier.classify(e, context)

                if not config.should_retry(last_classified.error_type):
                    break

                if attempts >= config.max_attempts:
                    break

                delay = self.calculate_delay(attempts, config, last_classified)
                total_delay += delay
                time.sleep(delay)

        return RetryResult(
            success=False,
            error=last_error,
            attempts=attempts,
            total_delay_seconds=total_delay,
            classified_error=last_classified,
        )


# Singleton instance
retry_manager = RetryManager()


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 300.0,
    on: Optional[List[ErrorType]] = None,
    jitter: bool = True,
):
    """
    Decorator for adding retry logic to async functions.

    Usage:
        @retry(max_attempts=3, on=[ErrorType.NETWORK])
        async def fetch_data():
            return await client.get("/data")

    Args:
        max_attempts: Maximum number of attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        on: List of ErrorTypes to retry on (default: NETWORK, RATE_LIMIT, TRANSIENT)
        jitter: Whether to add jitter to delays

    Returns:
        Decorated function
    """
    retryable = set(on) if on else {
        ErrorType.NETWORK,
        ErrorType.RATE_LIMIT,
        ErrorType.TRANSIENT,
    }

    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay_seconds=base_delay,
        max_delay_seconds=max_delay,
        jitter=jitter,
        retryable_errors=retryable,
    )

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            async def operation():
                return await func(*args, **kwargs)

            result = await retry_manager.execute_with_retry(
                operation=operation,
                config=config,
            )

            if result.success:
                return result.value
            else:
                raise result.error

        return wrapper

    return decorator


def retry_sync(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 300.0,
    on: Optional[List[ErrorType]] = None,
    jitter: bool = True,
):
    """
    Decorator for adding retry logic to sync functions.

    Usage:
        @retry_sync(max_attempts=3)
        def fetch_data():
            return requests.get("/data")
    """
    retryable = set(on) if on else {
        ErrorType.NETWORK,
        ErrorType.RATE_LIMIT,
        ErrorType.TRANSIENT,
    }

    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay_seconds=base_delay,
        max_delay_seconds=max_delay,
        jitter=jitter,
        retryable_errors=retryable,
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            def operation():
                return func(*args, **kwargs)

            result = retry_manager.execute_sync_with_retry(
                operation=operation,
                config=config,
            )

            if result.success:
                return result.value
            else:
                raise result.error

        return wrapper

    return decorator
