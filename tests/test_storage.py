"""
Tests for Agent Inspector storage module.

Tests SQLite database functionality including:
- Database initialization and schema
- Run operations (insert, update, get, list)
- Step operations (insert, get, get_step_data)
- Timeline queries
- Statistics and maintenance operations
- Error handling
"""

import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

from agent_inspector.core.config import TraceConfig
from agent_inspector.storage.database import Database


class TestDatabaseInitialization:
    """Test database initialization and schema."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            yield f.name

    @pytest.fixture
    def db(self, temp_db):
        """Create a database instance with temporary file."""
        config = TraceConfig(db_path=temp_db)
        db = Database(config)
        db.initialize()
        yield db
        # Cleanup
        if os.path.exists(temp_db):
            os.remove(temp_db)

    def test_database_initialization(self, temp_db):
        """Test that database initializes successfully."""
        config = TraceConfig(db_path=temp_db)
        db = Database(config)
        db.initialize()

        # Database file should be created
        assert os.path.exists(temp_db)

        # Schema version table should exist
        conn = db._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        result = cursor.fetchone()
        assert result is not None

    def test_database_initialize_twice(self, temp_db):
        """Test calling initialize twice is a no-op."""
        config = TraceConfig(db_path=temp_db)
        db = Database(config)
        db.initialize()
        db.initialize()
        assert db._initialized is True

    def test_run_migrations(self, temp_db):
        """Test migrations run when schema version is behind."""
        config = TraceConfig(db_path=temp_db)
        db = Database(config)
        db.initialize()

        conn = db._get_connection()
        conn.execute("UPDATE schema_version SET version = 0")
        conn.commit()

        db.SCHEMA_VERSION = 2
        db._run_migrations(conn)

        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_version")
        result = cursor.fetchone()
        assert result["version"] == 2

    def test_close_without_connection(self, temp_db):
        """Close should be a no-op without a connection."""
        config = TraceConfig(db_path=temp_db)
        db = Database(config)
        db.close()

    def test_schema_version(self, db):
        """Test that schema version is set."""
        conn = db._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT version FROM schema_version")
        result = cursor.fetchone()

        assert result is not None
        assert result["version"] == Database.SCHEMA_VERSION

    def test_runs_table_exists(self, db):
        """Test that runs table exists."""
        conn = db._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='runs'"
        )
        result = cursor.fetchone()

        assert result is not None

    def test_steps_table_exists(self, db):
        """Test that steps table exists."""
        conn = db._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='steps'"
        )
        result = cursor.fetchone()

        assert result is not None

    def test_indexes_exist(self, db):
        """Test that required indexes exist."""
        conn = db._get_connection()
        cursor = conn.cursor()

        # Check for run_id index
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_steps_run_id'"
        )
        result = cursor.fetchone()
        assert result is not None

        # Check for timestamp index
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_steps_timestamp'"
        )
        result = cursor.fetchone()
        assert result is not None


class TestRunOperations:
    """Test database operations on runs."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            yield f.name

    @pytest.fixture
    def db(self, temp_db):
        """Create a database instance with temporary file."""
        config = TraceConfig(db_path=temp_db)
        db = Database(config)
        db.initialize()
        yield db
        if os.path.exists(temp_db):
            os.remove(temp_db)

    def test_insert_run(self, db):
        """Test inserting a new run."""
        run_data = {
            "id": "test-run-1",
            "name": "Test Run",
            "status": "running",
            "started_at": int(time.time() * 1000),
            "agent_type": "custom",
            "user_id": "user123",
            "session_id": "session456",
            "metadata": {"key": "value"},
        }

        result = db.insert_run(run_data)

        assert result is True

        # Verify run was inserted
        run = db.get_run("test-run-1")
        assert run is not None
        assert run["id"] == "test-run-1"
        assert run["name"] == "Test Run"
        assert run["status"] == "running"

    def test_insert_run_with_metadata(self, db):
        """Test inserting a run with metadata."""
        run_data = {
            "id": "test-run-2",
            "name": "Test Run with Metadata",
            "status": "running",
            "started_at": int(time.time() * 1000),
            "metadata": {"custom_field": "custom_value", "number": 42},
        }

        db.insert_run(run_data)

        # Verify metadata was stored
        run = db.get_run("test-run-2")
        assert run is not None
        import json

        metadata = json.loads(run["metadata"])
        assert metadata["custom_field"] == "custom_value"
        assert metadata["number"] == 42

    def test_update_run_status(self, db):
        """Test updating run status."""
        # First insert a run
        run_data = {
            "id": "test-run-3",
            "name": "Test Run",
            "status": "running",
            "started_at": int(time.time() * 1000),
        }

        db.insert_run(run_data)

        # Update status
        result = db.update_run(run_id="test-run-3", status="completed")

        assert result is True

        # Verify update
        run = db.get_run("test-run-3")
        assert run["status"] == "completed"

    def test_update_run_metadata_invalid_json(self, db):
        """Test metadata merge when stored JSON is invalid."""
        run_data = {
            "id": "test-run-invalid-metadata",
            "name": "Test Run",
            "status": "running",
            "started_at": int(time.time() * 1000),
        }
        db.insert_run(run_data)

        conn = db._get_connection()
        conn.execute(
            "UPDATE runs SET metadata = ? WHERE id = ?",
            ("not-json", "test-run-invalid-metadata"),
        )
        conn.commit()

        result = db.update_run(
            run_id="test-run-invalid-metadata", metadata={"new": "value"}
        )
        assert result is True

        updated = db.get_run("test-run-invalid-metadata")
        import json

        merged = json.loads(updated["metadata"])
        assert merged == {"new": "value"}

    def test_update_run_metadata_invalid_json_uses_empty(self, db):
        """Ensure invalid JSON is treated as empty metadata."""
        run_data = {
            "id": "test-run-invalid-metadata-2",
            "name": "Test Run",
            "status": "running",
            "started_at": int(time.time() * 1000),
        }
        db.insert_run(run_data)

        conn = db._get_connection()
        conn.execute(
            "UPDATE runs SET metadata = ? WHERE id = ?",
            ("{", "test-run-invalid-metadata-2"),
        )
        conn.commit()

        db.update_run(run_id="test-run-invalid-metadata-2", metadata={"x": 1})
        run = db.get_run("test-run-invalid-metadata-2")
        import json

        meta = json.loads(run["metadata"])
        assert meta == {"x": 1}

    def test_update_run_no_updates(self, db):
        """Test update_run with no fields to update returns True."""
        assert db.update_run(run_id="missing") is True

    def test_update_run_completion_time(self, db):
        """Test updating run completion information."""
        # Insert run
        start_time = int(time.time() * 1000)
        run_data = {
            "id": "test-run-4",
            "name": "Test Run",
            "status": "running",
            "started_at": start_time,
        }

        db.insert_run(run_data)

        # Simulate run completion
        time.sleep(0.1)
        end_time = int(time.time() * 1000)
        duration_ms = end_time - start_time

        result = db.update_run(
            run_id="test-run-4",
            completed_at=end_time,
            duration_ms=duration_ms,
            status="completed",
        )

        assert result is True

        # Verify update
        run = db.get_run("test-run-4")
        assert run["completed_at"] == end_time
        assert run["duration_ms"] == duration_ms
        assert run["status"] == "completed"

    def test_update_run_metadata_merge(self, db):
        """Test updating run metadata merges JSON."""
        run_data = {
            "id": "test-run-meta",
            "name": "Test Run",
            "status": "running",
            "started_at": int(time.time() * 1000),
            "metadata": {"a": 1},
        }
        db.insert_run(run_data)

        db.update_run(run_id="test-run-meta", metadata={"b": 2})
        run = db.get_run("test-run-meta")
        import json

        meta = json.loads(run["metadata"])
        assert meta.get("a") == 1
        assert meta.get("b") == 2

    def test_update_run_metadata_overwrite(self, db):
        """Metadata keys should be overwritten by updates."""
        run_data = {
            "id": "test-run-meta-over",
            "name": "Test Run",
            "status": "running",
            "started_at": int(time.time() * 1000),
            "metadata": {"a": 1},
        }
        db.insert_run(run_data)
        db.update_run(run_id="test-run-meta-over", metadata={"a": 2})
        run = db.get_run("test-run-meta-over")
        import json

        meta = json.loads(run["metadata"])
        assert meta.get("a") == 2

    def test_get_run(self, db):
        """Test retrieving a run by ID."""
        # Insert a run
        run_data = {
            "id": "test-run-5",
            "name": "Test Run",
            "status": "completed",
            "started_at": int(time.time() * 1000),
            "completed_at": int(time.time() * 1000),
            "duration_ms": 1000,
        }

        db.insert_run(run_data)

        # Retrieve run
        run = db.get_run("test-run-5")

        assert run is not None
        assert run["id"] == "test-run-5"
        assert run["name"] == "Test Run"
        assert run["status"] == "completed"

    def test_get_nonexistent_run(self, db):
        """Test retrieving a non-existent run returns None."""
        run = db.get_run("nonexistent-run-id")

        assert run is None

    def test_list_runs_all(self, db):
        """Test listing all runs."""
        # Insert multiple runs
        for i in range(5):
            run_data = {
                "id": f"test-run-{i}",
                "name": f"Test Run {i}",
                "status": "completed",
                "started_at": int(time.time() * 1000),
                "completed_at": int(time.time() * 1000),
            }

            db.insert_run(run_data)

        # List runs
        runs = db.list_runs(limit=100)

        assert len(runs) == 5
        assert all(run["status"] == "completed" for run in runs)

    def test_list_runs_with_limit(self, db):
        """Test listing runs with limit."""
        # Insert 10 runs
        for i in range(10):
            run_data = {
                "id": f"test-run-{i}",
                "name": f"Test Run {i}",
                "status": "completed",
                "started_at": int(time.time() * 1000),
            }

            db.insert_run(run_data)

        # List with limit
        runs = db.list_runs(limit=3)

        assert len(runs) == 3

    def test_list_runs_with_offset(self, db):
        """Test listing runs with offset."""
        # Insert 5 runs
        for i in range(5):
            run_data = {
                "id": f"test-run-{i}",
                "name": f"Test Run {i}",
                "status": "completed",
                "started_at": int(time.time() * 1000),
            }

            db.insert_run(run_data)

        # List with offset
        runs = db.list_runs(limit=10, offset=2)

        assert len(runs) == 3

    def test_list_runs_with_status_filter(self, db):
        """Test listing runs with status filter."""
        # Insert runs with different statuses
        db.insert_run(
            {
                "id": "run-completed-1",
                "name": "Completed Run",
                "status": "completed",
                "started_at": int(time.time() * 1000),
            }
        )

        db.insert_run(
            {
                "id": "run-running-1",
                "name": "Running Run",
                "status": "running",
                "started_at": int(time.time() * 1000),
            }
        )

        db.insert_run(
            {
                "id": "run-failed-1",
                "name": "Failed Run",
                "status": "failed",
                "started_at": int(time.time() * 1000),
            }
        )

        # Filter by status
        runs = db.list_runs(limit=100, status="completed")

        assert len(runs) == 1
        assert runs[0]["status"] == "completed"

    def test_list_runs_with_user_filter(self, db):
        """Test listing runs with user filter."""
        # Insert runs for different users
        db.insert_run(
            {
                "id": "run-user1-1",
                "name": "User 1 Run",
                "status": "completed",
                "user_id": "user1",
                "started_at": int(time.time() * 1000),
            }
        )

        db.insert_run(
            {
                "id": "run-user2-1",
                "name": "User 2 Run",
                "status": "completed",
                "user_id": "user2",
                "started_at": int(time.time() * 1000),
            }
        )

        # Filter by user
        runs = db.list_runs(limit=100, user_id="user1")

        assert len(runs) == 1
        assert runs[0]["user_id"] == "user1"

    def test_list_runs_with_session_filter(self, db):
        """Test listing runs with session filter."""
        # Insert runs for different sessions
        db.insert_run(
            {
                "id": "run-session1-1",
                "name": "Session 1 Run",
                "status": "completed",
                "session_id": "session1",
                "started_at": int(time.time() * 1000),
            }
        )

        db.insert_run(
            {
                "id": "run-session2-1",
                "name": "Session 2 Run",
                "status": "completed",
                "session_id": "session2",
                "started_at": int(time.time() * 1000),
            }
        )

        # Filter by session
        runs = db.list_runs(limit=100, session_id="session1")

        assert len(runs) == 1
        assert runs[0]["session_id"] == "session1"

    def test_list_runs_with_search(self, db):
        """Test listing runs with search."""
        # Insert runs
        db.insert_run(
            {
                "id": "run-search-1",
                "name": "Flight Search",
                "status": "completed",
                "started_at": int(time.time() * 1000),
            }
        )

        db.insert_run(
            {
                "id": "run-search-2",
                "name": "Hotel Search",
                "status": "completed",
                "started_at": int(time.time() * 1000),
            }
        )

        # Search for "Flight"
        runs = db.list_runs(limit=100, search="Flight")

        assert len(runs) == 1
        assert "Flight" in runs[0]["name"]

    def test_list_runs_with_search_no_match(self, db):
        """Search with no matches returns empty list."""
        runs = db.list_runs(search="NoMatchHere")
        assert runs == []

    def test_list_runs_with_ordering(self, db):
        """Test listing runs with custom ordering."""
        # Insert runs at different times
        now = int(time.time() * 1000)
        for i in range(3):
            db.insert_run(
                {
                    "id": f"run-order-{i}",
                    "name": f"Run {i}",
                    "status": "completed",
                    "started_at": now - (2 - i) * 1000,
                }
            )

        # Order by started_at ascending
        runs = db.list_runs(limit=100, order_by="started_at", order_dir="ASC")

        assert len(runs) == 3
        assert runs[0]["started_at"] < runs[1]["started_at"]
        assert runs[1]["started_at"] < runs[2]["started_at"]

    def test_list_runs_with_invalid_order_by(self, db):
        """Invalid order_by should not crash and should return runs."""
        db.insert_run(
            {
                "id": "run-invalid-order",
                "name": "Run",
                "status": "completed",
                "started_at": int(time.time() * 1000),
            }
        )
        runs = db.list_runs(order_by="bad_field")
        assert len(runs) >= 1


