"""
API auth tests.
"""

from fastapi.testclient import TestClient

from agent_inspector.api.main import APIServer
from agent_inspector.core.config import TraceConfig


class DummyStore:
    def initialize(self):
        return None

    def get_stats(self):
        return {"total_runs": 0}

    def list_runs(self, **_):
        return []

    def get_run(self, run_id):
        return None

    def get_run_steps(self, **_):
        return []

    def get_run_timeline(self, **_):
        return []

    def get_step_data(self, step_id):
        return None


class DummyPipeline:
    def reverse(self, data):
        return {"decoded": True}


def make_client(required: bool, key: str):
    config = TraceConfig()
    config.api_key_required = required
    config.api_key = key
    server = APIServer(config, store=DummyStore(), pipeline=DummyPipeline())
    return TestClient(server.app)


def test_auth_required_missing_key():
    client = make_client(True, "secret")
    resp = client.get("/v1/runs")
    assert resp.status_code == 401


def test_auth_required_bad_key():
    client = make_client(True, "secret")
    resp = client.get("/v1/runs", headers={"x-api-key": "wrong"})
    assert resp.status_code == 403


def test_auth_required_ok():
    client = make_client(True, "secret")
    resp = client.get("/v1/runs", headers={"x-api-key": "secret"})
    assert resp.status_code == 200


def test_auth_required_missing_config():
    config = TraceConfig()
    config.api_key_required = True
    config.api_key = None
    server = APIServer(config, store=DummyStore(), pipeline=DummyPipeline())
    client = TestClient(server.app)
    resp = client.get("/v1/runs", headers={"x-api-key": "anything"})
    assert resp.status_code == 500


def test_stats_auth_required_ok():
    client = make_client(True, "secret")
    resp = client.get("/v1/stats", headers={"x-api-key": "secret"})
    assert resp.status_code == 200
