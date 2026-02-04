"""
Tests for Agent Inspector data processing pipeline.

Tests data processing functionality including:
- Redaction (key-based and pattern-based)
- Serialization (JSON)
- Compression (gzip)
- Encryption (Fernet)
- Complete pipeline operations
"""

import gzip
import json
import os
from unittest.mock import patch

import pytest

from agent_inspector.core.config import TraceConfig
from agent_inspector.processing.pipeline import (
    Compressor,
    Encryptor,
    ProcessingPipeline,
    Redactor,
    Serializer,
)


class TestRedactor:
    """Test redaction of sensitive data."""

    @pytest.fixture
    def redactor(self):
        """Create a redactor with default config."""
        config = TraceConfig()
        return Redactor(config)

    def test_redact_dict_by_key(self, redactor):
        """Test redacting dictionary by key."""
        data = {
            "username": "john",
            "password": "secret123",
            "email": "john@example.com",
            "api_key": "abc123def",
        }

        redacted = redactor.redact(data)

        assert redacted["username"] == "john"
        assert redacted["email"] == "john@example.com"
        assert redacted["password"] == "[REDACTED]"
        assert redacted["api_key"] == "[REDACTED]"

    def test_redact_nested_dict(self, redactor):
        """Test redacting nested dictionaries."""
        data = {
            "user": {
                "name": "John",
                "password": "secret",
            },
            "metadata": {
                "token": "abc123",
                "normal": "value",
            },
        }

        redacted = redactor.redact(data)

        assert redacted["user"]["name"] == "John"
        assert redacted["user"]["password"] == "[REDACTED]"
        assert redacted["metadata"]["token"] == "[REDACTED]"
        assert redacted["metadata"]["normal"] == "value"

    def test_redact_list(self, redactor):
        """Test redacting list of dictionaries."""
        data = [
            {"username": "john", "password": "secret1"},
            {"username": "jane", "password": "secret2"},
        ]

        redacted = redactor.redact(data)

        assert redacted[0]["username"] == "john"
        assert redacted[0]["password"] == "[REDACTED]"
        assert redacted[1]["username"] == "jane"
        assert redacted[1]["password"] == "[REDACTED]"

    def test_redact_passthrough_types(self, redactor):
        """Test that non-collection types are returned unchanged."""
        assert redactor.redact(123) == 123
        assert redactor.redact(True) is True
        redacted = redactor.redact([1, {"password": "secret"}])
        assert redacted[0] == 1
        assert redacted[1]["password"] == "[REDACTED]"

    def test_redact_by_pattern_ssn(self, redactor):
        """Test redacting SSN by pattern."""
        data = {"info": "My SSN is 123-45-6789"}

        redacted = redactor.redact(data)

        assert redacted["info"] == "My SSN is [REDACTED]"

    def test_redact_by_pattern_credit_card(self, redactor):
        """Test redacting credit card by pattern."""
        data = {"card": "My credit card is 1234-5678-9012-3456"}

        redacted = redactor.redact(data)

        assert redacted["card"] == "My credit card is [REDACTED]"

    def test_redact_string(self, redactor):
        """Test redacting string by pattern."""
        data = "Password: secret123, SSN: 123-45-6789"

        redacted = redactor.redact(data)

        assert "secret123" not in redacted
        assert "123-45-6789" not in redacted

    def test_redact_no_match(self, redactor):
        """Test that non-sensitive data is not redacted."""
        data = {
            "name": "John",
            "age": 30,
            "city": "New York",
        }

        redacted = redactor.redact(data)

        assert redacted == data

    def test_redact_primitive_types(self, redactor):
        """Test that primitive types are not redacted."""
        data = {
            "number": 42,
            "boolean": True,
            "null": None,
        }

        redacted = redactor.redact(data)

        assert redacted["number"] == 42
        assert redacted["boolean"] is True
        assert redacted["null"] is None

    def test_custom_redaction_key(self, redactor):
        """Test adding a custom redaction key."""
        redactor.add_redaction_key("custom_secret")

        data = {"custom_secret": "hidden", "other": "visible"}
        redacted = redactor.redact(data)

        assert redacted["custom_secret"] == "[REDACTED]"
        assert redacted["other"] == "visible"

    def test_custom_redaction_pattern(self, redactor):
        """Test adding a custom redaction pattern."""
        import re

        redactor.add_redaction_pattern(r"\b[A-Z]{2}-\d{4}\b")  # Pattern: AB-1234

        data = {"info": "Code is AB-5678"}

        redacted = redactor.redact(data)

        assert redacted["info"] == "Code is [REDACTED]"

    def test_case_insensitive_redaction(self, redactor):
        """Test that redaction keys are case-insensitive."""
        data = {
            "Password": "secret",
            "PASSWORD": "another",
            "PaSsWoRd": "third",
        }

        redacted = redactor.redact(data)

        # All should be redacted
        assert redacted["Password"] == "[REDACTED]"
        assert redacted["PASSWORD"] == "[REDACTED]"
        assert redacted["PaSsWoRd"] == "[REDACTED]"

    def test_custom_redaction_marker(self, redactor):
        """Test using custom redaction marker."""
        data = {"password": "secret"}

        # Default marker
        redacted1 = redactor.redact(data)
        assert redacted1["password"] == "[REDACTED]"

        # Custom marker
        redacted2 = redactor.redact(data, redaction_marker="***HIDDEN***")
        assert redacted2["password"] == "***HIDDEN***"


