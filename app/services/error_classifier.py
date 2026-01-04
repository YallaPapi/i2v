"""Error classification for intelligent retry and failure handling.

Principle 2: Error Classification
Not all errors are equal. Classify them and handle accordingly.
- NETWORK: Retry with backoff (timeouts, connection refused)
- RATE_LIMIT: Retry with longer backoff (HTTP 429, quota exceeded)
- INVALID_INPUT: Fail immediately (HTTP 400, validation error)
- TRANSIENT: Retry 2-3x then fail (HTTP 500-503)
- PERMANENT: Fail immediately, flag for review (HTTP 401/403)
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, Any
import httpx
import structlog

logger = structlog.get_logger()


class ErrorType(Enum):
    """Classification of errors for retry decisions."""
    NETWORK = auto()      # Timeouts, connection issues - retry with backoff
    RATE_LIMIT = auto()   # HTTP 429, quota exceeded - retry with longer backoff
    INVALID_INPUT = auto() # HTTP 400, validation errors - fail immediately
    TRANSIENT = auto()    # HTTP 500-503 - retry 2-3x then fail
    PERMANENT = auto()    # HTTP 401/403, suspended - fail, flag for review
    UNKNOWN = auto()      # Unclassified errors - default to transient behavior


@dataclass
class ClassifiedError:
    """Error with classification and context for intelligent handling."""
    error_type: ErrorType
    original_error: Exception
    message: str
    status_code: Optional[int] = None
    retryable: bool = True
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    context: Optional[dict] = None

    def __post_init__(self):
        """Set retry parameters based on error type."""
        if self.error_type == ErrorType.NETWORK:
            self.retryable = True
            self.max_retries = 5
            self.base_delay_seconds = 1.0
        elif self.error_type == ErrorType.RATE_LIMIT:
            self.retryable = True
            self.max_retries = 5
            self.base_delay_seconds = 30.0  # Longer backoff for rate limits
        elif self.error_type == ErrorType.INVALID_INPUT:
            self.retryable = False
            self.max_retries = 0
        elif self.error_type == ErrorType.TRANSIENT:
            self.retryable = True
            self.max_retries = 3
            self.base_delay_seconds = 2.0
        elif self.error_type == ErrorType.PERMANENT:
            self.retryable = False
            self.max_retries = 0
        else:  # UNKNOWN
            self.retryable = True
            self.max_retries = 2
            self.base_delay_seconds = 5.0


class ErrorClassifier:
    """
    Classifies errors for intelligent retry and failure handling.

    Usage:
        classifier = ErrorClassifier()
        classified = classifier.classify(error)

        if classified.retryable:
            # Retry with classified.base_delay_seconds
        else:
            # Fail immediately
    """

    # HTTP status code to error type mapping
    STATUS_CODE_MAP = {
        # Rate limiting
        429: ErrorType.RATE_LIMIT,

        # Invalid input - don't retry
        400: ErrorType.INVALID_INPUT,
        404: ErrorType.INVALID_INPUT,
        405: ErrorType.INVALID_INPUT,
        422: ErrorType.INVALID_INPUT,

        # Permanent errors - don't retry, flag for review
        401: ErrorType.PERMANENT,
        403: ErrorType.PERMANENT,
        402: ErrorType.PERMANENT,  # Payment required

        # Transient server errors - retry a few times
        500: ErrorType.TRANSIENT,
        502: ErrorType.TRANSIENT,
        503: ErrorType.TRANSIENT,
        504: ErrorType.TRANSIENT,
    }

    # Exception types that indicate network issues
    NETWORK_EXCEPTIONS = (
        TimeoutError,
        ConnectionError,
        ConnectionResetError,
        ConnectionRefusedError,
        BrokenPipeError,
        OSError,
    )

    def classify(self, error: Exception, context: Optional[dict] = None) -> ClassifiedError:
        """
        Classify an error for retry decisions.

        Args:
            error: The exception to classify
            context: Optional context dict (job_id, model, etc.)

        Returns:
            ClassifiedError with type, retry parameters, and context
        """
        error_type = self._determine_type(error)
        status_code = self._extract_status_code(error)
        message = self._format_message(error, error_type)

        classified = ClassifiedError(
            error_type=error_type,
            original_error=error,
            message=message,
            status_code=status_code,
            context=context,
        )

        logger.debug(
            "Error classified",
            error_type=error_type.name,
            retryable=classified.retryable,
            max_retries=classified.max_retries,
            status_code=status_code,
            message=message[:100],
        )

        return classified

    def _determine_type(self, error: Exception) -> ErrorType:
        """Determine the error type from the exception."""
        # Check for network-level exceptions first
        if isinstance(error, self.NETWORK_EXCEPTIONS):
            return ErrorType.NETWORK

        # Check httpx-specific exceptions
        if isinstance(error, httpx.TimeoutException):
            return ErrorType.NETWORK
        if isinstance(error, httpx.ConnectError):
            return ErrorType.NETWORK
        if isinstance(error, httpx.ReadTimeout):
            return ErrorType.NETWORK
        if isinstance(error, httpx.WriteTimeout):
            return ErrorType.NETWORK
        if isinstance(error, httpx.ConnectTimeout):
            return ErrorType.NETWORK

        # Check for HTTP errors with status codes
        status_code = self._extract_status_code(error)
        if status_code:
            return self.STATUS_CODE_MAP.get(status_code, ErrorType.TRANSIENT)

        # Check error message patterns
        error_str = str(error).lower()

        if any(term in error_str for term in ['timeout', 'timed out']):
            return ErrorType.NETWORK

        if any(term in error_str for term in ['rate limit', 'too many requests', 'quota']):
            return ErrorType.RATE_LIMIT

        if any(term in error_str for term in ['invalid', 'validation', 'bad request']):
            return ErrorType.INVALID_INPUT

        if any(term in error_str for term in ['unauthorized', 'forbidden', 'api key', 'authentication']):
            return ErrorType.PERMANENT

        # Default to unknown
        return ErrorType.UNKNOWN

    def _extract_status_code(self, error: Exception) -> Optional[int]:
        """Extract HTTP status code from various error types."""
        # httpx HTTPStatusError
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code

        # Check for status_code attribute
        if hasattr(error, 'status_code'):
            return getattr(error, 'status_code')

        # Check for response attribute with status_code
        if hasattr(error, 'response'):
            response = getattr(error, 'response')
            if hasattr(response, 'status_code'):
                return response.status_code

        return None

    def _format_message(self, error: Exception, error_type: ErrorType) -> str:
        """Format an actionable error message."""
        base_message = str(error)

        suggestions = {
            ErrorType.NETWORK: "Check network connectivity and try again.",
            ErrorType.RATE_LIMIT: "Rate limit exceeded. Will retry with backoff.",
            ErrorType.INVALID_INPUT: "Request validation failed. Check input parameters.",
            ErrorType.TRANSIENT: "Server error. Will retry automatically.",
            ErrorType.PERMANENT: "Authentication/authorization failed. Check API credentials.",
            ErrorType.UNKNOWN: "Unexpected error. Check logs for details.",
        }

        suggestion = suggestions.get(error_type, "")
        return f"{base_message} [{error_type.name}] {suggestion}"

    def is_retryable(self, error: Exception) -> bool:
        """Quick check if an error is retryable without full classification."""
        return self.classify(error).retryable

    def get_retry_delay(self, error: Exception, attempt: int = 1) -> float:
        """Get recommended retry delay for an error."""
        classified = self.classify(error)
        if not classified.retryable:
            return 0.0

        # Exponential backoff: base * 2^attempt
        delay = classified.base_delay_seconds * (2 ** (attempt - 1))

        # Cap at 5 minutes
        return min(delay, 300.0)


# Singleton instance for convenience
error_classifier = ErrorClassifier()
