"""Defense-in-depth input validation at the service layer.

Principle 5: Defense in Depth
Validate at every layer. Never trust upstream.
Bugs happen. APIs change. Users do unexpected things.
Multiple validation layers catch what single layers miss.

Pattern:
    Request -> Router Validation -> Service Validation -> Execution
                    |                       |
              "Is it JSON?"          "Does entity exist?"
              "Required fields?"     "Has quota remaining?"

Usage:
    validator = InputValidator()

    # URL validation
    validator.validate_url(url, schemes=["https"])

    # Image URL validation with optional reachability check
    await validator.validate_image_url_async(url, check_reachable=True)

    # Required fields
    validator.validate_required_fields(data, ["image_url", "prompt"])

    # Enum validation
    validator.validate_enum_value(model, ["wan", "kling", "veo2"])

    # Prompt validation
    validator.validate_prompt(prompt, max_length=1000)
"""

import re
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type, Union
from dataclasses import dataclass
from urllib.parse import urlparse
import structlog
import httpx

logger = structlog.get_logger()


@dataclass
class ValidationError(Exception):
    """Exception raised when validation fails.

    Attributes:
        field: Name of the field that failed validation
        message: Human-readable error message
        value: The invalid value (optional, for debugging)
        code: Machine-readable error code
    """
    field: str
    message: str
    value: Any = None
    code: str = "validation_error"

    def __str__(self):
        if self.value is not None:
            # Truncate long values
            value_str = str(self.value)
            if len(value_str) > 50:
                value_str = value_str[:50] + "..."
            return f"{self.field}: {self.message} (got: {value_str})"
        return f"{self.field}: {self.message}"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "field": self.field,
            "message": self.message,
            "code": self.code,
        }


class ValidationErrorCollection(Exception):
    """Collection of multiple validation errors."""

    def __init__(self, errors: List[ValidationError]):
        self.errors = errors
        super().__init__(f"Validation failed: {len(errors)} error(s)")

    def __str__(self):
        return "; ".join(str(e) for e in self.errors)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "detail": "Validation failed",
            "errors": [e.to_dict() for e in self.errors],
        }


