"""
FastAPI REST API module for Agent Inspector.

Provides endpoints for serving trace data to the UI with
authentication, rate limiting, and efficient query performance.
"""

from .main import APIServer, get_api_server, run_server

__all__ = ["APIServer", "get_api_server", "run_server"]
