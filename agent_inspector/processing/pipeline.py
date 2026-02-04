"""
Data processing pipeline for Agent Inspector.

Handles redaction, serialization, compression, and encryption of trace data
in a secure and efficient manner.
"""

import gzip
import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from cryptography.fernet import Fernet

from ..core.config import TraceConfig

logger = logging.getLogger(__name__)


class Redactor:
    """
    Redacts sensitive data from event payloads.

    Performs key-based and pattern-based redaction to protect sensitive
    information like passwords, API keys, tokens, etc.
    """

    def __init__(self, config: TraceConfig):
        """
        Initialize redactor with configuration.

        Args:
            config: TraceConfig instance with redaction settings.
        """
        self.config = config
        self.redact_keys: Set[str] = config.get_redaction_keys_set()
        self.redact_patterns: List[re.Pattern] = (
            config.get_redaction_patterns_compiled()
        )

    def redact(self, data: Any, redaction_marker: str = "[REDACTED]") -> Any:
        """
        Redact sensitive data from a value.

        Args:
            data: Data to redact (can be dict, list, string, or other).
            redaction_marker: String to replace sensitive data with.

        Returns:
            Redacted data with same structure as input.
        """
        if isinstance(data, dict):
            return self._redact_dict(data, redaction_marker)
        elif isinstance(data, list):
            return self._redact_list(data, redaction_marker)
        elif isinstance(data, str):
            return self._redact_string(data, redaction_marker)
        else:
            # Numbers, booleans, None - no redaction needed
            return data

    def _redact_dict(self, data: Dict[str, Any], marker: str) -> Dict[str, Any]:
        """Redact values in a dictionary based on keys."""
        redacted = {}
        for key, value in data.items():
            key_lower = key.lower()
            if key_lower in self.redact_keys:
                redacted[key] = marker
            elif isinstance(value, (dict, list, str)):
                redacted[key] = self.redact(value, marker)
            else:
                redacted[key] = value
        return redacted

    def _redact_list(self, data: List[Any], marker: str) -> List[Any]:
        """Redact values in a list."""
        redacted = []
        for item in data:
            if isinstance(item, (dict, list, str)):
                redacted.append(self.redact(item, marker))
            else:
                redacted.append(item)
        return redacted

    def _redact_string(self, data: str, marker: str) -> str:
        """Redact sensitive patterns in a string."""
        redacted = data

        # Redact based on key-value patterns
        for key in self.redact_keys:
            # Match key followed by :, =, or space, then capture the value
            # Example matches: "Password: secret123", "password=secret123", "PASSWORD secret123"
            pattern = re.compile(
                rf"(?i)(\b{re.escape(key)}\b\s*[:=]\s*)([^:\s]+(?:\s+[^\s:\n]+)*)",
                re.MULTILINE,
            )
            redacted = pattern.sub(r"\1" + marker, redacted)

        # Redact based on regex patterns
        for pattern in self.redact_patterns:
            redacted = pattern.sub(marker, redacted)

        return redacted

    def add_redaction_key(self, key: str):
        """
        Add a key to the redaction list.

        Args:
            key: Key to add (case-insensitive).
        """
        self.redact_keys.add(key.lower())

    def add_redaction_pattern(self, pattern: str):
        """
        Add a regex pattern to the redaction list.

        Args:
            pattern: Regex pattern string.

        Raises:
            re.error: If pattern is invalid.
        """
        compiled = re.compile(pattern)
        self.redact_patterns.append(compiled)


class Serializer:
    """
    Serializes data to compact JSON format.
    """

    @staticmethod
    def serialize(data: Any) -> bytes:
        """
        Serialize data to JSON bytes.

        Args:
            data: Data to serialize (must be JSON-serializable).

        Returns:
            UTF-8 encoded JSON bytes.

        Raises:
            TypeError: If data is not JSON-serializable.
        """
        try:
            json_str = json.dumps(
                data,
                ensure_ascii=False,
                separators=(",", ":"),  # Compact JSON
                default=str,  # Convert non-serializable types to string
            )
            return json_str.encode("utf-8")
        except Exception as e:
            logger.error(f"Serialization error: {e}")
            raise TypeError(f"Failed to serialize data: {e}")

    @staticmethod
    def deserialize(data: bytes) -> Any:
        """
        Deserialize JSON bytes back to Python object.

        Args:
            data: JSON bytes to deserialize.

        Returns:
            Deserialized Python object.

        Raises:
            json.JSONDecodeError: If data is not valid JSON.
        """
        try:
            json_str = data.decode("utf-8")
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Deserialization error: {e}")
            raise ValueError(f"Failed to deserialize data: {e}")