class InputValidator:
    """
    Service-layer input validator for defense-in-depth validation.

    Validates inputs that have already passed Pydantic router validation.
    This second layer catches business logic constraints and runtime issues.

    Attributes:
        default_url_schemes: Default allowed URL schemes
        default_max_prompt_length: Default maximum prompt length
        default_max_file_size_mb: Default maximum file size in MB
    """

    # Default configuration
    DEFAULT_URL_SCHEMES = {"http", "https"}
    DEFAULT_IMAGE_SCHEMES = {"https"}  # Prefer HTTPS for images
    DEFAULT_MAX_PROMPT_LENGTH = 2000
    DEFAULT_MIN_PROMPT_LENGTH = 1
    DEFAULT_MAX_FILE_SIZE_MB = 20
    DEFAULT_HTTP_TIMEOUT = 10.0

    # Valid image extensions
    VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

    # URL regex pattern
    URL_PATTERN = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    # Model resolution mapping (duplicated for validation)
    MODEL_RESOLUTIONS: Dict[str, List[str]] = {
        "wan": ["480p", "720p", "1080p"],
        "wan21": ["480p", "720p"],
        "wan22": ["480p", "580p", "720p"],
        "wan-pro": ["1080p"],
        "kling": ["720p", "1080p"],
        "kling-master": ["720p", "1080p"],
        "kling-standard": ["720p", "1080p"],
        "veo2": ["720p"],
        "veo31": ["720p", "1080p"],
        "veo31-fast": ["720p", "1080p"],
        "veo31-flf": ["720p", "1080p"],
        "veo31-fast-flf": ["720p", "1080p"],
        "sora-2": ["720p"],
        "sora-2-pro": ["720p", "1080p"],
    }

    # Model duration mapping
    MODEL_DURATIONS: Dict[str, List[int]] = {
        "wan": [5],
        "wan21": [5],
        "wan22": [5],
        "wan-pro": [5],
        "kling": [5, 10],
        "kling-master": [5, 10],
        "kling-standard": [5, 10],
        "veo2": [4, 6, 8],
        "veo31": [4, 6, 8],
        "veo31-fast": [4, 6, 8],
        "veo31-flf": [4, 6, 8],
        "veo31-fast-flf": [4, 6, 8],
        "sora-2": [4, 8, 12],
        "sora-2-pro": [4, 8, 12],
    }

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        """
        Initialize the validator.

        Args:
            http_client: Optional async HTTP client for reachability checks
        """
        self._http_client = http_client

    def validate_url(
        self,
        url: str,
        field_name: str = "url",
        schemes: Optional[Set[str]] = None,
        require_path: bool = False,
    ) -> str:
        """
        Validate a URL format and scheme.

        Args:
            url: The URL to validate
            field_name: Name of the field for error messages
            schemes: Allowed URL schemes (default: http, https)
            require_path: If True, URL must have a path component

        Returns:
            The validated URL (stripped of whitespace)

        Raises:
            ValidationError: If URL is invalid
        """
        if not url:
            raise ValidationError(
                field=field_name,
                message="URL is required",
                code="required",
            )

        url = url.strip()

        # Check format with regex
        if not self.URL_PATTERN.match(url):
            raise ValidationError(
                field=field_name,
                message="Invalid URL format",
                value=url,
                code="invalid_format",
            )

        # Parse and validate components
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValidationError(
                field=field_name,
                message=f"Failed to parse URL: {str(e)}",
                value=url,
                code="parse_error",
            )

        # Check scheme
        allowed_schemes = schemes or self.DEFAULT_URL_SCHEMES
        if parsed.scheme.lower() not in allowed_schemes:
            raise ValidationError(
                field=field_name,
                message=f"URL scheme must be one of: {', '.join(allowed_schemes)}",
                value=parsed.scheme,
                code="invalid_scheme",
            )

        # Check for path if required
        if require_path and not parsed.path.strip("/"):
            raise ValidationError(
                field=field_name,
                message="URL must include a path",
                value=url,
                code="missing_path",
            )

        logger.debug("URL validated", field=field_name, url=url[:50])
        return url

    def validate_image_url(
        self,
        url: str,
        field_name: str = "image_url",
        check_extension: bool = True,
    ) -> str:
        """
        Validate an image URL.

        Args:
            url: The image URL to validate
            field_name: Name of the field for error messages
            check_extension: If True, verify file extension

        Returns:
            The validated URL

        Raises:
            ValidationError: If URL is invalid for images
        """
        # First validate as general URL
        url = self.validate_url(
            url,
            field_name=field_name,
            schemes=self.DEFAULT_IMAGE_SCHEMES,
            require_path=True,
        )

        # Check file extension if required
        if check_extension:
            parsed = urlparse(url)
            path = parsed.path.lower()

            # Extract extension (handle query params)
            ext = None
            for valid_ext in self.VALID_IMAGE_EXTENSIONS:
                if valid_ext in path:
                    ext = valid_ext
                    break

            # Some URLs don't have extensions but are still valid (e.g., CDN URLs)
            # We'll allow them but log a warning
            if ext is None and not any(path.endswith(e) for e in self.VALID_IMAGE_EXTENSIONS):
                logger.debug(
                    "Image URL has no recognizable extension",
                    url=url[:100],
                )

        return url

    async def validate_image_url_async(
        self,
        url: str,
        field_name: str = "image_url",
        check_reachable: bool = False,
        check_content_type: bool = False,
    ) -> str:
        """
        Validate an image URL with optional reachability check.

        Args:
            url: The image URL to validate
            field_name: Name of the field for error messages
            check_reachable: If True, perform HEAD request to verify URL
            check_content_type: If True, verify Content-Type header

        Returns:
            The validated URL

        Raises:
            ValidationError: If URL is invalid or unreachable
        """
        # First validate format
        url = self.validate_image_url(url, field_name=field_name)

        # Optionally check reachability
        if check_reachable or check_content_type:
            await self._check_url_reachable(
                url,
                field_name=field_name,
                check_content_type=check_content_type,
            )

        return url

    async def _check_url_reachable(
        self,
        url: str,
        field_name: str,
        check_content_type: bool = False,
    ):
        """Check if a URL is reachable via HEAD request."""
        client = self._http_client or httpx.AsyncClient()
        close_client = self._http_client is None

        try:
            response = await client.head(
                url,
                timeout=self.DEFAULT_HTTP_TIMEOUT,
                follow_redirects=True,
            )

            if response.status_code >= 400:
                raise ValidationError(
                    field=field_name,
                    message=f"URL not accessible (HTTP {response.status_code})",
                    value=url,
                    code="unreachable",
                )

            if check_content_type:
                content_type = response.headers.get("content-type", "")
                if not content_type.startswith("image/"):
                    raise ValidationError(
                        field=field_name,
                        message=f"URL does not point to an image (Content-Type: {content_type})",
                        value=url,
                        code="invalid_content_type",
                    )

        except httpx.TimeoutException:
            raise ValidationError(
                field=field_name,
                message="URL timed out during validation",
                value=url,
                code="timeout",
            )
        except httpx.RequestError as e:
            raise ValidationError(
                field=field_name,
                message=f"Failed to reach URL: {str(e)}",
                value=url,
                code="connection_error",
            )
        finally:
            if close_client:
                await client.aclose()

    def validate_required_fields(
        self,
        data: Dict[str, Any],
        required_fields: List[str],
        allow_empty: bool = False,
    ) -> Dict[str, Any]:
        """
        Validate that required fields exist and are non-empty.

        Args:
            data: Dictionary of data to validate
            required_fields: List of required field names
            allow_empty: If True, allow empty strings/lists

        Returns:
            The validated data dictionary

        Raises:
            ValidationErrorCollection: If any required fields are missing
        """
        errors = []

        for field in required_fields:
            if field not in data:
                errors.append(ValidationError(
                    field=field,
                    message="Field is required",
                    code="required",
                ))
            elif not allow_empty:
                value = data[field]
                if value is None:
                    errors.append(ValidationError(
                        field=field,
                        message="Field cannot be null",
                        code="null_value",
                    ))
                elif isinstance(value, str) and not value.strip():
                    errors.append(ValidationError(
                        field=field,
                        message="Field cannot be empty",
                        code="empty_string",
                    ))
                elif isinstance(value, (list, dict)) and len(value) == 0:
                    errors.append(ValidationError(
                        field=field,
                        message="Field cannot be empty",
                        code="empty_collection",
                    ))

        if errors:
            raise ValidationErrorCollection(errors)

        return data

    def validate_enum_value(
        self,
        value: Any,
        valid_values: Union[List[Any], Set[Any], Type[Enum]],
        field_name: str = "value",
    ) -> Any:
        """
        Validate that a value is within allowed options.

        Args:
            value: The value to validate
            valid_values: List, set, or Enum class of valid values
            field_name: Name of the field for error messages

        Returns:
            The validated value

        Raises:
            ValidationError: If value is not in valid options
        """
        # Convert Enum class to list of values
        if isinstance(valid_values, type) and issubclass(valid_values, Enum):
            valid_set = {e.value for e in valid_values}
        else:
            valid_set = set(valid_values)

        if value not in valid_set:
            # Format valid options nicely
            options_str = ", ".join(str(v) for v in sorted(valid_set, key=str)[:10])
            if len(valid_set) > 10:
                options_str += f" ... ({len(valid_set)} total)"

            raise ValidationError(
                field=field_name,
                message=f"Invalid value. Valid options: {options_str}",
                value=value,
                code="invalid_choice",
            )

        return value

    def validate_prompt(
        self,
        prompt: str,
        field_name: str = "prompt",
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        allow_empty: bool = False,
    ) -> str:
        """
        Validate a prompt string.

        Args:
            prompt: The prompt to validate
            field_name: Name of the field for error messages
            min_length: Minimum length (default: 1)
            max_length: Maximum length (default: 2000)
            allow_empty: If True, allow empty prompts

        Returns:
            The validated and stripped prompt

        Raises:
            ValidationError: If prompt is invalid
        """
        if prompt is None:
            if allow_empty:
                return ""
            raise ValidationError(
                field=field_name,
                message="Prompt is required",
                code="required",
            )

        prompt = prompt.strip()

        min_len = min_length if min_length is not None else self.DEFAULT_MIN_PROMPT_LENGTH
        max_len = max_length if max_length is not None else self.DEFAULT_MAX_PROMPT_LENGTH

        if not prompt and not allow_empty:
            raise ValidationError(
                field=field_name,
                message="Prompt cannot be empty",
                code="empty_string",
            )

        if len(prompt) < min_len:
            raise ValidationError(
                field=field_name,
                message=f"Prompt must be at least {min_len} characters",
                value=prompt,
                code="too_short",
            )

        if len(prompt) > max_len:
            raise ValidationError(
                field=field_name,
                message=f"Prompt cannot exceed {max_len} characters",
                value=prompt[:50] + "...",
                code="too_long",
            )

        return prompt

    def validate_prompts_list(
        self,
        prompts: List[str],
        field_name: str = "prompts",
        min_count: int = 1,
        max_count: int = 10,
        max_prompt_length: Optional[int] = None,
    ) -> List[str]:
        """
        Validate a list of prompts.

        Args:
            prompts: List of prompts to validate
            field_name: Name of the field for error messages
            min_count: Minimum number of prompts
            max_count: Maximum number of prompts
            max_prompt_length: Maximum length per prompt

        Returns:
            List of validated and stripped prompts

        Raises:
            ValidationErrorCollection: If any prompts are invalid
        """
        if not prompts:
            raise ValidationError(
                field=field_name,
                message="At least one prompt is required",
                code="empty_collection",
            )

        if len(prompts) < min_count:
            raise ValidationError(
                field=field_name,
                message=f"At least {min_count} prompt(s) required",
                code="too_few",
            )

        if len(prompts) > max_count:
            raise ValidationError(
                field=field_name,
                message=f"Cannot exceed {max_count} prompts",
                code="too_many",
            )

        validated = []
        errors = []

        for i, prompt in enumerate(prompts):
            try:
                validated.append(self.validate_prompt(
                    prompt,
                    field_name=f"{field_name}[{i}]",
                    max_length=max_prompt_length,
                ))
            except ValidationError as e:
                errors.append(e)

        if errors:
            raise ValidationErrorCollection(errors)

        return validated

    def validate_model_resolution(
        self,
        model: str,
        resolution: str,
        model_field: str = "model",
        resolution_field: str = "resolution",
    ) -> tuple:
        """
        Validate that a resolution is supported by a model.

        Args:
            model: The model name
            resolution: The requested resolution
            model_field: Name of the model field for errors
            resolution_field: Name of the resolution field for errors

        Returns:
            Tuple of (model, resolution) validated

        Raises:
            ValidationError: If resolution not supported by model
        """
        valid_resolutions = self.MODEL_RESOLUTIONS.get(model)

        if valid_resolutions is None:
            raise ValidationError(
                field=model_field,
                message=f"Unknown model",
                value=model,
                code="unknown_model",
            )

        if resolution not in valid_resolutions:
            raise ValidationError(
                field=resolution_field,
                message=f"Resolution '{resolution}' not supported by {model}. Valid: {valid_resolutions}",
                value=resolution,
                code="invalid_resolution_for_model",
            )

        return model, resolution

    def validate_model_duration(
        self,
        model: str,
        duration_sec: int,
        model_field: str = "model",
        duration_field: str = "duration_sec",
    ) -> tuple:
        """
        Validate that a duration is supported by a model.

        Args:
            model: The model name
            duration_sec: The requested duration in seconds
            model_field: Name of the model field for errors
            duration_field: Name of the duration field for errors

        Returns:
            Tuple of (model, duration_sec) validated

        Raises:
            ValidationError: If duration not supported by model
        """
        valid_durations = self.MODEL_DURATIONS.get(model)

        if valid_durations is None:
            raise ValidationError(
                field=model_field,
                message="Unknown model",
                value=model,
                code="unknown_model",
            )

        if duration_sec not in valid_durations:
            raise ValidationError(
                field=duration_field,
                message=f"Duration {duration_sec}s not supported by {model}. Valid: {valid_durations}",
                value=duration_sec,
                code="invalid_duration_for_model",
            )

        return model, duration_sec

    def validate_file_size(
        self,
        size_bytes: int,
        field_name: str = "file",
        max_size_mb: Optional[float] = None,
    ) -> int:
        """
        Validate file size is within limits.

        Args:
            size_bytes: File size in bytes
            field_name: Name of the field for error messages
            max_size_mb: Maximum size in MB (default: 20)

        Returns:
            The file size in bytes

        Raises:
            ValidationError: If file exceeds size limit
        """
        max_mb = max_size_mb if max_size_mb is not None else self.DEFAULT_MAX_FILE_SIZE_MB
        max_bytes = int(max_mb * 1024 * 1024)

        if size_bytes > max_bytes:
            size_mb = size_bytes / (1024 * 1024)
            raise ValidationError(
                field=field_name,
                message=f"File size ({size_mb:.1f} MB) exceeds maximum ({max_mb} MB)",
                value=f"{size_mb:.1f} MB",
                code="file_too_large",
            )

        return size_bytes

    def validate_image_urls_list(
        self,
        urls: List[str],
        field_name: str = "image_urls",
        min_count: int = 1,
        max_count: int = 10,
    ) -> List[str]:
        """
        Validate a list of image URLs.

        Args:
            urls: List of URLs to validate
            field_name: Name of the field for error messages
            min_count: Minimum number of URLs
            max_count: Maximum number of URLs

        Returns:
            List of validated URLs

        Raises:
            ValidationErrorCollection: If any URLs are invalid
        """
        if not urls:
            raise ValidationError(
                field=field_name,
                message="At least one image URL is required",
                code="empty_collection",
            )

        if len(urls) < min_count:
            raise ValidationError(
                field=field_name,
                message=f"At least {min_count} image URL(s) required",
                code="too_few",
            )

        if len(urls) > max_count:
            raise ValidationError(
                field=field_name,
                message=f"Cannot exceed {max_count} image URLs",
                code="too_many",
            )

        validated = []
        errors = []

        for i, url in enumerate(urls):
            try:
                validated.append(self.validate_image_url(
                    url,
                    field_name=f"{field_name}[{i}]",
                ))
            except ValidationError as e:
                errors.append(e)

        if errors:
            raise ValidationErrorCollection(errors)

        return validated