class TestStepOperations:
    """Test database operations on steps."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            yield f.name

    @pytest.fixture
    def db(self, temp_db):
        """Create a database instance with temporary file."""
        config = TraceConfig(db_path=temp_db)
        db = Database(config)
        db.initialize()
        yield db
        if os.path.exists(temp_db):
            os.remove(temp_db)

    @pytest.fixture
    def sample_run(self, db):
        """Create a sample run for step tests."""
        run_data = {
            "id": "sample-run",
            "name": "Sample Run",
            "status": "running",
            "started_at": int(time.time() * 1000),
        }

        db.insert_run(run_data)
        return "sample-run"

    def test_insert_steps_batch(self, db, sample_run):
        """Test inserting a batch of steps."""
        import json

        # Create sample events
        events = []
        for i in range(5):
            event = {
                "event_id": f"step-{i}",
                "run_id": sample_run,
                "timestamp_ms": int(time.time() * 1000),
                "type": "llm_call",
                "name": f"LLM Call {i}",
                "status": "completed",
                "duration_ms": 100 + i * 10,
                "model": f"gpt-{i}",
            }

            event_bytes = json.dumps(event).encode("utf-8")
            events.append((event, event_bytes))

        # Insert batch
        result = db.insert_steps(events)

        assert result == 5

        # Verify steps were inserted
        steps = db.get_run_steps(sample_run)
        assert len(steps) == 5

    def test_insert_steps_empty(self, db):
        """Test inserting an empty step batch returns 0."""
        assert db.insert_steps([]) == 0

    def test_get_run_steps_all(self, db, sample_run):
        """Test getting all steps for a run."""
        # Insert steps
        import json

        events = []
        for i in range(3):
            event = {
                "event_id": f"step-{i}",
                "run_id": sample_run,
                "timestamp_ms": int(time.time() * 1000),
                "type": "tool_call",
                "name": f"Tool Call {i}",
            }

            event_bytes = json.dumps(event).encode("utf-8")
            events.append((event, event_bytes))

        db.insert_steps(events)

        # Get all steps
        steps = db.get_run_steps(sample_run)

        assert len(steps) == 3
        assert all(step["run_id"] == sample_run for step in steps)

    def test_get_run_steps_ordering(self, db, sample_run):
        """Steps should be ordered by timestamp ASC."""
        import json

        events = [
            {"event_id": "s1", "run_id": sample_run, "timestamp_ms": 5, "type": "tool_call"},
            {"event_id": "s2", "run_id": sample_run, "timestamp_ms": 1, "type": "tool_call"},
            {"event_id": "s3", "run_id": sample_run, "timestamp_ms": 3, "type": "tool_call"},
        ]
        for event in events:
            db.insert_steps([(event, json.dumps(event).encode("utf-8"))])

        steps = db.get_run_steps(sample_run)
        timestamps = [step["timestamp"] for step in steps]
        assert timestamps == sorted(timestamps)

    def test_get_run_steps_with_limit(self, db, sample_run):
        """Test getting steps with limit."""
        import json

        # Insert 5 steps
        events = []
        for i in range(5):
            event = {
                "event_id": f"step-{i}",
                "run_id": sample_run,
                "timestamp_ms": int(time.time() * 1000),
                "type": "llm_call",
            }

            event_bytes = json.dumps(event).encode("utf-8")
            events.append((event, event_bytes))

        db.insert_steps(events)

        # Get with limit
        steps = db.get_run_steps(sample_run, limit=2)

        assert len(steps) == 2

    def test_get_run_steps_with_offset(self, db, sample_run):
        """Test getting steps with offset."""
        import json

        # Insert steps
        events = []
        for i in range(5):
            event = {
                "event_id": f"step-{i}",
                "run_id": sample_run,
                "timestamp_ms": int(time.time() * 1000),
                "type": "tool_call",
            }

            event_bytes = json.dumps(event).encode("utf-8")
            events.append((event, event_bytes))

        db.insert_steps(events)

        # Get with offset
        steps = db.get_run_steps(sample_run, limit=10, offset=2)

        assert len(steps) == 3

    def test_get_run_steps_with_type_filter(self, db, sample_run):
        """Test getting steps filtered by type."""
        import json

        # Insert different event types
        events = []

        # Add llm_call events
        for i in range(2):
            event = {
                "event_id": f"llm-{i}",
                "run_id": sample_run,
                "timestamp_ms": int(time.time() * 1000),
                "type": "llm_call",
            }

            event_bytes = json.dumps(event).encode("utf-8")
            events.append((event, event_bytes))

        # Add tool_call events
        for i in range(2):
            event = {
                "event_id": f"tool-{i}",
                "run_id": sample_run,
                "timestamp_ms": int(time.time() * 1000),
                "type": "tool_call",
            }

            event_bytes = json.dumps(event).encode("utf-8")
            events.append((event, event_bytes))

        db.insert_steps(events)

        # Filter by llm_call type
        steps = db.get_run_steps(sample_run, event_type="llm_call")

        assert len(steps) == 2
        assert all(step["type"] == "llm_call" for step in steps)

    def test_get_step_data(self, db, sample_run):
        """Test getting raw step data."""
        import json

        # Insert a step
        event = {
            "event_id": "test-step",
            "run_id": sample_run,
            "timestamp_ms": int(time.time() * 1000),
            "type": "memory_read",
            "data": {"key": "value"},
        }

        event_bytes = json.dumps(event).encode("utf-8")
        db.insert_steps([(event, event_bytes)])

        # Get step data
        data = db.get_step_data("test-step")

        assert data is not None
        assert isinstance(data, bytes)


class TestTimelineQueries:
    """Test timeline query operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            yield f.name

    @pytest.fixture
    def db(self, temp_db):
        """Create a database instance with temporary file."""
        config = TraceConfig(db_path=temp_db)
        db = Database(config)
        db.initialize()
        yield db
        if os.path.exists(temp_db):
            os.remove(temp_db)

    @pytest.fixture
    def sample_run(self, db):
        """Create a sample run with steps."""
        run_data = {
            "id": "timeline-run",
            "name": "Timeline Test Run",
            "status": "completed",
            "started_at": int(time.time() * 1000),
        }

        db.insert_run(run_data)

        # Insert steps
        import json

        events = []
        for i in range(5):
            event = {
                "event_id": f"timeline-step-{i}",
                "run_id": "timeline-run",
                "timestamp_ms": int(time.time() * 1000),
                "type": "llm_call",
                "name": f"Event {i}",
                "status": "completed",
            }

            event_bytes = json.dumps(event).encode("utf-8")
            events.append((event, event_bytes))

        db.insert_steps(events)

        return "timeline-run"

    def test_get_run_timeline(self, db, sample_run):
        """Test getting timeline for a run."""
        timeline = db.get_run_timeline(sample_run, include_data=False)

        assert timeline is not None
        assert isinstance(timeline, list)
        assert len(timeline) > 0

        # Check events are ordered
        timestamps = [event["timestamp"] for event in timeline]
        assert timestamps == sorted(timestamps)

    def test_get_run_timeline_ordering(self, db):
        """Timeline should be ordered by timestamp ASC."""
        import json

        run_id = "timeline-order"
        db.insert_run(
            {
                "id": run_id,
                "name": "Timeline Order",
                "status": "completed",
                "started_at": 1,
            }
        )
        events = [
            {"event_id": "t1", "run_id": run_id, "timestamp_ms": 5, "type": "llm_call"},
            {"event_id": "t2", "run_id": run_id, "timestamp_ms": 1, "type": "llm_call"},
            {"event_id": "t3", "run_id": run_id, "timestamp_ms": 3, "type": "llm_call"},
        ]
        for event in events:
            db.insert_steps([(event, json.dumps(event).encode("utf-8"))])

        timeline = db.get_run_timeline(run_id)
        timestamps = [event["timestamp"] for event in timeline]
        assert timestamps == sorted(timestamps)

    def test_get_run_timeline_with_data(self, db, sample_run):
        """Test getting timeline with full data."""
        timeline = db.get_run_timeline(sample_run, include_data=True)

        assert timeline is not None
        assert isinstance(timeline, list)
        assert len(timeline) > 0

        # Should have data field when include_data=True
        assert "data" in timeline[0]

    def test_get_run_timeline_nonexistent(self, db):
        """Test getting timeline for non-existent run."""
        timeline = db.get_run_timeline("nonexistent-run")

        assert timeline is not None
        assert isinstance(timeline, list)
        assert len(timeline) == 0


