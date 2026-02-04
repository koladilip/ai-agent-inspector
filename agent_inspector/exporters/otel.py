"""
OpenTelemetry OTLP exporter for Agent Inspector.

Sends trace events to an OTLP-compatible backend (e.g. Jaeger, Tempo, Grafana).
Requires: pip install ai-agent-inspector[otel]

Usage:
    from agent_inspector.exporters.otel import OTLPExporter
    from agent_inspector import Trace

    trace = Trace(exporter=OTLPExporter(endpoint="http://localhost:4318"))
    with trace.run("my_agent"):
        ...
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Optional OpenTelemetry imports
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        import json
        return json.dumps(v, default=str)[:1024]
    return str(v)[:1024]


class OTLPExporter:
    """
    Exporter that sends Agent Inspector events to an OTLP backend as spans.

    Each event becomes one span with name = event type and attributes from
    the event (run_id, event_id, type, etc.). Install with: pip install ai-agent-inspector[otel]
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        service_name: str = "agent-inspector",
    ):
        """
        Args:
            endpoint: OTLP HTTP endpoint (e.g. http://localhost:4318/v1/traces).
                If None, uses OTEL_EXPORTER_OTLP_ENDPOINT or default.
            service_name: Service name for the OTLP resource.
        """
        if not _OTEL_AVAILABLE:
            raise ImportError(
                "OpenTelemetry is required for OTLPExporter. "
                "Install with: pip install ai-agent-inspector[otel]"
            )
        self._endpoint = endpoint
        self._service_name = service_name
        self._provider: Optional[TracerProvider] = None
        self._tracer = None

    def initialize(self) -> None:
        """Create TracerProvider and OTLP exporter."""
        if self._provider is not None:
            return
        kwargs = {}
        if self._endpoint:
            kwargs["endpoint"] = self._endpoint.rstrip("/") + "/v1/traces"
        exporter = OTLPSpanExporter(**kwargs)
        self._provider = TracerProvider()
        self._provider.add_span_processor(BatchSpanProcessor(exporter))
        self._tracer = self._provider.get_tracer(
            "agent-inspector",
            "1.0.0",
            schema_url="https://opentelemetry.io/schemas/1.0.0",
        )
        logger.info("OTLP exporter initialized (endpoint=%s)", self._endpoint or "default")

    def export_batch(self, events: List[Dict[str, Any]]) -> None:
        """Convert each event to a span and export."""
        if not self._tracer:
            self.initialize()
        for ev in events:
            try:
                name = ev.get("type", "event") or "event"
                run_id = ev.get("run_id", "")
                event_id = ev.get("event_id", "")
                with self._tracer.start_as_current_span(name) as span:
                    span.set_attribute("agent_inspector.run_id", run_id)
                    span.set_attribute("agent_inspector.event_id", event_id)
                    if ev.get("timestamp_ms"):
                        span.set_attribute("agent_inspector.timestamp_ms", ev["timestamp_ms"])
                    if ev.get("duration_ms") is not None:
                        span.set_attribute("agent_inspector.duration_ms", ev["duration_ms"])
                    if ev.get("name"):
                        span.set_attribute("agent_inspector.name", _safe_str(ev["name"]))
                    if ev.get("status"):
                        span.set_attribute("agent_inspector.status", _safe_str(ev["status"]))
            except Exception as e:
                logger.warning("OTLP export failed for event %s: %s", ev.get("event_id"), e)

    def shutdown(self) -> None:
        """Shutdown the tracer provider and flush spans."""
        if self._provider:
            try:
                self._provider.shutdown()
            except Exception as e:
                logger.warning("OTLP provider shutdown error: %s", e)
            self._provider = None
            self._tracer = None
