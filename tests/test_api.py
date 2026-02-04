"""
Tests for API server with injected store/pipeline.
"""

from typing import Any, Dict, List, Optional

from fastapi.testclient import TestClient

from agent_inspector.api.main import APIServer
from agent_inspector.core.config import TraceConfig


class FakeStore:
    def __init__(self):
        self._runs = [
            {
                "id": "run-1",
                "name": "Test Run",
                "status": "completed",
                "started_at": 1000,
                "completed_at": 2000,
                "duration_ms": 1000,
                "agent_type": "custom",
                "user_id": "user123",
                "session_id": "session123",
                "metadata": "{}",
                "created_at": "2026-02-04 00:00:00",
            }
        ]

    def get_stats(self) -> Dict[str, Any]:
        return {"total_runs": 1}

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
        return self._runs

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self._runs[0] if run_id == "run-1" else None

    def get_run_steps(
        self,
        run_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if run_id != "run-1":
            return []
        return [
            {
                "id": "step-1",
                "run_id": "run-1",
                "timestamp": 1000,
                "type": "llm_call",
                "name": "LLM Call",
                "status": "completed",
                "duration_ms": 10,
                "data": b'{"test": "data"}',
            }
        ]

    def get_run_timeline(self, run_id: str, include_data: bool = False):
        if run_id != "run-1":
            return []
        return [
            {
                "id": "step-1",
                "run_id": "run-1",
                "timestamp": 1000,
                "type": "llm_call",
                "name": "LLM Call",
                "status": "completed",
                "duration_ms": 10,
                "data": b'{"test": "data"}' if include_data else None,
            }
        ]

    def get_step_data(self, step_id: str) -> Optional[bytes]:
        return b'{"test": "data"}' if step_id == "step-1" else None


class FakePipeline:
    def reverse(self, data: bytes):
        return {"decoded": True}


def make_client():
    config = TraceConfig()
    server = APIServer(config, store=FakeStore(), pipeline=FakePipeline())
    return TestClient(server.app)


def test_root_redirect():
    client = make_client()
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/ui/"


def test_runs_list():
    client = make_client()
    response = client.get("/v1/runs")
    assert response.status_code == 200
    body = response.json()
    assert body["runs"][0]["id"] == "run-1"


def test_run_steps_decode():
    client = make_client()
    response = client.get("/v1/runs/run-1/steps")
    assert response.status_code == 200
    body = response.json()
    assert body["steps"][0]["data"] == {"decoded": True}


def test_step_data_decode():
    client = make_client()
    response = client.get("/v1/runs/run-1/steps/step-1/data")
    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {"decoded": True}


def test_static_assets_served():
    client = make_client()
    response = client.get("/ui/static/app.css")
    assert response.status_code == 200
    assert "body" in response.text


def test_ui_index_served():
    client = make_client()
    response = client.get("/ui/")
    assert response.status_code == 200
    assert "<title>Agent Inspector</title>" in response.text


def test_root_redirect_followed():
    client = make_client()
    response = client.get("/", follow_redirects=True)
    assert response.status_code == 200
    assert "<title>Agent Inspector</title>" in response.text


def test_api_server_run_uses_defaults(monkeypatch):
    config = TraceConfig(api_host="127.0.0.2", api_port=12345, log_level="INFO")
    server = APIServer(config, store=FakeStore(), pipeline=FakePipeline())
    called = {}

    def _fake_run(app, host, port, log_level):
        called["host"] = host
        called["port"] = port
        called["log_level"] = log_level

    monkeypatch.setattr("agent_inspector.api.main.uvicorn.run", _fake_run)
    server.run()
    assert called == {"host": "127.0.0.2", "port": 12345, "log_level": "info"}


def test_run_server_delegates(monkeypatch):
    from agent_inspector.api import main as api_main

    api_main._api_app = None
    called = {}

    def _fake_run(app, host, port, log_level):
        called["host"] = host
        called["port"] = port
        called["log_level"] = log_level

    monkeypatch.setattr("agent_inspector.api.main.uvicorn.run", _fake_run)
    api_main.run_server(host="0.0.0.0", port=9999)
    assert called == {"host": "0.0.0.0", "port": 9999, "log_level": "info"}


def test_stats_endpoint():
    client = make_client()
    response = client.get("/v1/stats")
    assert response.status_code == 200
    body = response.json()
    assert "total_runs" in body


def test_health_endpoint():
    client = make_client()
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("healthy", "unhealthy")


def test_runs_query_validation():
    client = make_client()
    response = client.get("/v1/runs?limit=0")
    assert response.status_code == 422


def test_runs_order_dir_validation():
    client = make_client()
    response = client.get("/v1/runs?order_dir=BAD")
    assert response.status_code == 422


def test_runs_search_filter():
    client = make_client()
    response = client.get("/v1/runs?search=Test")
    assert response.status_code == 200
    body = response.json()
    assert any("Test" in run["name"] for run in body["runs"])


def test_runs_order_by_invalid_ignored():
    client = make_client()
    response = client.get("/v1/runs?order_by=invalid")
    assert response.status_code == 200


def test_runs_pagination():
    client = make_client()
    response = client.get("/v1/runs?limit=1&offset=0")
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 1
    assert body["offset"] == 0


def test_runs_status_filter():
    client = make_client()
    response = client.get("/v1/runs?run_status=completed")
    assert response.status_code == 200
    body = response.json()
    assert all(run["status"] == "completed" for run in body["runs"])


def test_runs_user_filter():
    client = make_client()
    response = client.get("/v1/runs?user_id=user123")
    assert response.status_code == 200
    body = response.json()
    assert all(run["user_id"] == "user123" for run in body["runs"])


def test_runs_session_filter():
    client = make_client()
    response = client.get("/v1/runs?session_id=session123")
    assert response.status_code == 200
    body = response.json()
    assert all(run["session_id"] == "session123" for run in body["runs"])


def test_runs_order_by_name():
    client = make_client()
    response = client.get("/v1/runs?order_by=name&order_dir=ASC")
    assert response.status_code == 200


def test_get_run_not_found():
    client = make_client()
    response = client.get("/v1/runs/missing")
    assert response.status_code == 404


def test_get_run_metadata_parsed():
    client = make_client()
    response = client.get("/v1/runs/run-1")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body.get("metadata"), dict)


