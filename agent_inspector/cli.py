"""
Command-line interface for Agent Inspector.

Provides commands for:
- Starting the API server
- Viewing database statistics
- Pruning old trace data
- Exporting runs to JSON
- Managing configuration
"""

import argparse
import json
import logging
import sys
from typing import Optional

from . import __version__
from .api.main import run_server
from .core.config import Profile, TraceConfig, get_config, set_config


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """
    Setup logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional path to log file. If None, logs to stdout.
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename=log_file,
    )


def cmd_server(args):
    """Start the API server."""
    print("🚀 Starting Agent Inspector API server...")

    # Setup logging
    setup_logging(log_level=args.log_level, log_file=args.log_file)

    # Get or create configuration
    config = get_config()

    # Override with CLI arguments
    if args.host:
        config.api_host = args.host
    if args.port:
        config.api_port = args.port

    # Set the config
    set_config(config)

    # Start server
    print(f"📍 Server running on http://{config.api_host}:{config.api_port}")
    print(f"🌐 UI available at http://{config.api_host}:{config.api_port}/ui")
    print(f"📚 API docs at http://{config.api_host}:{config.api_port}/docs")
    print("\nPress Ctrl+C to stop the server\n")

    run_server(host=config.api_host, port=config.api_port)


def cmd_stats(args):
    """View database statistics."""
    from .storage.database import Database

    print("📊 Agent Inspector Statistics\n")

    # Setup logging
    setup_logging(log_level="WARNING")

    # Get configuration
    config = get_config()

    # Initialize database
    db = Database(config)
    db.initialize()

    # Get stats
    stats = db.get_stats()

    if not stats:
        print("❌ No statistics available")
        return 1

    # Display stats
    print(f"Total Runs: {stats.get('total_runs', 0)}")
    print(f"  - Running: {stats.get('running_runs', 0)}")
    print(f"  - Completed: {stats.get('completed_runs', 0)}")
    print(f"  - Failed: {stats.get('failed_runs', 0)}")
    print(f"\nTotal Steps (Events): {stats.get('total_steps', 0)}")
    print(f"Database Size: {stats.get('db_size_bytes', 0):,} bytes")
    print(f"\nRecent Activity (24h): {stats.get('recent_runs_24h', 0)} runs")

    return 0


def cmd_prune(args):
    """Prune old trace data."""
    from .storage.database import Database

    print("🧹 Pruning old trace data...")

    # Setup logging
    setup_logging(log_level=args.log_level or "INFO")

    # Get configuration
    config = get_config()

    # Override with CLI arguments
    if args.retention_days is not None:
        config.retention_days = args.retention_days
    if getattr(args, "retention_max_bytes", None) is not None:
        config.retention_max_bytes = args.retention_max_bytes

    # Initialize database
    db = Database(config)
    db.initialize()

    # Prune by age first
    deleted_count = db.prune_old_runs(retention_days=config.retention_days)
    size_deleted = 0

    # Then prune by size if configured
    max_bytes = config.retention_max_bytes
    if max_bytes is not None and max_bytes > 0:
        size_deleted = db.prune_by_size(max_bytes)
        deleted_count += size_deleted
        if size_deleted > 0:
            print(f"✅ Pruned {size_deleted} runs by size (max_bytes={max_bytes})")

    if deleted_count > 0:
        if size_deleted == 0:  # only age-based pruning had effect
            print(f"✅ Pruned {deleted_count} old runs")

        # Optionally vacuum to reclaim space (prune_by_size already vacuums)
        if args.vacuum:
            print("💾 Running VACUUM to reclaim disk space...")
            if db.vacuum():
                print("✅ VACUUM completed")
            else:
                print("⚠️  VACUUM failed")
    else:
        print("ℹ️  No runs to prune")

    return 0


def cmd_vacuum(args):
    """Run VACUUM to reclaim disk space."""
    from .storage.database import Database

    print("💾 Running VACUUM to reclaim disk space...")

    # Setup logging
    setup_logging(log_level="WARNING")

    # Get configuration
    config = get_config()

    # Initialize database
    db = Database(config)
    db.initialize()

    # Run vacuum
    if db.vacuum():
        print("✅ VACUUM completed successfully")
        return 0
    else:
        print("❌ VACUUM failed")
        return 1


def cmd_backup(args):
    """Create a database backup."""
    from .storage.database import Database

    print(f"💾 Creating backup to {args.backup_path}...")

    # Setup logging
    setup_logging(log_level="INFO")

    # Get configuration
    config = get_config()

    # Initialize database
    db = Database(config)
    db.initialize()

    # Create backup
    if db.backup(args.backup_path):
        print(f"✅ Backup created at {args.backup_path}")
        return 0
    else:
        print("❌ Backup failed")
        return 1


def cmd_export(args):
    """Export run(s) to JSON file or stdout."""
    from .processing.pipeline import ProcessingPipeline
    from .storage.database import Database

    if not getattr(args, "all_runs", False) and not getattr(args, "run_id", None):
        print("Error: provide run_id or use --all", file=sys.stderr)
        return 1

    setup_logging(log_level="INFO")
    config = get_config()
    db = Database(config)
    db.initialize()
    pipeline = ProcessingPipeline(config)

    def export_one(run_id: str) -> Optional[dict]:
        run = db.get_run(run_id)
        if not run:
            print(f"Run {run_id} not found", file=sys.stderr)
            return None
        timeline = db.get_run_timeline(run_id=run_id, include_data=True)
        for event in timeline:
            if event.get("data"):
                try:
                    event["data"] = pipeline.reverse(event["data"])
                except Exception:
                    event["data"] = None
        return {"run": dict(run), "timeline": timeline}

    if getattr(args, "all_runs", False):
        runs = db.list_runs(limit=args.limit or 1000, offset=0)
        payload = []
        for r in runs:
            rid = r.get("id")
            if rid:
                one = export_one(rid)
                if one:
                    payload.append(one)
        data = {"runs": payload, "total": len(payload)}
    else:
        one = export_one(args.run_id)
        if not one:
            return 1
        data = one

    out = args.output
    json_str = json.dumps(data, indent=2, default=str)
    if out:
        with open(out, "w") as f:
            f.write(json_str)
        print(f"✅ Exported to {out}")
    else:
        print(json_str)
    return 0


def cmd_config(args):
    """View or set configuration."""
    config = get_config()

    if args.show:
        # Show current configuration
        print("⚙️  Current Configuration\n")
        print(config.to_json())
    elif args.profile:
        # Set profile
        try:
            profile = Profile(args.profile.lower())

            if profile == Profile.PRODUCTION:
                new_config = TraceConfig.production()
            elif profile == Profile.DEVELOPMENT:
                new_config = TraceConfig.development()
            elif profile == Profile.DEBUG:
                new_config = TraceConfig.debug()
            else:
                print(f"❌ Unknown profile: {args.profile}")
                return 1

            set_config(new_config)
            print(f"✅ Configuration set to {profile.value} profile")
            return 0
        except ValueError as e:
            print(f"❌ Invalid profile: {e}")
            return 1
    else:
        # Show brief configuration
        print("⚙️  Agent Inspector Configuration\n")
        print(f"Sample Rate: {config.sample_rate * 100:.1f}%")
        print(f"Only on Error: {config.only_on_error}")
        print(f"Encryption: {'Enabled' if config.encryption_enabled else 'Disabled'}")
        print(f"Compression: {'Enabled' if config.compression_enabled else 'Disabled'}")
        print(f"API Host: {config.api_host}:{config.api_port}")
        print(f"Database: {config.db_path}")

    return 0


def cmd_init(args):
    """Initialize Agent Inspector."""
    print("🔧 Initializing Agent Inspector...")

    # Create default configuration
    config = TraceConfig()

    # Override with arguments
    if args.profile:
        try:
            profile = Profile(args.profile.lower())
            if profile == Profile.PRODUCTION:
                config = TraceConfig.production()
            elif profile == Profile.DEVELOPMENT:
                config = TraceConfig.development()
            elif profile == Profile.DEBUG:
                config = TraceConfig.debug()
        except ValueError as e:
            print(f"❌ Invalid profile: {e}")
            return 1

    # Initialize database
    from .storage.database import Database

    db = Database(config)
    db.initialize()

    print("✅ Agent Inspector initialized!")
    print(f"\n📍 Database: {config.db_path}")
    print(f"📊 Sample Rate: {config.sample_rate * 100:.1f}%")
    print(f"🔒 Encryption: {'Enabled' if config.encryption_enabled else 'Disabled'}")

    print("\n💡 Next steps:")
    print("   - Start API server: agent-inspector server")
    print("   - Run examples: python examples/basic_tracing.py")
    print("   - View UI: http://localhost:8000/ui")

    return 0


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="agent-inspector",
        description="Framework-agnostic observability for AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start API server
  agent-inspector server

  # Start server on custom port
  agent-inspector server --port 8080

  # View statistics
  agent-inspector stats

  # Prune data older than 30 days
  agent-inspector prune --retention-days 30

  # Set development profile
  agent-inspector config --profile development

  # Initialize with debug profile
  agent-inspector init --profile debug
        """,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Server command
    server_parser = subparsers.add_parser(
        "server",
        help="Start the API server",
        description="Start the FastAPI server for serving trace data and UI",
    )
    server_parser.add_argument(
        "--host",
        type=str,
        help="Host to bind to (default: 127.0.0.1)",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        help="Port to bind to (default: 8000)",
    )
    server_parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Log level (default: INFO)",
    )
    server_parser.add_argument(
        "--log-file",
        type=str,
        help="Path to log file (default: stdout)",
    )

    # Stats command
    _stats_parser = subparsers.add_parser(
        "stats",
        help="View database statistics",
        description="Display statistics about stored trace data",
    )

    # Prune command
    prune_parser = subparsers.add_parser(
        "prune",
        help="Prune old trace data",
        description="Delete trace data older than the retention period",
    )
    prune_parser.add_argument(
        "--retention-days",
        type=int,
        help="Retention period in days (default: from config)",
    )
    prune_parser.add_argument(
        "--retention-max-bytes",
        type=int,
        default=None,
        metavar="BYTES",
        help="Prune oldest runs until DB size is at or below BYTES (optional; from config if set)",
    )
    prune_parser.add_argument(
        "--vacuum",
        action="store_true",
        help="Run VACUUM after pruning to reclaim disk space",
    )
    prune_parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )

    # Vacuum command
    _vacuum_parser = subparsers.add_parser(
        "vacuum",
        help="Run VACUUM to reclaim disk space",
        description="Run SQLite VACUUM to reclaim disk space",
    )

    # Backup command
    backup_parser = subparsers.add_parser(
        "backup",
        help="Create database backup",
        description="Create a backup of the SQLite database",
    )
    backup_parser.add_argument(
        "backup_path",
        type=str,
        help="Path where backup should be saved",
    )

    # Export command
    export_parser = subparsers.add_parser(
        "export",
        help="Export run(s) to JSON",
        description="Export a run or all runs to JSON (run metadata + timeline with decoded event data)",
    )
    export_parser.add_argument(
        "run_id",
        nargs="?",
        type=str,
        help="Run ID to export (omit if using --all)",
    )
    export_parser.add_argument(
        "--all",
        dest="all_runs",
        action="store_true",
        help="Export all runs",
    )
    export_parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Max runs to export when using --all (default: 1000)",
    )
    export_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path (default: stdout)",
    )

    # Config command
    config_parser = subparsers.add_parser(
        "config",
        help="View or set configuration",
        description="View current configuration or set a profile preset",
    )
    config_parser.add_argument(
        "--show",
        action="store_true",
        help="Show full configuration",
    )
    config_parser.add_argument(
        "--profile",
        type=str,
        choices=["production", "development", "debug"],
        help="Set configuration profile (production, development, debug)",
    )

    # Init command
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize Agent Inspector",
        description="Initialize Agent Inspector with default configuration",
    )
    init_parser.add_argument(
        "--profile",
        type=str,
        choices=["production", "development", "debug"],
        help="Configuration profile to use",
    )

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    if args.command == "server":
        return cmd_server(args)
    elif args.command == "stats":
        return cmd_stats(args)
    elif args.command == "prune":
        return cmd_prune(args)
    elif args.command == "vacuum":
        return cmd_vacuum(args)
    elif args.command == "backup":
        return cmd_backup(args)
    elif args.command == "export":
        return cmd_export(args)
    elif args.command == "config":
        return cmd_config(args)
    elif args.command == "init":
        return cmd_init(args)
    else:
        # No command specified, show help
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
