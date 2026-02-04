"""
Public interfaces for Agent Inspector SDK components.

All protocols in this module define extension points for the tracing library.
Implement these interfaces to plug in custom exporters, samplers, or storage.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import TraceConfig


class Exporter(Protocol):
    """Exporter interface for sending event batches to a backend."""

    def initialize(self) -> None:
        """Initialize exporter resources."""
        ...  # pragma: no cover

    def export_batch(self, events: List[Dict[str, Any]]) -> None:
        """Export a batch of events."""
        ...  # pragma: no cover

    def shutdown(self) -> None:
        """Shutdown exporter and flush resources."""
        ...  # pragma: no cover


class Sampler(Protocol):
    """
    Protocol for run sampling decisions.

    Implement this to control which runs are traced (e.g., rate-based,
    user-based, or deterministic). Pass an implementation to Trace(sampler=...).
    """

    def should_sample(
        self,
        run_id: str,
        run_name: str,
        config: "TraceConfig",
    ) -> bool:
        """
        Return True if this run should be traced, False to skip.

        Args:
            run_id: Unique run identifier.
            run_name: Human-readable run name.
            config: Current trace configuration.

        Returns:
            True to trace this run, False to skip (no-op context is yielded).
        """
        ...  # pragma: no cover


class ReadStore(Protocol):
    """Read-only storage interface used by the API server."""

    def get_stats(self) -> Dict[str, Any]:
        ...  # pragma: no cover

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
        ...  # pragma: no cover

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        ...  # pragma: no cover

    def get_run_steps(
        self,
        run_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        ...  # pragma: no cover

    def get_run_timeline(
        self, run_id: str, include_data: bool = False
    ) -> List[Dict[str, Any]]:
        ...  # pragma: no cover

    def get_step_data(self, step_id: str) -> Optional[bytes]:
        ...  # pragma: no cover