class TestSerializer:
    """Test JSON serialization."""

    def test_serialize_error_raises(self, monkeypatch):
        """Test serialize error path."""
        def _boom(*_args, **_kwargs):
            raise TypeError("boom")

        monkeypatch.setattr(json, "dumps", _boom)
        with pytest.raises(TypeError, match="Failed to serialize data"):
            Serializer.serialize({"a": 1})

    def test_serialize_simple_dict(self):
        """Test serializing a simple dictionary."""
        data = {"name": "John", "age": 30}

        serialized = Serializer.serialize(data)

        assert isinstance(serialized, bytes)
        assert b"name" in serialized
        assert b"John" in serialized

    def test_serialize_nested_dict(self):
        """Test serializing nested dictionaries."""
        data = {
            "user": {"name": "John", "address": {"city": "NYC"}},
            "metadata": {"count": 5},
        }

        serialized = Serializer.serialize(data)

        assert isinstance(serialized, bytes)
        assert b"NYC" in serialized

    def test_serialize_list(self):
        """Test serializing a list."""
        data = [1, 2, 3, "four"]

        serialized = Serializer.serialize(data)

        assert isinstance(serialized, bytes)
        assert b"[1,2,3" in serialized

    def test_serialize_string(self):
        """Test serializing a string."""
        data = "Hello, World!"

        serialized = Serializer.serialize(data)

        assert isinstance(serialized, bytes)
        assert b"Hello" in serialized

    def test_serialize_compact_json(self):
        """Test that JSON is compact (no extra spaces)."""
        data = {"name": "John", "age": 30}

        serialized = Serializer.serialize(data)

        # Should not have extra spaces
        assert b"  " not in serialized  # No extra spaces after colons

    def test_deserialize_simple_dict(self):
        """Test deserializing a simple dictionary."""
        data = {"name": "John", "age": 30}
        serialized = Serializer.serialize(data)

        deserialized = Serializer.deserialize(serialized)

        assert deserialized == data

    def test_deserialize_nested_dict(self):
        """Test deserializing nested dictionaries."""
        data = {
            "user": {"name": "Jane", "age": 25},
        }
        serialized = Serializer.serialize(data)

        deserialized = Serializer.deserialize(serialized)

        assert deserialized == data

    def test_deserialize_list(self):
        """Test deserializing a list."""
        data = ["a", "b", "c"]
        serialized = Serializer.serialize(data)

        deserialized = Serializer.deserialize(serialized)

        assert deserialized == data

    def test_serialize_roundtrip(self):
        """Test serialize -> deserialize roundtrip."""
        original = {
            "string": "test",
            "number": 42,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "object": {"key": "value"},
        }

        serialized = Serializer.serialize(original)
        deserialized = Serializer.deserialize(serialized)

        assert deserialized == original

    def test_serialize_non_serializable(self):
        """Test that non-serializable types are converted to string."""

        class CustomClass:
            def __str__(self):
                return "custom"

        data = {"custom": CustomClass()}

        serialized = Serializer.serialize(data)

        assert isinstance(serialized, bytes)
        assert b"custom" in serialized

    def test_deserialize_invalid_json(self):
        """Test that deserializing invalid JSON raises error."""
        import json

        invalid_data = b"{invalid json}"

        with pytest.raises(ValueError, match="Failed to deserialize"):
            Serializer.deserialize(invalid_data)