class TestStatistics:
    """Test statistics operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            yield f.name

    @pytest.fixture
    def db(self, temp_db):
        """Create a database instance with temporary file."""
        config = TraceConfig(db_path=temp_db)
        db = Database(config)
        db.initialize()
        yield db
        if os.path.exists(temp_db):
            os.remove(temp_db)

    def test_get_stats_empty(self, db):
        """Test getting statistics from empty database."""
        stats = db.get_stats()

        assert stats is not None
        assert stats["total_runs"] == 0
        assert stats["running_runs"] == 0
        assert stats["completed_runs"] == 0
        assert stats["failed_runs"] == 0
        assert stats["total_steps"] == 0

    def test_get_stats_with_data(self, db):
        """Test getting statistics with data."""
        # Insert runs with different statuses
        db.insert_run(
            {
                "id": "stats-run-1",
                "name": "Completed Run",
                "status": "completed",
                "started_at": int(time.time() * 1000),
            }
        )

        db.insert_run(
            {
                "id": "stats-run-2",
                "name": "Running Run",
                "status": "running",
                "started_at": int(time.time() * 1000),
            }
        )

        db.insert_run(
            {
                "id": "stats-run-3",
                "name": "Failed Run",
                "status": "failed",
                "started_at": int(time.time() * 1000),
            }
        )

        # Insert a step
        import json

        event = {
            "event_id": "stats-step-1",
            "run_id": "stats-run-1",
            "timestamp_ms": int(time.time() * 1000),
            "type": "llm_call",
        }

        event_bytes = json.dumps(event).encode("utf-8")
        db.insert_steps([(event, event_bytes)])

        # Get stats
        stats = db.get_stats()

        assert stats["total_runs"] == 3
        assert stats["completed_runs"] == 1
        assert stats["running_runs"] == 1
        assert stats["failed_runs"] == 1
        assert stats["total_steps"] == 1
        assert stats["db_size_bytes"] > 0

    def test_get_stats_failure(self, db, monkeypatch):
        """Test get_stats failure path."""
        class DummyConn:
            def cursor(self):
                raise RuntimeError("boom")

        monkeypatch.setattr(db, "_get_connection", lambda: DummyConn())
        assert db.get_stats() == {}


class TestMaintenanceOperations:
    """Test maintenance operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            yield f.name

    @pytest.fixture
    def db(self, temp_db):
        """Create a database instance with temporary file."""
        config = TraceConfig(db_path=temp_db, retention_days=30)
        db = Database(config)
        db.initialize()
        yield db
        if os.path.exists(temp_db):
            os.remove(temp_db)

    def test_prune_old_runs(self, db):
        """Test pruning old runs."""
        # Insert old run
        old_time = int((time.time() - 40 * 86400) * 1000)  # 40 days ago

        db.insert_run(
            {
                "id": "old-run",
                "name": "Old Run",
                "status": "completed",
                "started_at": old_time,
            }
        )

        # Insert recent run
        db.insert_run(
            {
                "id": "recent-run",
                "name": "Recent Run",
                "status": "completed",
                "started_at": int(time.time() * 1000),
            }
        )

        # Prune with 30 day retention
        deleted_count = db.prune_old_runs(retention_days=30)

        assert deleted_count == 1

        # Verify only old run was deleted
        old_run = db.get_run("old-run")
        assert old_run is None

        recent_run = db.get_run("recent-run")
        assert recent_run is not None

    def test_prune_no_old_runs(self, db):
        """Test pruning when no old runs exist."""
        # Insert recent run only
        db.insert_run(
            {
                "id": "recent-run",
                "name": "Recent Run",
                "status": "completed",
                "started_at": int(time.time() * 1000),
            }
        )

        # Prune
        deleted_count = db.prune_old_runs(retention_days=30)

        assert deleted_count == 0

        # Verify recent run still exists
        recent_run = db.get_run("recent-run")
        assert recent_run is not None

    def test_prune_with_zero_retention(self, db):
        """Test pruning with zero retention (no pruning)."""
        # Insert a run
        db.insert_run(
            {
                "id": "test-run",
                "name": "Test Run",
                "status": "completed",
                "started_at": int(time.time() * 1000),
            }
        )

        # Prune with zero retention
        deleted_count = db.prune_old_runs(retention_days=0)

        assert deleted_count == 0

    def test_prune_with_negative_retention(self, db):
        """Test pruning with negative retention (disabled)."""
        deleted_count = db.prune_old_runs(retention_days=-1)
        assert deleted_count == 0

    def test_prune_uses_config_retention(self, db):
        """Test pruning uses config retention when not provided."""
        old_time = int((time.time() - 40 * 86400) * 1000)
        db.insert_run(
            {
                "id": "old-run-config",
                "name": "Old Run",
                "status": "completed",
                "started_at": old_time,
            }
        )
        deleted_count = db.prune_old_runs()
        assert deleted_count == 1

    def test_vacuum(self, db):
        """Test vacuum operation."""
        # Insert some data
        db.insert_run(
            {
                "id": "vacuum-run",
                "name": "Vacuum Test Run",
                "status": "completed",
                "started_at": int(time.time() * 1000),
            }
        )

        # Vacuum
        result = db.vacuum()

        assert result is True

    def test_vacuum_failure(self, db, monkeypatch):
        """Test vacuum failure path."""
        class DummyConn:
            def execute(self, *_args, **_kwargs):
                raise RuntimeError("vacuum failed")

            def commit(self):
                return None

        monkeypatch.setattr(db, "_get_connection", lambda: DummyConn())
        assert db.vacuum() is False

    def test_backup(self, db):
        """Test database backup."""
        # Insert test data
        db.insert_run(
            {
                "id": "backup-run",
                "name": "Backup Test Run",
                "status": "completed",
                "started_at": int(time.time() * 1000),
            }
        )

        # Create backup
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            backup_path = f.name

        result = db.backup(backup_path)

        assert result is True

        # Verify backup was created
        assert os.path.exists(backup_path)

        # Cleanup
        os.remove(backup_path)

    def test_backup_failure(self, db, monkeypatch):
        """Test backup failure path."""
        def _boom(*_args, **_kwargs):
            raise RuntimeError("backup failed")

        monkeypatch.setattr("sqlite3.connect", _boom)
        assert db.backup("dummy.db") is False

    def test_close_clears_connection(self, db):
        """Test closing the database connection."""
        conn = db._get_connection()
        assert db._local.connection is conn
        db.close()
        assert db._local.connection is None

    def test_delete_run(self, db):
        """Test deleting a run."""
        # Insert a run with steps
        run_data = {
            "id": "delete-run",
            "name": "Delete Test Run",
            "status": "completed",
            "started_at": int(time.time() * 1000),
        }

        db.insert_run(run_data)

        # Insert steps
        import json

        events = []
        for i in range(3):
            event = {
                "event_id": f"delete-step-{i}",
                "run_id": "delete-run",
                "timestamp_ms": int(time.time() * 1000),
                "type": "llm_call",
            }

            event_bytes = json.dumps(event).encode("utf-8")
            events.append((event, event_bytes))

        db.insert_steps(events)

        # Delete run
        result = db.delete_run("delete-run")

        assert result is True

        # Verify run was deleted
        run = db.get_run("delete-run")
        assert run is None

        # Verify steps were deleted (cascade)
        steps = db.get_run_steps("delete-run")
        assert len(steps) == 0

    def test_delete_nonexistent_run(self, db):
        """Test deleting non-existent run."""
        result = db.delete_run("nonexistent-run")

        assert result is False


