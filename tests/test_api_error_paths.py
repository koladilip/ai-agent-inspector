"""
API error path tests.
"""

from fastapi.testclient import TestClient

from agent_inspector.api.main import APIServer
from agent_inspector.core.config import TraceConfig


class ErrorStore:
    def __init__(self, where: str):
        self.where = where

    def initialize(self):
        return None

    def get_stats(self):
        if self.where == "stats":
            raise RuntimeError("boom")
        return {"total_runs": 0}

    def list_runs(self, **_):
        if self.where == "list":
            raise RuntimeError("boom")
        return []

    def get_run(self, run_id):
        if self.where == "get_run":
            raise RuntimeError("boom")
        # Return a run to allow downstream handlers to execute and hit error paths
        return {"id": run_id}

    def get_run_steps(self, **_):
        if self.where == "steps":
            raise RuntimeError("boom")
        return []

    def get_run_timeline(self, **_):
        if self.where == "timeline":
            raise RuntimeError("boom")
        return []

    def get_step_data(self, step_id):
        if self.where == "step_data":
            raise RuntimeError("boom")
        return None


class DummyPipeline:
    def reverse(self, data):
        return {"decoded": True}


def make_client(where: str):
    config = TraceConfig()
    server = APIServer(config, store=ErrorStore(where), pipeline=DummyPipeline())
    return TestClient(server.app)


def test_health_check_error_returns_503():
    client = make_client("stats")
    resp = client.get("/health")
    assert resp.status_code == 503


def test_list_runs_error_returns_500():
    client = make_client("list")
    resp = client.get("/v1/runs")
    assert resp.status_code == 500


def test_get_run_error_returns_500():
    client = make_client("get_run")
    resp = client.get("/v1/runs/run-1")
    assert resp.status_code == 500


def test_steps_error_returns_500():
    client = make_client("steps")
    resp = client.get("/v1/runs/run-1/steps")
    assert resp.status_code == 500


def test_timeline_error_returns_500():
    client = make_client("timeline")
    resp = client.get("/v1/runs/run-1/timeline")
    assert resp.status_code == 500


def test_step_data_error_returns_500():
    client = make_client("step_data")
    resp = client.get("/v1/runs/run-1/steps/step-1/data")
    assert resp.status_code == 500


def test_stats_error_returns_500():
    client = make_client("stats")
    resp = client.get("/v1/stats")
    assert resp.status_code == 500


def test_get_run_not_found_returns_404():
    class MissingStore(ErrorStore):
        def get_run(self, run_id):
            return None

    config = TraceConfig()
    server = APIServer(config, store=MissingStore("list"), pipeline=DummyPipeline())
    client = TestClient(server.app)
    resp = client.get("/v1/runs/missing")
    assert resp.status_code == 404