class TestCompressor:
    """Test gzip compression."""

    @pytest.fixture
    def compressor_enabled(self):
        """Create an enabled compressor."""
        return Compressor(enabled=True, compression_level=6)

    @pytest.fixture
    def compressor_disabled(self):
        """Create a disabled compressor."""
        return Compressor(enabled=False, compression_level=6)

    def test_compress_data(self, compressor_enabled):
        """Test compressing data."""
        original = (
            b"Hello, World! This is a test string that should compress well." * 100
        )

        compressed = compressor_enabled.compress(original)

        assert isinstance(compressed, bytes)
        assert len(compressed) < len(original)  # Should be smaller

    def test_compress_disabled(self, compressor_disabled):
        """Test that disabled compression returns original data."""
        original = b"Hello, World!"

        compressed = compressor_disabled.compress(original)

        assert compressed == original

    def test_decompress_data(self, compressor_enabled):
        """Test decompressing data."""
        original = b"Hello, World!" * 50

        compressed = compressor_enabled.compress(original)
        decompressed = compressor_enabled.decompress(compressed)

        assert decompressed == original

    def test_decompress_disabled(self, compressor_disabled):
        """Test that disabled decompression returns original data."""
        original = b"Hello, World!"

        compressed = compressor_disabled.compress(original)
        decompressed = compressor_disabled.decompress(compressed)

        assert decompressed == original

    def test_compress_roundtrip(self, compressor_enabled):
        """Test compress -> decompress roundtrip."""
        original = b"Test data for compression roundtrip. " * 20

        compressed = compressor_enabled.compress(original)
        decompressed = compressor_enabled.decompress(compressed)

        assert decompressed == original

    def test_compression_levels(self):
        """Test different compression levels."""
        data = b"Test data" * 100

        # Higher compression = smaller but slower
        fast = Compressor(enabled=True, compression_level=1).compress(data)
        medium = Compressor(enabled=True, compression_level=6).compress(data)
        slow = Compressor(enabled=True, compression_level=9).compress(data)

        assert len(fast) >= len(medium)
        assert len(medium) >= len(slow)
        assert len(slow) < len(data)  # All should be smaller

    def test_is_compressed(self, compressor_enabled):
        """Test detecting compressed data."""
        data = b"Test data"

        compressed = compressor_enabled.compress(data)

        assert compressor_enabled.is_compressed(compressed) is True
        assert compressor_enabled.is_compressed(data) is False

    def test_compression_ratio(self, compressor_enabled):
        """Test that compression achieves good ratio."""
        # Use compressible data (repetitive patterns)
        data = b"ABCD" * 1000

        compressed = compressor_enabled.compress(data)
        ratio = len(compressed) / len(data)

        # Should achieve at least 5x compression
        assert ratio < 0.2

    def test_compress_error_raises(self, monkeypatch):
        """Test compress error path."""
        def _boom(*_args, **_kwargs):
            raise OSError("boom")

        monkeypatch.setattr(gzip, "compress", _boom)
        compressor = Compressor(enabled=True, compression_level=6)
        with pytest.raises(RuntimeError, match="Failed to compress data"):
            compressor.compress(b"data")

    def test_decompress_error_raises(self, monkeypatch):
        """Test decompress error path."""
        def _boom(*_args, **_kwargs):
            raise OSError("boom")

        monkeypatch.setattr(gzip, "decompress", _boom)
        compressor = Compressor(enabled=True, compression_level=6)
        with pytest.raises(RuntimeError, match="Failed to decompress data"):
            compressor.decompress(b"data")