class TestErrorHandling:
    """Test error handling in database operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            yield f.name

    @pytest.fixture
    def db(self, temp_db):
        """Create a database instance with temporary file."""
        config = TraceConfig(db_path=temp_db)
        db = Database(config)
        db.initialize()
        yield db
        if os.path.exists(temp_db):
            os.remove(temp_db)

    def test_insert_run_failure(self, db, monkeypatch):
        """Test insert_run failure path."""
        class DummyConn:
            def execute(self, *_args, **_kwargs):
                raise RuntimeError("insert failed")

            def commit(self):
                return None

        monkeypatch.setattr(db, "_get_connection", lambda: DummyConn())
        assert db.insert_run({"id": "x", "name": "y", "started_at": 1}) is False

    def test_update_run_failure(self, db, monkeypatch):
        """Test update_run failure path."""
        class DummyConn:
            def execute(self, *_args, **_kwargs):
                raise RuntimeError("update failed")

            def commit(self):
                return None

        monkeypatch.setattr(db, "_get_connection", lambda: DummyConn())
        assert db.update_run(run_id="x", status="completed") is False

    def test_insert_steps_failure(self, db, monkeypatch):
        """Test insert_steps failure path."""
        class DummyConn:
            def executemany(self, *_args, **_kwargs):
                raise RuntimeError("insert steps failed")

            def commit(self):
                return None

        monkeypatch.setattr(db, "_get_connection", lambda: DummyConn())
        event = {"event_id": "e", "run_id": "r", "timestamp_ms": 1, "type": "llm_call"}
        assert db.insert_steps([(event, b"data")]) == 0

    def test_get_nonexistent_run_returns_none(self, db):
        """Test getting non-existent run returns None."""
        run = db.get_run("nonexistent-id")

        assert run is None

    def test_get_nonexistent_step_data_returns_none(self, db):
        """Test getting non-existent step data returns None."""
        data = db.get_step_data("nonexistent-step-id")

        assert data is None

    def test_list_runs_with_invalid_filter(self, db):
        """Test listing runs with filters works with no matches."""
        runs = db.list_runs(limit=100, status="invalid_status")

        assert isinstance(runs, list)
        assert len(runs) == 0

    def test_get_run_failure(self, db, monkeypatch):
        """Test get_run failure path."""
        class DummyConn:
            def cursor(self):
                raise RuntimeError("boom")

        monkeypatch.setattr(db, "_get_connection", lambda: DummyConn())
        assert db.get_run("x") is None

    def test_list_runs_failure(self, db, monkeypatch):
        """Test list_runs failure path."""
        class DummyConn:
            def cursor(self):
                raise RuntimeError("boom")

        monkeypatch.setattr(db, "_get_connection", lambda: DummyConn())
        assert db.list_runs() == []

    def test_get_run_steps_failure(self, db, monkeypatch):
        """Test get_run_steps failure path."""
        class DummyConn:
            def cursor(self):
                raise RuntimeError("boom")

        monkeypatch.setattr(db, "_get_connection", lambda: DummyConn())
        assert db.get_run_steps("run") == []

    def test_get_run_timeline_failure(self, db, monkeypatch):
        """Test get_run_timeline failure path."""
        class DummyConn:
            def cursor(self):
                raise RuntimeError("boom")

        monkeypatch.setattr(db, "_get_connection", lambda: DummyConn())
        assert db.get_run_timeline("run") == []

    def test_get_step_data_failure(self, db, monkeypatch):
        """Test get_step_data failure path."""
        class DummyConn:
            def cursor(self):
                raise RuntimeError("boom")

        monkeypatch.setattr(db, "_get_connection", lambda: DummyConn())
        assert db.get_step_data("step") is None

    def test_delete_run_failure(self, db, monkeypatch):
        """Test delete_run failure path."""
        class DummyConn:
            def cursor(self):
                raise RuntimeError("boom")

        monkeypatch.setattr(db, "_get_connection", lambda: DummyConn())
        assert db.delete_run("run") is False

    def test_prune_old_runs_failure(self, db, monkeypatch):
        """Test prune_old_runs failure path."""
        class DummyConn:
            def cursor(self):
                raise RuntimeError("boom")

        monkeypatch.setattr(db, "_get_connection", lambda: DummyConn())
        assert db.prune_old_runs(retention_days=1) == 0

    def test_delete_nonexistent_run(self, db):
        """Test deleting non-existent run returns False."""
        result = db.delete_run("nonexistent-run")

        assert result is False

    def test_concurrent_operations(self, temp_db):
        """Test that concurrent operations work correctly."""
        import threading

        config = TraceConfig(db_path=temp_db)
        db1 = Database(config)
        db1.initialize()

        db2 = Database(config)

        # Insert from multiple threads
        def insert_run(db, run_id):
            run_data = {
                "id": run_id,
                "name": f"Thread Run {run_id}",
                "status": "running",
                "started_at": int(time.time() * 1000),
            }

            db.insert_run(run_data)

        threads = []
        for i in range(10):
            t = threading.Thread(target=insert_run, args=(db1, f"thread-run-{i}"))
            t.start()
            threads.append(t)

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Verify all runs were inserted
        runs = db1.list_runs(limit=100)

        assert len(runs) >= 10
