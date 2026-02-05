"""
Tests for Agent Inspector CLI.

Covers prune with retention_max_bytes and other CLI behavior.
"""

from unittest.mock import MagicMock, patch

from agent_inspector.cli import cmd_prune
from agent_inspector.core.config import TraceConfig


class TestPruneCli:
    """Test prune command behavior."""

    def test_prune_calls_prune_by_size_when_retention_max_bytes_set(self):
        """cmd_prune calls db.prune_by_size when config.retention_max_bytes is set."""
        with patch("agent_inspector.cli.get_config") as mock_get_config:
            with patch("agent_inspector.storage.database.Database") as mock_db_class:
                mock_db = MagicMock()
                mock_db.prune_old_runs.return_value = 0
                mock_db.prune_by_size.return_value = 2
                mock_db_class.return_value = mock_db

                config = TraceConfig()
                config.retention_days = 30
                config.retention_max_bytes = 5000000
                mock_get_config.return_value = config

                args = MagicMock()
                args.retention_days = None
                args.retention_max_bytes = None
                args.log_level = "INFO"
                args.vacuum = False

                result = cmd_prune(args)

                assert result == 0
                mock_db.initialize.assert_called_once()
                mock_db.prune_old_runs.assert_called_once_with(retention_days=30)
                mock_db.prune_by_size.assert_called_once_with(5000000)

    def test_prune_cli_arg_retention_max_bytes_overrides_config(self):
        """--retention-max-bytes CLI arg overrides config."""
        with patch("agent_inspector.cli.get_config") as mock_get_config:
            with patch("agent_inspector.storage.database.Database") as mock_db_class:
                mock_db = MagicMock()
                mock_db.prune_old_runs.return_value = 0
                mock_db.prune_by_size.return_value = 0
                mock_db_class.return_value = mock_db

                config = TraceConfig()
                config.retention_days = 7
                config.retention_max_bytes = None
                mock_get_config.return_value = config

                args = MagicMock()
                args.retention_days = None
                args.retention_max_bytes = 10000000
                args.log_level = "INFO"
                args.vacuum = False

                result = cmd_prune(args)

                assert result == 0
                mock_db.prune_by_size.assert_called_once_with(10000000)

    def test_prune_skips_prune_by_size_when_retention_max_bytes_none(self):
        """cmd_prune does not call prune_by_size when retention_max_bytes is None."""
        with patch("agent_inspector.cli.get_config") as mock_get_config:
            with patch("agent_inspector.storage.database.Database") as mock_db_class:
                mock_db = MagicMock()
                mock_db.prune_old_runs.return_value = 1
                mock_db_class.return_value = mock_db

                config = TraceConfig()
                config.retention_days = 30
                config.retention_max_bytes = None
                mock_get_config.return_value = config

                args = MagicMock()
                args.retention_days = None
                args.retention_max_bytes = None
                args.log_level = "INFO"
                args.vacuum = False

                result = cmd_prune(args)

                assert result == 0
                mock_db.prune_old_runs.assert_called_once()
                mock_db.prune_by_size.assert_not_called()