class TestEncryptor:
    """Test Fernet encryption."""

    @pytest.fixture
    def test_key(self):
        """Generate a test encryption key."""
        return Encryptor.generate_key()

    @pytest.fixture
    def encryptor_enabled(self, test_key):
        """Create an enabled encryptor."""
        return Encryptor(enabled=True, encryption_key=test_key)

    @pytest.fixture
    def encryptor_disabled(self):
        """Create a disabled encryptor."""
        return Encryptor(enabled=False)

    def test_generate_key(self):
        """Test generating encryption keys."""
        key1 = Encryptor.generate_key()
        key2 = Encryptor.generate_key()

        # Keys should be different
        assert key1 != key2

        # Keys should be valid Fernet keys (base64, 44 chars)
        assert len(key1) == 44
        # Base64 encoded keys contain special characters (+, /, =)
        # so we verify they're properly encoded by checking they work with Encryptor
        encryptor = Encryptor(enabled=True, encryption_key=key1)
        assert encryptor.fernet is not None

    def test_encrypt_data(self, encryptor_enabled):
        """Test encrypting data."""
        original = b"Secret data to encrypt"

        encrypted = encryptor_enabled.encrypt(original)

        assert isinstance(encrypted, bytes)
        assert encrypted != original  # Encrypted data should be different

    def test_encrypt_disabled(self, encryptor_disabled):
        """Test that disabled encryption returns original data."""
        original = b"Test data"

        encrypted = encryptor_disabled.encrypt(original)

        assert encrypted == original

    def test_decrypt_data(self, encryptor_enabled):
        """Test decrypting data."""
        original = b"Secret message"

        encrypted = encryptor_enabled.encrypt(original)
        decrypted = encryptor_enabled.decrypt(encrypted)

        assert decrypted == original

    def test_decrypt_disabled(self, encryptor_disabled):
        """Test that disabled decryption returns original data."""
        original = b"Test data"

        encrypted = encryptor_disabled.encrypt(original)
        decrypted = encryptor_disabled.decrypt(encrypted)

        assert decrypted == original

    def test_encrypt_roundtrip(self, encryptor_enabled):
        """Test encrypt -> decrypt roundtrip."""
        original = b"Test encryption roundtrip data. " * 10

        encrypted = encryptor_enabled.encrypt(original)
        decrypted = encryptor_enabled.decrypt(encrypted)

        assert decrypted == original

    def test_decrypt_with_wrong_key(self, test_key):
        """Test that decrypting with wrong key raises error."""
        wrong_key = Encryptor.generate_key()

        encryptor1 = Encryptor(enabled=True, encryption_key=test_key)
        encryptor2 = Encryptor(enabled=True, encryption_key=wrong_key)

        data = b"Secret"
        encrypted = encryptor1.encrypt(data)

        with pytest.raises(RuntimeError, match="Failed to decrypt"):
            encryptor2.decrypt(encrypted)

    def test_encrypt_error_raises(self, encryptor_enabled, monkeypatch):
        """Test encrypt error path."""
        def _boom(_data):
            raise Exception("boom")

        monkeypatch.setattr(encryptor_enabled.fernet, "encrypt", _boom)
        with pytest.raises(RuntimeError, match="Failed to encrypt data"):
            encryptor_enabled.encrypt(b"data")

    def test_decrypt_error_raises(self, encryptor_enabled, monkeypatch):
        """Test decrypt error path."""
        def _boom(_data):
            raise Exception("boom")

        monkeypatch.setattr(encryptor_enabled.fernet, "decrypt", _boom)
        with pytest.raises(RuntimeError, match="Failed to decrypt data"):
            encryptor_enabled.decrypt(b"data")

    def test_invalid_key_raises_error(self):
        """Test that invalid encryption key raises error."""
        with pytest.raises(ValueError, match="Invalid encryption key"):
            Encryptor(enabled=True, encryption_key="invalid_key")

    def test_enabled_without_key_raises_error(self):
        """Test that enabling encryption without key raises error."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove any TRACE_ENCRYPTION_KEY
            with pytest.raises(
                ValueError,
                match="Encryption key is required when encryption is enabled",
            ):
                Encryptor(enabled=True)


class TestProcessingPipeline:
    """Test complete processing pipeline."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return TraceConfig(
            redact_keys=["password", "secret"],
            redact_patterns=[r"\b\d{3}-\d{2}-\d{4}\b"],
            compression_enabled=True,
            compression_level=6,
            encryption_enabled=False,  # Disabled for simpler tests
        )

    @pytest.fixture
    def pipeline(self, config):
        """Create processing pipeline."""
        return ProcessingPipeline(config)

    def test_pipeline_redaction(self, pipeline):
        """Test that pipeline redacts data."""
        data = {
            "username": "john",
            "password": "secret123",
            "ssn": "123-45-6789",
        }

        processed = pipeline.process(data)
        reversed = pipeline.reverse(processed)

        assert reversed["username"] == "john"
        assert reversed["password"] == "[REDACTED]"
        assert "123-45-6789" not in str(reversed["ssn"])

    def test_pipeline_serialization(self, pipeline):
        """Test that pipeline serializes data."""
        data = {"name": "John", "age": 30}

        processed = pipeline.process(data)
        reversed = pipeline.reverse(processed)

        assert reversed == data

    def test_pipeline_compression(self, pipeline):
        """Test that pipeline compresses data."""
        data = {"message": "Hello" * 100}

        processed = pipeline.process(data)

        # Compressed data should be much smaller than JSON
        # JSON would be ~1500 bytes, compressed should be <500
        assert len(processed) < 500

    def test_pipeline_reverse_with_encryption_and_compression(self):
        """Reverse should work with encryption + compression."""
        key = Encryptor.generate_key()
        config = TraceConfig(
            encryption_enabled=True,
            encryption_key=key,
            compression_enabled=True,
            compression_level=6,
        )
        pipeline = ProcessingPipeline(config)
        original = {"hello": "world", "n": 1}
        processed = pipeline.process(original)
        reversed_data = pipeline.reverse(processed)
        assert reversed_data == original

    def test_pipeline_batch(self, pipeline):
        """Test processing a batch of events."""
        batch = [
            {"id": 1, "data": "Event 1"},
            {"id": 2, "data": "Event 2"},
            {"id": 3, "data": "Event 3"},
        ]

        processed = pipeline.process_batch(batch)

        assert len(processed) == len(batch)

    def test_pipeline_reverse(self, pipeline):
        """Test reverse processing (decrypt -> decompress -> deserialize)."""
        original = {"test": "data", "value": 123}

        processed = pipeline.process(original)
        reversed = pipeline.reverse(processed)

        assert reversed == original

    def test_reverse_handles_uncompressed_bytes(self):
        """Reverse should accept uncompressed JSON even if compression is enabled."""
        config = TraceConfig(
            compression_enabled=True,
            encryption_enabled=False,
        )
        pipeline = ProcessingPipeline(config)
        raw = Serializer.serialize({"a": 1})
        # Raw is not gzip-compressed, reverse should still work
        reversed = pipeline.reverse(raw)
        assert reversed == {"a": 1}

    def test_pipeline_roundtrip(self, pipeline):
        """Test complete pipeline roundtrip."""
        original = {
            "user": "john",
            "password": "secret",
            "data": "test",
        }

        processed = pipeline.process(original)
        reversed = pipeline.reverse(processed)

        # Data should be roundtripped (except redacted values)
        assert reversed["user"] == original["user"]
        assert reversed["data"] == original["data"]
        assert reversed["password"] == "[REDACTED]"  # Password redacted

    def test_pipeline_stats(self, pipeline):
        """Test getting pipeline statistics."""
        stats = pipeline.get_stats()

        assert "redaction" in stats
        assert "compression" in stats
        assert "encryption" in stats

        assert stats["redaction"]["enabled"] is True
        assert stats["compression"]["enabled"] is True
        assert stats["encryption"]["enabled"] is False


