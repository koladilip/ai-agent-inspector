"""
Tests for Agent Inspector configuration module.

Tests configuration management including:
- Default configuration
- Environment variable overrides
- Profile presets (production/development/debug)
- Configuration validation
- Redaction rules
- Serialization and deserialization
"""

import os
import tempfile
from unittest.mock import patch

import pytest

from agent_inspector.core.config import (
    Profile,
    TraceConfig,
    get_config,
    set_config,
)


class TestDefaultConfiguration:
    """Test default TraceConfig values."""

    def test_default_config(self):
        """Test creating default configuration."""
        config = TraceConfig()

        # Sampling defaults
        assert 0.0 <= config.sample_rate <= 1.0
        assert config.sample_rate == 0.1

        # Queue and batch defaults
        assert config.queue_size == 1000
        assert config.batch_size == 50
        assert config.batch_timeout_ms == 1000

        # Redaction defaults
        assert len(config.redact_keys) > 0
        assert "password" in config.redact_keys
        assert "api_key" in config.redact_keys
        assert len(config.redact_patterns) > 0

        # Encryption defaults
        assert config.encryption_enabled is False
        assert config.encryption_key is None

        # Storage defaults
        assert config.db_path == "agent_inspector.db"
        assert config.retention_days == 30
        assert config.retention_max_bytes is None

        # API defaults
        assert config.api_host == "127.0.0.1"
        assert config.api_port == 8000
        assert config.api_enabled is True
        assert config.api_key_required is False

        # UI defaults
        assert config.ui_enabled is True
        assert config.ui_path == "/ui"

        # Processing defaults
        assert config.compression_enabled is True
        assert config.compression_level == 6

        # Logging defaults
        assert config.log_level == "INFO"
        assert config.log_path is None


def test_get_set_config():
    """Test global config getters/setters."""
    from agent_inspector.core.config import get_config, set_config

    cfg = TraceConfig(sample_rate=0.2)
    set_config(cfg)
    assert get_config() is cfg


def test_profile_env_invalid_raises():
    """Invalid TRACE_PROFILE should raise a ValueError."""
    with patch.dict(os.environ, {"TRACE_PROFILE": "invalid"}, clear=True):
        with pytest.raises(ValueError):
            TraceConfig()


def test_redaction_pattern_invalid_raises():
    """Invalid redaction pattern should raise."""
    from agent_inspector.processing.pipeline import Redactor

    with pytest.raises(ValueError):
        Redactor(TraceConfig(redact_patterns=["[invalid("]))


class TestProfilePresets:
    """Test configuration profile presets."""

    def test_production_profile(self):
        """Test production profile configuration."""
        # Set test encryption key for production profile
        env_vars = {"TRACE_ENCRYPTION_KEY": "test_key_32_bytes_long_1234567890"}
        with patch.dict(os.environ, env_vars, clear=True):
            config = TraceConfig.production()

            # Production should have low sampling
            assert config.sample_rate == 0.01
            assert config.compression_enabled is True
            assert config.compression_level == 6
            assert config.encryption_enabled is True
            assert config.log_level == "WARNING"

    def test_development_profile(self):
        """Test development profile configuration."""
        config = TraceConfig.development()

        # Development should have moderate sampling
        assert config.sample_rate == 0.5
        assert config.compression_enabled is True
        assert config.compression_level == 3
        assert config.encryption_enabled is False
        assert config.log_level == "INFO"

    def test_debug_profile(self):
        """Test debug profile configuration."""
        config = TraceConfig.debug()

        # Debug should sample everything
        assert config.sample_rate == 1.0
        assert config.compression_enabled is False
        assert config.encryption_enabled is False
        assert config.log_level == "DEBUG"
        assert config.queue_size == 2000
        assert config.batch_size == 10