# Singleton instance for convenience
input_validator = InputValidator()


# Convenience functions for common validations
def validate_job_input(
    image_url: str,
    motion_prompt: str,
    model: str,
    resolution: str,
    duration_sec: int,
    negative_prompt: Optional[str] = None,
) -> dict:
    """
    Validate job creation input at the service layer.

    This provides a second layer of validation after Pydantic router validation.

    Args:
        image_url: Source image URL
        motion_prompt: Motion description prompt
        model: Video model to use
        resolution: Output resolution
        duration_sec: Video duration in seconds
        negative_prompt: Optional negative prompt

    Returns:
        Dict of validated inputs

    Raises:
        ValidationError or ValidationErrorCollection: If validation fails
    """
    validator = input_validator

    validated_url = validator.validate_image_url(image_url, "image_url")
    validated_prompt = validator.validate_prompt(motion_prompt, "motion_prompt")
    validator.validate_model_resolution(model, resolution)
    validator.validate_model_duration(model, duration_sec)

    validated_negative = None
    if negative_prompt:
        validated_negative = validator.validate_prompt(
            negative_prompt,
            "negative_prompt",
            allow_empty=True,
        )

    return {
        "image_url": validated_url,
        "motion_prompt": validated_prompt,
        "model": model,
        "resolution": resolution,
        "duration_sec": duration_sec,
        "negative_prompt": validated_negative,
    }


