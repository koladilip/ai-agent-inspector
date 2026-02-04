"""
Configuration module for Agent Inspector.

Provides centralized configuration management with environment variable support,
presets, and sensible defaults.
"""

import json
import os
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class Profile(Enum):
    """Configuration presets for different environments."""

    PRODUCTION = "production"
    DEVELOPMENT = "development"
    DEBUG = "debug"


@dataclass
class TraceConfig:
    """
    Centralized configuration for Agent Inspector.

    Configuration is loaded in this priority order:
    1. Code defaults (defined here)
    2. Environment variables (TRACE_* prefixed)
    3. Runtime config object (when instantiated)
    4. Profile presets (if specified)
    """

    # Sampling Configuration
    sample_rate: float = 0.1
    """Fraction of runs to trace (0.0 to 1.0)."""

    only_on_error: bool = False
    """Only trace runs that encounter errors."""

    # Queue and Batch Processing
    queue_size: int = 1000
    """Maximum number of events in the in-memory queue."""

    batch_size: int = 50
    """Number of events to batch before processing."""

    batch_timeout_ms: int = 1000
    """Maximum time to wait before flushing batch (milliseconds)."""

    block_on_run_end: bool = False
    """If True, block (up to run_end_block_timeout_ms) when queueing run_end so it is not dropped under backpressure."""

    run_end_block_timeout_ms: int = 5000
    """Max time to block when queueing run_end when block_on_run_end is True (milliseconds)."""

    # Redaction Configuration
    redact_keys: List[str] = field(
        default_factory=lambda: [
            "password",
            "api_key",
            "token",
            "secret",
            "credential",
            "access_key",
            "private_key",
            "auth_token",
            "session_token",
            "authorization",
            "bearer",
        ]
    )
    """Keys to redact from event data (case-insensitive)."""

    redact_patterns: List[str] = field(
        default_factory=lambda: [
            r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
            r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",  # Credit card
            r"\b[A-Za-z0-9]{32,}\b",  # Likely tokens/keys
            r"Bearer\s+[A-Za-z0-9\-._~+/]+=*",  # Bearer tokens
            r"Authorization:\s*[A-Za-z0-9\-._~+/]+",  # Authorization headers
        ]
    )
    """Regex patterns to redact from event data."""

    # Encryption Configuration
    encryption_enabled: bool = False
    """Enable encryption at rest using Fernet."""

    encryption_key: Optional[str] = None
    """Fernet encryption key (32 bytes, base64-encoded)."""

    # Storage Configuration
    db_path: str = "agent_inspector.db"
    """Path to SQLite database file."""

    retention_days: int = 30
    """Number of days to retain trace data before pruning."""

    # API Configuration
    api_host: str = "127.0.0.1"
    """Host for API server."""

    api_port: int = 8000
    """Port for API server."""

    api_enabled: bool = True
    """Whether to start the API server."""

    api_key_required: bool = False
    """Require API key for authentication."""

    api_key: Optional[str] = None
    """API key for authentication."""

    api_cors_origins: List[str] = field(default_factory=lambda: ["*"])
    """Allowed CORS origins for API server. Defaults to all origins."""

    # UI Configuration
    ui_enabled: bool = True
    """Whether to serve the web UI."""

    ui_path: str = "/ui"
    """URL path for UI."""

    # Performance Configuration
    compression_enabled: bool = True
    """Enable gzip compression before storage."""

    compression_level: int = 6
    """Gzip compression level (1-9, higher = more compression, slower)."""

    # Logging Configuration
    log_level: str = "INFO"
    """Logging level (DEBUG, INFO, WARNING, ERROR)."""

    log_path: Optional[str] = None
    """Path to log file. If None, logs to stdout."""

    def __post_init__(self):
        """Post-initialization to validate and normalize config."""
        self._validate()
        self._apply_profile()
        self._load_from_env()
        self._validate()

    def _validate(self):
        """Validate configuration values."""
        # Validate sample_rate
        if not 0.0 <= self.sample_rate <= 1.0:
            raise ValueError(
                f"sample_rate must be between 0.0 and 1.0, got {self.sample_rate}"
            )

        # Validate queue_size
        if self.queue_size <= 0:
            raise ValueError(f"queue_size must be positive, got {self.queue_size}")

        # Validate batch_size
        if self.batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {self.batch_size}")

        # Validate compression_level
        if not 1 <= self.compression_level <= 9:
            raise ValueError(
                f"compression_level must be between 1 and 9, got {self.compression_level}"
            )

        # Validate log_level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if self.log_level not in valid_levels:
            raise ValueError(
                f"log_level must be one of {valid_levels}, got {self.log_level}"
            )

        # Validate encryption
        if self.encryption_enabled and not self.encryption_key:
            self.encryption_key = os.getenv("TRACE_ENCRYPTION_KEY")
            if not self.encryption_key:
                raise ValueError(
                    "encryption_key is required when encryption_enabled=True"
                )

        # Validate API key
        if self.api_key_required and not self.api_key:
            self.api_key = os.getenv("TRACE_API_KEY")
            if not self.api_key:
                raise ValueError("api_key is required when api_key_required=True")

    def _apply_profile(self):
        """Apply profile preset if specified via environment."""
        profile_str = os.getenv("TRACE_PROFILE")
        if profile_str:
            try:
                profile = Profile(profile_str.lower())
                self._apply_preset(profile)
            except ValueError:
                raise ValueError(f"Invalid TRACE_PROFILE: {profile_str}")

    def _apply_preset(self, profile: Profile):
        """Apply preset configuration for the given profile."""
        if profile == Profile.PRODUCTION:
            # Production: minimal overhead, secure, efficient
            self.sample_rate = 0.01
            self.queue_size = 1000
            self.batch_size = 100
            self.compression_enabled = True
            self.compression_level = 6
            # Only enable encryption if a key is available
            self.encryption_key = self.encryption_key or os.getenv(
                "TRACE_ENCRYPTION_KEY"
            )
            self.encryption_enabled = bool(self.encryption_key)
            self.log_level = "WARNING"

        elif profile == Profile.DEVELOPMENT:
            # Development: moderate tracing, no encryption
            self.sample_rate = 0.5
            self.queue_size = 1000
            self.batch_size = 50
            self.compression_enabled = True
            self.compression_level = 3
            self.encryption_enabled = False
            self.log_level = "INFO"

        elif profile == Profile.DEBUG:
            # Debug: full tracing, detailed logging
            self.sample_rate = 1.0
            self.queue_size = 2000
            self.batch_size = 10
            self.compression_enabled = False
            self.encryption_enabled = False
            self.log_level = "DEBUG"

    def _load_from_env(self):
        """Load configuration from environment variables."""
        env_mapping = {
            "TRACE_SAMPLE_RATE": ("sample_rate", float),
            "TRACE_ONLY_ON_ERROR": (
                "only_on_error",
                lambda v: v.lower() in ("true", "1", "yes"),
            ),
            "TRACE_QUEUE_SIZE": ("queue_size", int),
            "TRACE_BATCH_SIZE": ("batch_size", int),
            "TRACE_BATCH_TIMEOUT": ("batch_timeout_ms", int),
            "TRACE_BLOCK_ON_RUN_END": (
                "block_on_run_end",
                lambda v: v.lower() in ("true", "1", "yes"),
            ),
            "TRACE_RUN_END_BLOCK_TIMEOUT": ("run_end_block_timeout_ms", int),
            "TRACE_ENCRYPTION_ENABLED": (
                "encryption_enabled",
                lambda v: v.lower() in ("true", "1", "yes"),
            ),
            "TRACE_ENCRYPTION_KEY": ("encryption_key", str),
            "TRACE_DB_PATH": ("db_path", str),
            "TRACE_RETENTION_DAYS": ("retention_days", int),
            "TRACE_API_HOST": ("api_host", str),
            "TRACE_API_PORT": ("api_port", int),
            "TRACE_API_ENABLED": (
                "api_enabled",
                lambda v: v.lower() in ("true", "1", "yes"),
            ),
            "TRACE_API_KEY_REQUIRED": (
                "api_key_required",
                lambda v: v.lower() in ("true", "1", "yes"),
            ),
            "TRACE_API_KEY": ("api_key", str),
            "TRACE_API_CORS_ORIGINS": ("api_cors_origins", self._parse_list),
            "TRACE_UI_ENABLED": (
                "ui_enabled",
                lambda v: v.lower() in ("true", "1", "yes"),
            ),
            "TRACE_UI_PATH": ("ui_path", str),
            "TRACE_COMPRESSION_ENABLED": (
                "compression_enabled",
                lambda v: v.lower() in ("true", "1", "yes"),
            ),
            "TRACE_COMPRESSION_LEVEL": ("compression_level", int),
            "TRACE_LOG_LEVEL": ("log_level", str.upper),
            "TRACE_LOG_PATH": ("log_path", str),
            "TRACE_REDACT_KEYS": ("redact_keys", self._parse_list),
            "TRACE_REDACT_PATTERNS": ("redact_patterns", self._parse_list),
        }

        for env_var, (attr_name, parser) in env_mapping.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    parsed_value = parser(value)
                    setattr(self, attr_name, parsed_value)
                except (ValueError, AttributeError) as e:
                    raise ValueError(f"Invalid {env_var}: {value} - {e}")

    def _parse_list(self, value: str) -> List[str]:
        """Parse comma-separated list from environment variable."""
        return [item.strip() for item in value.split(",") if item.strip()]

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert configuration to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "TraceConfig":
        """Create TraceConfig from dictionary."""
        return cls(**config_dict)

    @classmethod
    def from_json(cls, json_str: str) -> "TraceConfig":
        """Create TraceConfig from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def production(cls) -> "TraceConfig":
        """Get production preset configuration."""
        config = cls()
        config._apply_preset(Profile.PRODUCTION)
        return config

    @classmethod
    def development(cls) -> "TraceConfig":
        """Get development preset configuration."""
        config = cls()
        config._apply_preset(Profile.DEVELOPMENT)
        return config

    @classmethod
    def debug(cls) -> "TraceConfig":
        """Get debug preset configuration."""
        config = cls()
        config._apply_preset(Profile.DEBUG)
        return config

    def get_redaction_keys_set(self) -> Set[str]:
        """Get redaction keys as a set for fast lookup (lowercased)."""
        return set(key.lower() for key in self.redact_keys)

    def get_redaction_patterns_compiled(self) -> List[re.Pattern]:
        """Get compiled regex patterns for redaction."""
        try:
            return [re.compile(pattern) for pattern in self.redact_patterns]
        except re.error as e:
            raise ValueError(f"Invalid redaction pattern: {e}")

    def add_redaction_key(self, key: str):
        """Add a redaction key to the configuration.

        Args:
            key: The key to redact (case-insensitive).
        """
        if key not in self.redact_keys:
            self.redact_keys.append(key)

    def add_redaction_pattern(self, pattern: str):
        """Add a redaction pattern to the configuration.

        Args:
            pattern: Regex pattern to match for redaction.
        """
        if pattern not in self.redact_patterns:
            self.redact_patterns.append(pattern)


# Global configuration instance (can be overridden)
_global_config: Optional[TraceConfig] = None


def get_config() -> TraceConfig:
    """
    Get the global configuration instance.

    Creates a default configuration if none has been set.

    Returns:
        TraceConfig: The global configuration instance.
    """
    global _global_config
    if _global_config is None:
        _global_config = TraceConfig()
    return _global_config


def set_config(config: TraceConfig):
    """
    Set the global configuration instance.

    Args:
        config: The TraceConfig instance to use globally.
    """
    global _global_config
    _global_config = config