class TestConfigurationValidation:
    """Test configuration validation."""

    def test_valid_sample_rate(self):
        """Test that valid sample rates are accepted."""
        config = TraceConfig(sample_rate=0.5)
        assert config.sample_rate == 0.5

        config = TraceConfig(sample_rate=0.0)
        assert config.sample_rate == 0.0

        config = TraceConfig(sample_rate=1.0)
        assert config.sample_rate == 1.0

    def test_invalid_sample_rate_high(self):
        """Test that sample_rate > 1.0 raises error."""
        with pytest.raises(ValueError, match="sample_rate must be between"):
            TraceConfig(sample_rate=1.5)

    def test_invalid_sample_rate_low(self):
        """Test that sample_rate < 0.0 raises error."""
        with pytest.raises(ValueError, match="sample_rate must be between"):
            TraceConfig(sample_rate=-0.1)

    def test_invalid_queue_size_zero(self):
        """Test that queue_size=0 raises error."""
        with pytest.raises(ValueError, match="queue_size must be positive"):
            TraceConfig(queue_size=0)

    def test_invalid_queue_size_negative(self):
        """Test that negative queue_size raises error."""
        with pytest.raises(ValueError, match="queue_size must be positive"):
            TraceConfig(queue_size=-100)

    def test_valid_queue_size(self):
        """Test that valid queue sizes are accepted."""
        config = TraceConfig(queue_size=500)
        assert config.queue_size == 500

        config = TraceConfig(queue_size=10000)
        assert config.queue_size == 10000

    def test_invalid_compression_level_low(self):
        """Test that compression_level < 1 raises error."""
        with pytest.raises(ValueError, match="compression_level must be between"):
            TraceConfig(compression_level=0)

    def test_invalid_compression_level_high(self):
        """Test that compression_level > 9 raises error."""
        with pytest.raises(ValueError, match="compression_level must be between"):
            TraceConfig(compression_level=10)

    def test_valid_compression_level(self):
        """Test that valid compression levels are accepted."""
        config = TraceConfig(compression_level=1)
        assert config.compression_level == 1

        config = TraceConfig(compression_level=9)
        assert config.compression_level == 9

    def test_invalid_log_level(self):
        """Test that invalid log level raises error."""
        with pytest.raises(ValueError, match="log_level must be one of"):
            TraceConfig(log_level="INVALID")

    def test_valid_log_levels(self):
        """Test that valid log levels are accepted."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            config = TraceConfig(log_level=level)
            assert config.log_level == level

    def test_encryption_enabled_without_key(self):
        """Test that encryption_enabled=True without key raises error."""
        # Remove any existing encryption key
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="encryption_key is required"):
                TraceConfig(encryption_enabled=True)

    def test_encryption_with_key(self):
        """Test that encryption with key is accepted."""
        config = TraceConfig(encryption_enabled=True, encryption_key="test_key_123")
        assert config.encryption_enabled is True
        assert config.encryption_key == "test_key_123"

    def test_api_key_required_with_env(self):
        """Test that api_key is loaded from env when required."""
        with patch.dict(os.environ, {"TRACE_API_KEY": "from-env"}, clear=True):
            config = TraceConfig(api_key_required=True)
            assert config.api_key == "from-env"


class TestEnvironmentVariables:
    """Test configuration from environment variables."""

    def test_sample_rate_from_env(self):
        """Test loading sample_rate from environment."""
        env_vars = {"TRACE_SAMPLE_RATE": "0.75"}
        with patch.dict(os.environ, env_vars, clear=True):
            config = TraceConfig()
            assert config.sample_rate == 0.75

    def test_queue_size_from_env(self):
        """Test loading queue_size from environment."""
        env_vars = {"TRACE_QUEUE_SIZE": "500"}
        with patch.dict(os.environ, env_vars, clear=True):
            config = TraceConfig()
            assert config.queue_size == 500

    def test_encryption_from_env(self):
        """Test loading encryption settings from environment."""
        env_vars = {
            "TRACE_ENCRYPTION_ENABLED": "true",
            "TRACE_ENCRYPTION_KEY": "test_secret_key",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = TraceConfig()
            assert config.encryption_enabled is True
            assert config.encryption_key == "test_secret_key"

    def test_redact_keys_from_env(self):
        """Test loading redact_keys from environment."""
        env_vars = {"TRACE_REDACT_KEYS": "password,secret,token"}
        with patch.dict(os.environ, env_vars, clear=True):
            config = TraceConfig()
            assert "password" in config.redact_keys
            assert "secret" in config.redact_keys
            assert "token" in config.redact_keys

    def test_redact_patterns_from_env(self):
        """Test loading redact_patterns from environment."""
        pattern = r"\b\d{3}-\d{2}-\d{4}\b"
        env_vars = {"TRACE_REDACT_PATTERNS": pattern}
        with patch.dict(os.environ, env_vars, pattern):
            config = TraceConfig()
            assert len(config.redact_patterns) >= 1

    def test_profile_from_env(self):
        """Test applying profile from environment."""
        env_vars = {"TRACE_PROFILE": "production"}
        with patch.dict(os.environ, env_vars, clear=True):
            config = TraceConfig()
            assert config.sample_rate == 0.01  # Production default
            assert config.log_level == "WARNING"

    def test_env_overrides_default(self):
        """Test that env vars override defaults."""
        env_vars = {
            "TRACE_SAMPLE_RATE": "0.5",
            "TRACE_QUEUE_SIZE": "2000",
            "TRACE_LOG_LEVEL": "DEBUG",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = TraceConfig()
            assert config.sample_rate == 0.5
            assert config.queue_size == 2000
            assert config.log_level == "DEBUG"

    def test_retention_max_bytes_from_env(self):
        """Test loading retention_max_bytes from environment."""
        env_vars = {"TRACE_RETENTION_MAX_BYTES": "5000000"}
        with patch.dict(os.environ, env_vars, clear=True):
            config = TraceConfig()
            assert config.retention_max_bytes == 5000000

    def test_retention_max_bytes_empty_env_is_none(self):
        """Test that empty or zero TRACE_RETENTION_MAX_BYTES yields None."""
        env_vars = {"TRACE_RETENTION_MAX_BYTES": ""}
        with patch.dict(os.environ, env_vars, clear=True):
            config = TraceConfig()
            assert config.retention_max_bytes is None

    def test_retention_max_bytes_zero_env_is_none(self):
        """Test that TRACE_RETENTION_MAX_BYTES=0 yields None."""
        env_vars = {"TRACE_RETENTION_MAX_BYTES": "0"}
        with patch.dict(os.environ, env_vars, clear=True):
            config = TraceConfig()
            assert config.retention_max_bytes is None


class TestRedactionRules:
    """Test redaction configuration."""

    def test_get_redaction_keys_set(self):
        """Test getting redaction keys as normalized set."""
        config = TraceConfig(redact_keys=["PASSWORD", "API_KEY", "token", "Secret"])

        keys_set = config.get_redaction_keys_set()
        assert len(keys_set) == 4
        assert "password" in keys_set
        assert "api_key" in keys_set
        assert "token" in keys_set
        assert "secret" in keys_set

    def test_add_redaction_key(self):
        """Test adding a redaction key."""
        config = TraceConfig(redact_keys=["password"])
        config.add_redaction_key("api_key")

        keys_set = config.get_redaction_keys_set()
        assert "password" in keys_set
        assert "api_key" in keys_set

    def test_get_redaction_patterns_compiled(self):
        """Test getting compiled redaction patterns."""
        config = TraceConfig(redact_patterns=[r"\b\d{3}-\d{2}-\d{4}\b"])

        patterns = config.get_redaction_patterns_compiled()
        assert len(patterns) == 1
        assert hasattr(patterns[0], "match")  # Compiled regex

    def test_add_redaction_pattern(self):
        """Test adding a redaction pattern."""
        config = TraceConfig(redact_patterns=[])
        pattern = r"\b[A-Za-z0-9]{32,}\b"

        config.add_redaction_pattern(pattern)
        patterns = config.get_redaction_patterns_compiled()
        assert len(patterns) == 1


class TestSerialization:
    """Test configuration serialization and deserialization."""

    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = TraceConfig(sample_rate=0.5, queue_size=500, compression_enabled=False)

        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict["sample_rate"] == 0.5
        assert config_dict["queue_size"] == 500
        assert config_dict["compression_enabled"] is False

    def test_to_json(self):
        """Test converting config to JSON."""
        config = TraceConfig(sample_rate=0.75)

        config_json = config.to_json()
        assert isinstance(config_json, str)
        assert "0.75" in config_json
        assert "sample_rate" in config_json

    def test_from_dict(self):
        """Test creating config from dictionary."""
        config_dict = {
            "sample_rate": 0.3,
            "queue_size": 2000,
        }

        config = TraceConfig.from_dict(config_dict)

        assert config.sample_rate == 0.3
        assert config.queue_size == 2000

    def test_from_json(self):
        """Test creating config from JSON."""
        config_json = """
        {
            "sample_rate": 0.25,
            "compression_level": 9,
            "log_level": "DEBUG"
        }
        """

        config = TraceConfig.from_json(config_json)

        assert config.sample_rate == 0.25
        assert config.compression_level == 9
        assert config.log_level == "DEBUG"


class TestGlobalConfig:
    """Test global configuration instance."""

    def test_get_config_creates_instance(self):
        """Test that get_config() creates instance."""
        # Clear any existing global config
        from agent_inspector.core import config as config_module

        config_module._global_config = None

        config1 = get_config()
        config2 = get_config()

        # Should be same instance
        assert config1 is config2

    def test_set_config(self):
        """Test setting global configuration."""
        new_config = TraceConfig(sample_rate=1.0)
        set_config(new_config)

        # Should get the config we just set
        retrieved_config = get_config()
        assert retrieved_config.sample_rate == 1.0


class TestProfileEnum:
    """Test Profile enumeration."""

    def test_profile_values(self):
        """Test that all profile values exist."""
        assert Profile.PRODUCTION.value == "production"
        assert Profile.DEVELOPMENT.value == "development"
        assert Profile.DEBUG.value == "debug"

    def test_profile_from_string(self):
        """Test creating Profile from string."""
        prod = Profile("production")
        dev = Profile("development")
        debug = Profile("debug")

        assert prod == Profile.PRODUCTION
        assert dev == Profile.DEVELOPMENT
        assert debug == Profile.DEBUG

    def test_invalid_profile_string(self):
        """Test that invalid profile string raises error."""
        with pytest.raises(ValueError):
            Profile("invalid")