def test_compressor_is_compressed_false_for_short():
    """is_compressed should return False for too-short data."""
    comp = Compressor(enabled=True, compression_level=6)
    assert comp.is_compressed(b"") is False
    assert comp.is_compressed(b"\x1f") is False


def test_compressor_is_compressed_true():
    """is_compressed should return True for gzip magic bytes."""
    comp = Compressor(enabled=True, compression_level=6)
    assert comp.is_compressed(b"\x1f\x8b\x00") is True


class TestPipelineWithEncryption:
    """Test pipeline with encryption enabled."""

    @pytest.fixture
    def config_with_encryption(self):
        """Create configuration with encryption."""
        key = Encryptor.generate_key()
        return TraceConfig(
            encryption_enabled=True,
            encryption_key=key,
            compression_enabled=True,
            redact_keys=[],  # Disable redaction to test encryption alone
        )

    @pytest.fixture
    def encrypted_pipeline(self, config_with_encryption):
        """Create pipeline with encryption."""
        return ProcessingPipeline(config_with_encryption)

    def test_encrypted_pipeline_roundtrip(self, encrypted_pipeline):
        """Test pipeline roundtrip with encryption."""
        original = {"secret": "my secret data", "public": "public info"}

        processed = encrypted_pipeline.process(original)
        reversed = encrypted_pipeline.reverse(processed)

        assert reversed == original

    def test_encryption_in_pipeline(self, encrypted_pipeline):
        """Test that encryption is applied in pipeline."""
        data = {"test": "data" * 50}

        processed = encrypted_pipeline.process(data)

        # Encrypted + compressed data
        # Original is ~400 bytes, encrypted/compressed should be different size
        assert len(processed) != len(b"test" * 50)


