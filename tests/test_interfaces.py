"""
Protocol usage tests for core interfaces.
"""

from typing import Any, Dict, List, Optional

from agent_inspector.core.interfaces import Exporter, ReadStore


class DummyExporter:
    def initialize(self) -> None:
        return None

    def export_batch(self, events: List[Dict[str, Any]]) -> None:
        return None

    def shutdown(self) -> None:
        return None


class DummyStore:
    def get_stats(self) -> Dict[str, Any]:
        return {"total_runs": 0}

    def list_runs(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        search: Optional[str] = None,
        started_after: Optional[int] = None,
        started_before: Optional[int] = None,
        order_by: str = "started_at",
        order_dir: str = "DESC",
    ) -> List[Dict[str, Any]]:
        return []

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return None

    def get_run_steps(
        self,
        run_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return []

    def get_run_timeline(
        self, run_id: str, include_data: bool = False
    ) -> List[Dict[str, Any]]:
        return []

    def get_step_data(self, step_id: str) -> Optional[bytes]:
        return None


def test_exporter_protocol_usage():
    exporter: Exporter = DummyExporter()
    exporter.initialize()
    exporter.export_batch([])
    exporter.shutdown()


def test_readstore_protocol_usage():
    store: ReadStore = DummyStore()
    store.get_stats()
    store.list_runs()
    store.get_run("x")
    store.get_run_steps("x")
    store.get_run_timeline("x")
    store.get_step_data("x")