class Compressor:
    """
    Compresses data using gzip for storage efficiency.
    """

    def __init__(self, enabled: bool = True, compression_level: int = 6):
        """
        Initialize compressor with configuration.

        Args:
            enabled: Whether compression is enabled.
            compression_level: Gzip compression level (1-9).
        """
        self.enabled = enabled
        self.compression_level = compression_level

    def compress(self, data: bytes) -> bytes:
        """
        Compress data using gzip.

        Args:
            data: Data to compress.

        Returns:
            Compressed data (or original data if compression disabled).

        Raises:
            Exception: If compression fails.
        """
        if not self.enabled:
            return data

        try:
            compressed = gzip.compress(data, compresslevel=self.compression_level)
            ratio = len(compressed) / len(data) if data else 0
            logger.debug(
                f"Compressed {len(data)} bytes to {len(compressed)} bytes "
                f"(ratio: {ratio:.2%})"
            )
            return compressed
        except Exception as e:
            logger.error(f"Compression error: {e}")
            raise RuntimeError(f"Failed to compress data: {e}")

    def decompress(self, data: bytes) -> bytes:
        """
        Decompress gzip data.

        Args:
            data: Compressed data.

        Returns:
            Decompressed data.

        Raises:
            Exception: If decompression fails.
        """
        if not self.enabled:
            return data

        try:
            return gzip.decompress(data)
        except Exception as e:
            logger.error(f"Decompression error: {e}")
            raise RuntimeError(f"Failed to decompress data: {e}")

    def is_compressed(self, data: bytes) -> bool:
        """
        Check if data is gzip-compressed.

        Args:
            data: Data to check.

        Returns:
            True if data appears to be gzip-compressed.
        """
        if len(data) < 2:
            return False
        # Check for gzip magic number
        return data[0:2] == b"\x1f\x8b"


