"""
SQLite storage module for Agent Inspector.

Provides persistent storage for trace data with efficient querying,
batch operations, and automatic schema migrations.
"""

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..core.config import TraceConfig

logger = logging.getLogger(__name__)


class Database:
    """
    SQLite database for storing trace data.

    Features:
    - WAL mode for concurrent access
    - Efficient indexing on run_id and timestamp
    - Batch insert operations
    - Automatic schema migration
    - Prune and vacuum utilities
    """

    # Current schema version
    SCHEMA_VERSION = 1

    def __init__(self, config: TraceConfig):
        """
        Initialize the database.

        Args:
            config: TraceConfig instance with database configuration.
        """
        self.config = config
        self.db_path = config.db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._initialized = False

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get a thread-local database connection.

        Each thread gets its own connection to ensure thread safety.
        Connections are created on first use per thread.

        Returns:
            SQLite connection for the current thread.
        """
        # Check if we already have a connection for this thread
        if not hasattr(self._local, "connection") or self._local.connection is None:
            # Create a new connection for this thread
            # check_same_thread=True is the default and ensures thread safety
            conn = sqlite3.connect(
                self.db_path,
                check_same_thread=True,  # Enforce thread safety
                timeout=30.0,
                isolation_level=None,  # Autocommit mode for better concurrency
            )
            conn.row_factory = sqlite3.Row

            # Configure connection for WAL mode and performance
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA mmap_size=30000000000")  # Enable memory mapping

            self._local.connection = conn
            logger.debug(
                f"Created new database connection for thread {threading.current_thread().name}"
            )

        return self._local.connection

    def initialize(self):
        """Initialize database schema and migrations."""
        if self._initialized:
            logger.warning("Database already initialized")
            return

        self._lock.acquire()
        try:
            conn = self._get_connection()

            # Create schema if it doesn't exist
            self._create_schema(conn)

            # Run migrations if needed
            self._run_migrations(conn)

            self._initialized = True
            logger.info(f"Database initialized at {self.db_path}")
        finally:
            self._lock.release()

    def _create_schema(self, conn: sqlite3.Connection):
        """Create database schema."""
        # Check if schema exists
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )

        if cursor.fetchone() is None:
            logger.info("Creating database schema")

            # Schema version table
            conn.execute(
                """
                CREATE TABLE schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Runs table - stores run metadata
            conn.execute(
                """
                CREATE TABLE runs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at INTEGER NOT NULL,
                    completed_at INTEGER,
                    duration_ms INTEGER,
                    agent_type TEXT,
                    user_id TEXT,
                    session_id TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Steps table - stores individual events
            conn.execute(
                """
                CREATE TABLE steps (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    name TEXT,
                    status TEXT,
                    duration_ms INTEGER,
                    data BLOB NOT NULL,
                    parent_event_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
                )
            """
            )

            # Indexes for efficient queries
            conn.execute("CREATE INDEX idx_runs_started_at ON runs(started_at)")
            conn.execute("CREATE INDEX idx_runs_status ON runs(status)")
            conn.execute("CREATE INDEX idx_runs_user_id ON runs(user_id)")
            conn.execute("CREATE INDEX idx_runs_session_id ON runs(session_id)")
            conn.execute("CREATE INDEX idx_steps_run_id ON steps(run_id)")
            conn.execute("CREATE INDEX idx_steps_timestamp ON steps(timestamp)")
            conn.execute("CREATE INDEX idx_steps_type ON steps(type)")
            conn.execute(
                "CREATE INDEX idx_steps_run_id_timestamp ON steps(run_id, timestamp)"
            )

            # Insert schema version
            conn.execute(
                f"INSERT INTO schema_version (version) VALUES ({self.SCHEMA_VERSION})"
            )

            conn.commit()
            logger.info("Database schema created")

    def _run_migrations(self, conn: sqlite3.Connection):
        """Run database migrations if needed."""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        )
        row = cursor.fetchone()

        current_version = row["version"] if row else 0

        if current_version < self.SCHEMA_VERSION:
            logger.info(
                f"Running migrations from version {current_version} to {self.SCHEMA_VERSION}"
            )

            # Add future migrations here
            # Example:
            # if current_version < 2:
            #     self._migrate_to_v2(conn)

            conn.execute(f"UPDATE schema_version SET version = {self.SCHEMA_VERSION}")
            conn.commit()
            logger.info("Migrations completed")

    def insert_run(self, run_data: Dict[str, Any]) -> bool:
        """
        Insert a new run into the database.

        Args:
            run_data: Dictionary with run information (id, name, status, etc.).

        Returns:
            True if insert successful, False otherwise.
        """
        try:
            conn = self._get_connection()
            conn.execute(
                """
                INSERT OR REPLACE INTO runs (
                    id, name, status, started_at, completed_at, duration_ms,
                    agent_type, user_id, session_id, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_data.get("id"),
                    run_data.get("name"),
                    run_data.get("status", "running"),
                    run_data.get("started_at"),
                    run_data.get("completed_at"),
                    run_data.get("duration_ms"),
                    run_data.get("agent_type"),
                    run_data.get("user_id"),
                    run_data.get("session_id"),
                    json.dumps(run_data.get("metadata", {})),
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to insert run: {e}")
            return False

    def update_run(
        self,
        run_id: str,
        status: Optional[str] = None,
        completed_at: Optional[int] = None,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update a run with new information.

        Args:
            run_id: ID of the run to update.
            status: New status (running, completed, failed).
            completed_at: Completion timestamp in milliseconds.
            duration_ms: Duration of the run in milliseconds.
            metadata: Additional metadata to update.

        Returns:
            True if update successful, False otherwise.
        """
        try:
            conn = self._get_connection()

            # Build update query dynamically
            updates = []
            params = []

            if status is not None:
                updates.append("status = ?")
                params.append(status)

            if completed_at is not None:
                updates.append("completed_at = ?")
                params.append(completed_at)

            if duration_ms is not None:
                updates.append("duration_ms = ?")
                params.append(duration_ms)

            if metadata is not None:
                # Merge JSON metadata in Python to avoid string concatenation
                existing = {}
                current = self.get_run(run_id)
                if current and current.get("metadata"):
                    try:
                        existing = json.loads(current.get("metadata") or "{}")
                    except Exception:
                        existing = {}
                merged = {**existing, **metadata}
                updates.append("metadata = ?")
                params.append(json.dumps(merged))

            if not updates:
                return True  # Nothing to update

            params.append(run_id)

            query = f"UPDATE runs SET {', '.join(updates)} WHERE id = ?"
            conn.execute(query, params)
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update run {run_id}: {e}")
            return False

    def insert_steps(self, steps: List[Tuple[Dict[str, Any], bytes]]) -> int:
        """
        Insert multiple steps in a batch.

        Args:
            steps: List of tuples (event_dict, processed_data_bytes).
                   event_dict contains the event metadata as a dictionary.
                   processed_data_bytes is the processed/encrypted data for storage.
                   Each step's data should already be processed through the pipeline.

        Returns:
            Number of steps successfully inserted.
        """
        if not steps:
            return 0

        try:
            conn = self._get_connection()
            # Prepare data for insertion - convert dicts to JSON strings
            import json as json_module

            values = []
            for event_dict, processed_data in steps:
                # Convert event dict to JSON string for json_extract to work
                json_str = json_module.dumps(event_dict)
                values.append(
                    (
                        json_str,  # For json_extract('$.event_id')
                        json_str,  # For json_extract('$.run_id')
                        json_str,  # For json_extract('$.timestamp_ms')
                        json_str,  # For json_extract('$.type')
                        json_str,  # For json_extract('$.name')
                        json_str,  # For json_extract('$.status')
                        json_str,  # For json_extract('$.duration_ms')
                        processed_data,  # The actual blob data
                        json_str,  # For json_extract('$.parent_event_id')
                    )
                )

            conn.executemany(
                """
                INSERT OR REPLACE INTO steps (id, run_id, timestamp, type, name, status, duration_ms, data, parent_event_id)
                VALUES (
                    json_extract(?, '$.event_id'),
                    json_extract(?, '$.run_id'),
                    json_extract(?, '$.timestamp_ms'),
                    json_extract(?, '$.type'),
                    json_extract(?, '$.name'),
                    json_extract(?, '$.status'),
                    json_extract(?, '$.duration_ms'),
                    ?,
                    json_extract(?, '$.parent_event_id')
                )
                """,
                values,
            )
            conn.commit()
            return len(steps)
        except Exception as e:
            logger.error(f"Failed to insert batch of {len(steps)} steps: {e}")
            return 0

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a run by ID.

        Args:
            run_id: ID of the run.

        Returns:
            Run dictionary or None if not found.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"Failed to get run {run_id}: {e}")
            return None

    def list_runs(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        search: Optional[str] = None,
        order_by: str = "started_at",
        order_dir: str = "DESC",
    ) -> List[Dict[str, Any]]:
        """
        List runs with filtering and pagination.

        Args:
            limit: Maximum number of runs to return.
            offset: Number of runs to skip.
            status: Filter by status (running, completed, failed).
            user_id: Filter by user ID.
            session_id: Filter by session ID.
            search: Search in run name.
            order_by: Field to order by.
            order_dir: Direction (ASC or DESC).

        Returns:
            List of run dictionaries.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Build query with filters
            query = "SELECT * FROM runs WHERE 1=1"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status)

            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)

            if search:
                query += " AND name LIKE ?"
                params.append(f"%{search}%")

            # Add ordering
            valid_order_fields = ["started_at", "completed_at", "duration_ms", "name"]
            if order_by in valid_order_fields:
                query += f" ORDER BY {order_by} {order_dir}"

            # Add pagination
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to list runs: {e}")
            return []

    def get_run_steps(
        self,
        run_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all steps for a run.

        Args:
            run_id: ID of the run.
            limit: Maximum number of steps to return.
            offset: Number of steps to skip.
            event_type: Filter by event type.

        Returns:
            List of step dictionaries with decoded data.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = "SELECT * FROM steps WHERE run_id = ?"
            params = [run_id]

            if event_type:
                query += " AND type = ?"
                params.append(event_type)

            query += " ORDER BY timestamp ASC"

            if limit:
                query += " LIMIT ? OFFSET ?"
                params.extend([str(limit), str(offset)])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            steps = []
            for row in rows:
                step = dict(row)
                # Note: data is not decoded here as it needs the pipeline
                steps.append(step)

            return steps
        except Exception as e:
            logger.error(f"Failed to get steps for run {run_id}: {e}")
            return []

    def get_run_timeline(
        self, run_id: str, include_data: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get timeline data for a run (optimized for UI).

        Args:
            run_id: ID of the run.
            include_data: Whether to include full event data.

        Returns:
            List of timeline events.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Select fields based on whether data is needed
            if include_data:
                query = "SELECT * FROM steps WHERE run_id = ? ORDER BY timestamp ASC"
            else:
                query = """
                    SELECT id, run_id, timestamp, type, name, status, duration_ms, parent_event_id
                    FROM steps WHERE run_id = ? ORDER BY timestamp ASC
                """

            cursor.execute(query, (run_id,))
            rows = cursor.fetchall()

            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get timeline for run {run_id}: {e}")
            return []

    def get_step_data(self, step_id: str) -> Optional[bytes]:
        """
        Get raw BLOB data for a step.

        Args:
            step_id: ID of step.

        Returns:
            Raw BLOB data or None if not found.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT data FROM steps WHERE id = ?", (step_id,))
            row = cursor.fetchone()

            if row:
                return row[0]
            return None
        except Exception as e:
            logger.error(f"Failed to get step data for {step_id}: {e}")
            return None

    def delete_run(self, run_id: str) -> bool:
        """
        Delete a run and all its associated steps.

        Args:
            run_id: ID of the run to delete.

        Returns:
            True if deletion successful, False otherwise.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Delete steps first (cascade will handle this due to foreign key)
            cursor.execute("DELETE FROM steps WHERE run_id = ?", (run_id,))
            steps_deleted = cursor.rowcount

            # Delete run
            cursor.execute("DELETE FROM runs WHERE id = ?", (run_id,))
            runs_deleted = cursor.rowcount

            conn.commit()

            if runs_deleted > 0:
                logger.info(f"Deleted run {run_id} and {steps_deleted} steps")
                return True

            logger.warning(f"Run {run_id} not found for deletion")
            return False
        except Exception as e:
            logger.error(f"Failed to delete run {run_id}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with database statistics.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            stats = {}

            # Run counts
            cursor.execute("SELECT COUNT(*) as total FROM runs")
            stats["total_runs"] = cursor.fetchone()["total"]

            cursor.execute(
                "SELECT COUNT(*) as running FROM runs WHERE status = 'running'"
            )
            stats["running_runs"] = cursor.fetchone()["running"]

            cursor.execute(
                "SELECT COUNT(*) as completed FROM runs WHERE status = 'completed'"
            )
            stats["completed_runs"] = cursor.fetchone()["completed"]

            cursor.execute(
                "SELECT COUNT(*) as failed FROM runs WHERE status = 'failed'"
            )
            stats["failed_runs"] = cursor.fetchone()["failed"]

            # Step counts
            cursor.execute("SELECT COUNT(*) as total FROM steps")
            stats["total_steps"] = cursor.fetchone()["total"]

            # Database size
            cursor.execute(
                "SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"
            )
            stats["db_size_bytes"] = cursor.fetchone()["size"]

            # Recent activity
            cursor.execute(
                "SELECT COUNT(*) as recent FROM runs WHERE started_at > ?",
                (int((time.time() - 86400) * 1000),),  # Last 24 hours
            )
            stats["recent_runs_24h"] = cursor.fetchone()["recent"]

            return stats
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}

    def prune_old_runs(self, retention_days: Optional[int] = None) -> int:
        """
        Delete runs older than the retention period.

        Args:
            retention_days: Number of days to retain. If None, uses config.

        Returns:
            Number of runs deleted.
        """
        if retention_days is None:
            retention_days = self.config.retention_days

        if retention_days <= 0:
            logger.info("Pruning disabled (retention_days <= 0)")
            return 0

        try:
            cutoff_time = int(
                (datetime.now() - timedelta(days=retention_days)).timestamp() * 1000
            )

            conn = self._get_connection()
            cursor = conn.cursor()

            # Get count before deletion
            cursor.execute(
                "SELECT COUNT(*) as count FROM runs WHERE started_at < ?",
                (cutoff_time,),
            )
            count = cursor.fetchone()["count"]

            if count == 0:
                logger.info(f"No runs older than {retention_days} days to prune")
                return 0

            # Delete old runs (cascade will delete steps)
            cursor.execute("DELETE FROM runs WHERE started_at < ?", (cutoff_time,))
            conn.commit()

            logger.info(f"Pruned {count} runs older than {retention_days} days")
            return count
        except Exception as e:
            logger.error(f"Failed to prune old runs: {e}")
            return 0

    def vacuum(self) -> bool:
        """
        Run VACUUM to reclaim disk space.

        Returns:
            True if successful, False otherwise.
        """
        try:
            logger.info("Running VACUUM...")
            conn = self._get_connection()
            conn.execute("VACUUM")
            conn.commit()
            logger.info("VACUUM completed")
            return True
        except Exception as e:
            logger.error(f"Failed to run VACUUM: {e}")
            return False

    def backup(self, backup_path: str) -> bool:
        """
        Create a backup of the database.

        Args:
            backup_path: Path where backup should be saved.

        Returns:
            True if successful, False otherwise.
        """
        try:
            logger.info(f"Creating backup to {backup_path}...")
            source = sqlite3.connect(self.db_path)
            dest = sqlite3.connect(backup_path)
            source.backup(dest)
            dest.close()
            source.close()
            logger.info("Backup completed")
            return True
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return False

    def close(self):
        """Close database connection for the current thread."""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