def validate_bulk_pipeline_input(
    source_images: List[str],
    i2v_prompts: List[str],
    i2v_model: str,
    i2v_resolution: str,
    i2v_duration_sec: int,
    i2i_prompts: Optional[List[str]] = None,
) -> dict:
    """
    Validate bulk pipeline input at the service layer.

    Args:
        source_images: List of source image URLs
        i2v_prompts: List of motion prompts
        i2v_model: Video model to use
        i2v_resolution: Output resolution
        i2v_duration_sec: Video duration
        i2i_prompts: Optional list of I2I prompts

    Returns:
        Dict of validated inputs

    Raises:
        ValidationError or ValidationErrorCollection: If validation fails
    """
    validator = input_validator

    validated_images = validator.validate_image_urls_list(
        source_images,
        "source_images",
        max_count=10,
    )

    validated_i2v_prompts = validator.validate_prompts_list(
        i2v_prompts,
        "i2v_prompts",
        max_count=10,
    )

    validator.validate_model_resolution(i2v_model, i2v_resolution)
    validator.validate_model_duration(i2v_model, i2v_duration_sec)

    validated_i2i_prompts = None
    if i2i_prompts:
        validated_i2i_prompts = validator.validate_prompts_list(
            i2i_prompts,
            "i2i_prompts",
            max_count=10,
        )

    return {
        "source_images": validated_images,
        "i2v_prompts": validated_i2v_prompts,
        "i2v_model": i2v_model,
        "i2v_resolution": i2v_resolution,
        "i2v_duration_sec": i2v_duration_sec,
        "i2i_prompts": validated_i2i_prompts,
    }