def test_steps_run_not_found():
    client = make_client()
    response = client.get("/v1/runs/missing/steps")
    assert response.status_code == 404


def test_steps_event_type_filter_param():
    client = make_client()
    response = client.get("/v1/runs/run-1/steps?event_type=llm_call")
    assert response.status_code == 200


def test_timeline_run_not_found():
    client = make_client()
    response = client.get("/v1/runs/missing/timeline")
    assert response.status_code == 404


def test_step_data_run_not_found():
    client = make_client()
    response = client.get("/v1/runs/missing/steps/step-1/data")
    assert response.status_code == 404


def test_timeline_include_data_true():
    client = make_client()
    response = client.get("/v1/runs/run-1/timeline?include_data=true")
    assert response.status_code == 200
    body = response.json()
    assert body["events"][0]["data"] == {"decoded": True}



def test_missing_run_returns_404():
    client = make_client()
    response = client.get("/v1/runs/missing")
    assert response.status_code == 404


def test_missing_step_returns_404():
    client = make_client()
    response = client.get("/v1/runs/run-1/steps/missing/data")
    assert response.status_code == 404


def test_bad_timeline_decode_returns_null_data():
    class BadPipeline:
        def reverse(self, data):
            raise RuntimeError("bad")

    config = TraceConfig()
    server = APIServer(config, store=FakeStore(), pipeline=BadPipeline())
    client = TestClient(server.app)

    response = client.get("/v1/runs/run-1/timeline?include_data=true")
    assert response.status_code == 200
    body = response.json()
    assert body["events"][0]["data"] is None


def test_bad_steps_decode_returns_null_data():
    class BadPipeline:
        def reverse(self, data):
            raise RuntimeError("bad")

    config = TraceConfig()
    server = APIServer(config, store=FakeStore(), pipeline=BadPipeline())
    client = TestClient(server.app)

    response = client.get("/v1/runs/run-1/steps")
    assert response.status_code == 200
    body = response.json()
    assert body["steps"][0]["data"] is None