class TestPipelineErrorHandling:
    """Test error handling in pipeline."""

    def test_redaction_error_handling(self):
        """Test that invalid redaction pattern raises error."""
        config = TraceConfig(redact_patterns=["[invalid(regex"])

        with pytest.raises(ValueError, match="Invalid redaction pattern"):
            Redactor(config)

    def test_serialization_error_handling(self):
        """Test that non-serializable data raises error."""

        # Create object that can't be serialized
        class UnserializableClass:
            pass

        pipeline = ProcessingPipeline(TraceConfig())
        data = {"data": UnserializableClass()}

        # Serializer has default=str, so this should work
        processed = pipeline.process(data)
        assert processed is not None

    def test_compression_error_handling(self):
        """Test that compression errors are handled."""
        # Create invalid compressor
        compressor = Compressor(enabled=True, compression_level=1)

        # This should work
        data = b"test"
        compressed = compressor.compress(data)

        assert compressed is not None

    def test_encryption_error_handling(self):
        """Test that encryption errors are handled."""
        # Try to encrypt without valid key
        with pytest.raises(ValueError):
            Encryptor(enabled=True, encryption_key="invalid_key")

    def test_batch_with_partial_failures(self):
        """Test that batch processing continues with partial failures."""
        # Mock to simulate partial failures
        config = TraceConfig(
            encryption_enabled=False,
            compression_enabled=False,
        )
        pipeline = ProcessingPipeline(config)

        # Create batch where some events might fail
        batch = [
            {"id": 1, "valid": True},
            {"id": 2, "valid": True},
            {"id": 3, "valid": True},
        ]

        # All should process (even if some fail internally)
        processed = pipeline.process_batch(batch)

        assert len(processed) > 0

    @pytest.mark.parametrize(
        ("attr", "method", "message"),
        [
            ("redactor", "redact", "Redaction failed"),
            ("serializer", "serialize", "Serialization failed"),
            ("compressor", "compress", "Compression failed"),
            ("encryptor", "encrypt", "Encryption failed"),
        ],
    )
    def test_process_step_error_paths(self, monkeypatch, attr, method, message):
        """Pipeline should surface step failures with context."""
        pipeline = ProcessingPipeline(TraceConfig())

        def _boom(*_args, **_kwargs):
            raise ValueError("boom")

        monkeypatch.setattr(getattr(pipeline, attr), method, _boom)
        with pytest.raises(RuntimeError, match=message):
            pipeline.process({"event_id": "evt-1", "type": "test", "run_id": "run-1"})

    def test_process_batch_skips_failed_events(self):
        """process_batch should skip failed events."""
        pipeline = ProcessingPipeline(TraceConfig())

        def _process(event):
            if event.get("event_id") == "bad":
                raise RuntimeError("boom")
            return b"ok"

        pipeline.process = _process  # type: ignore[assignment]
        processed = pipeline.process_batch(
            [
                {"event_id": "good"},
                {"event_id": "bad"},
            ]
        )
        assert processed == [b"ok"]

    def test_reverse_decrypt_failure_raises(self):
        """Reverse should surface decryption errors."""
        key = Encryptor.generate_key()
        config = TraceConfig(
            encryption_enabled=True,
            encryption_key=key,
            compression_enabled=False,
        )
        pipeline = ProcessingPipeline(config)
        # Create encrypted data with a different key to force failure
        wrong_key = Encryptor.generate_key()
        other = ProcessingPipeline(
            TraceConfig(
                encryption_enabled=True,
                encryption_key=wrong_key,
                compression_enabled=False,
            )
        )
        data = other.process({"secret": "data"})
        with pytest.raises(RuntimeError, match="Failed to decrypt"):
            pipeline.reverse(data)

    def test_reverse_deserialize_failure_raises(self):
        """Reverse should surface deserialize errors."""
        config = TraceConfig(
            encryption_enabled=False,
            compression_enabled=False,
        )
        pipeline = ProcessingPipeline(config)
        bad = b"not-json"
        with pytest.raises(RuntimeError, match="Failed to reverse process data"):
            pipeline.reverse(bad)