class Encryptor:
    """
    Encrypts data using Fernet symmetric encryption.

    Encryption is optional and configured via TraceConfig.
    """

    def __init__(self, enabled: bool = False, encryption_key: Optional[str] = None):
        """
        Initialize encryptor with configuration.

        Args:
            enabled: Whether encryption is enabled.
            encryption_key: Fernet encryption key (32 bytes, base64-encoded).

        Raises:
            ValueError: If encryption is enabled but no key is provided.
            Exception: If key is invalid.
        """
        self.enabled = enabled
        self.fernet: Optional[Fernet] = None

        if enabled:
            if not encryption_key:
                raise ValueError(
                    "Encryption key is required when encryption is enabled"
                )
            try:
                self.fernet = Fernet(
                    encryption_key.encode()
                    if isinstance(encryption_key, str)
                    else encryption_key
                )
            except Exception as e:
                logger.error(f"Failed to initialize Fernet: {e}")
                raise ValueError(f"Invalid encryption key: {e}")

    def encrypt(self, data: bytes) -> bytes:
        """
        Encrypt data using Fernet.

        Args:
            data: Data to encrypt.

        Returns:
            Encrypted data.

        Raises:
            Exception: If encryption fails.
        """
        if not self.enabled or not self.fernet:
            return data

        try:
            encrypted = self.fernet.encrypt(data)
            logger.debug(f"Encrypted {len(data)} bytes to {len(encrypted)} bytes")
            return encrypted
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise RuntimeError(f"Failed to encrypt data: {e}")

    def decrypt(self, data: bytes) -> bytes:
        """
        Decrypt Fernet-encrypted data.

        Args:
            data: Encrypted data.

        Returns:
            Decrypted data.

        Raises:
            Exception: If decryption fails.
        """
        if not self.enabled or not self.fernet:
            return data

        try:
            decrypted = self.fernet.decrypt(data)
            return decrypted
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise RuntimeError(f"Failed to decrypt data: {e}")

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.

        Returns:
            Base64-encoded encryption key string.

        Example:
            >>> key = Encryptor.generate_key()
            >>> print(key)
            'gAAAAABl...'
        """
        import base64

        from cryptography.fernet import Fernet

        return Fernet.generate_key().decode()


class ProcessingPipeline:
    """
    Complete data processing pipeline.

    Processes event data through: redaction → serialization → compression → encryption.
    """

    def __init__(self, config: TraceConfig):
        """
        Initialize the processing pipeline.

        Args:
            config: TraceConfig instance.
        """
        self.config = config
        self.redactor = Redactor(config)
        self.serializer = Serializer()
        self.compressor = Compressor(
            enabled=config.compression_enabled,
            compression_level=config.compression_level,
        )
        self.encryptor = Encryptor(
            enabled=config.encryption_enabled,
            encryption_key=config.encryption_key,
        )

    def process(self, data: Dict[str, Any]) -> bytes:
        """
        Process event data through the complete pipeline.

        Pipeline order: redaction → serialization → compression → encryption

        Args:
            data: Event dictionary to process.

        Returns:
            Processed bytes ready for storage.

        Raises:
            RuntimeError: If any processing step fails, with detailed context.
        """
        event_id = data.get("event_id", "unknown")
        event_type = data.get("type", "unknown")
        run_id = data.get("run_id", "unknown")

        try:
            # Step 1: Redact sensitive data
            try:
                redacted = self.redactor.redact(data)
            except Exception as e:
                raise RuntimeError(f"Redaction failed for event {event_id}: {e}")

            # Step 2: Serialize to JSON
            try:
                serialized = self.serializer.serialize(redacted)
            except Exception as e:
                raise RuntimeError(f"Serialization failed for event {event_id}: {e}")

            # Step 3: Compress
            try:
                compressed = self.compressor.compress(serialized)
            except Exception as e:
                raise RuntimeError(f"Compression failed for event {event_id}: {e}")

            # Step 4: Encrypt (optional)
            try:
                encrypted = self.encryptor.encrypt(compressed)
            except Exception as e:
                raise RuntimeError(f"Encryption failed for event {event_id}: {e}")

            return encrypted
        except Exception as e:
            logger.error(
                f"Pipeline processing error for event {event_id} "
                f"(type={event_type}, run={run_id}): {e}"
            )
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(
                f"Failed to process event {event_id} through pipeline: {e}"
            ) from e

    def process_batch(self, events: List[Dict[str, Any]]) -> List[bytes]:
        """
        Process a batch of events through the pipeline.

        Args:
            events: List of event dictionaries.

        Returns:
            List of processed byte arrays.
        """
        processed = []
        for event in events:
            try:
                processed_event = self.process(event)
                processed.append(processed_event)
            except Exception as e:
                logger.error(f"Failed to process event {event.get('event_id')}: {e}")
                # Skip failed events, continue processing others
                continue
        return processed

    def reverse(self, data: bytes) -> Dict[str, Any]:
        """
        Reverse process: decrypt → decompress → deserialize.

        Args:
            data: Processed bytes from storage.

        Returns:
            Original event dictionary.

        Raises:
            Exception: If any reverse processing step fails.
        """
        try:
            # Step 1: Decrypt (reverse of encrypt)
            decrypted = self.encryptor.decrypt(data)

            # Step 2: Decompress (reverse of compress)
            if self.compressor.enabled and self.compressor.is_compressed(decrypted):
                decompressed = self.compressor.decompress(decrypted)
            else:
                decompressed = decrypted

            # Step 3: Deserialize (reverse of serialize)
            deserialized = self.serializer.deserialize(decompressed)

            # Note: Redaction cannot be reversed
            return deserialized
        except Exception as e:
            logger.error(f"Pipeline reverse processing error: {e}")
            raise RuntimeError(f"Failed to reverse process data: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get pipeline statistics and configuration.

        Returns:
            Dictionary with pipeline configuration.
        """
        return {
            "redaction": {
                "enabled": True,
                "redact_keys_count": len(self.redactor.redact_keys),
                "redact_patterns_count": len(self.redactor.redact_patterns),
            },
            "compression": {
                "enabled": self.compressor.enabled,
                "level": self.compressor.compression_level,
            },
            "encryption": {
                "enabled": self.encryptor.enabled,
            },
        }
