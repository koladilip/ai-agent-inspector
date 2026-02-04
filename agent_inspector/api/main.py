"""
FastAPI REST API server for Agent Inspector.

Provides endpoints for serving trace data to the UI with
authentication, rate limiting, and efficient query performance.
"""

import hmac
import logging
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from ..core.config import TraceConfig, get_config
from ..core.interfaces import ReadStore
from ..processing.pipeline import ProcessingPipeline
from ..ui.app import setup_ui
from ..storage.database import Database

logger = logging.getLogger(__name__)

# Global instances
_api_app: Optional["APIServer"] = None
_database: Optional[Database] = None
_pipeline: Optional[ProcessingPipeline] = None


class APIServer:
    """
    FastAPI REST API server for Agent Inspector.

    Serves trace data through REST endpoints with authentication,
    rate limiting, and efficient query performance.
    """

    def __init__(
        self,
        config: TraceConfig,
        store: Optional[ReadStore] = None,
        pipeline: Optional[ProcessingPipeline] = None,
    ):
        """
        Initialize the API server.

        Args:
            config: TraceConfig instance with API configuration.
        """
        self.config = config
        self.app = FastAPI(
            title="Agent Inspector API",
            description="Framework-agnostic observability for AI agents",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc",
        )

        # Initialize components
        self._database = store or Database(config)
        self._pipeline = pipeline or ProcessingPipeline(config)

        # Setup middleware
        self._setup_middleware()

        # Setup routes
        self._setup_routes()

        # Setup UI routes
        if self.config.ui_enabled:
            setup_ui(self.app)

        # Initialize database if available
        if hasattr(self._database, "initialize"):
            self._database.initialize()

        logger.info("API server initialized")

    def _setup_middleware(self):
        """Setup CORS and other middleware."""
        origins = self.config.api_cors_origins
        logger.debug(f"Configuring CORS with origins: {origins}")

        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self):
        """Setup API routes."""

        @self.app.get("/")
        async def root_redirect():
            """Redirect root to the UI."""
            return RedirectResponse(url="/ui/")

        @self.app.get("/health")
        async def health_check():
            """
            Health check endpoint.

            Returns:
                Status of the API server and database.
            """
            try:
                # Check database connection
                stats = self._database.get_stats()
                is_healthy = bool(stats)

                return {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "timestamp": int(time.time() * 1000),
                }
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Service unavailable",
                )

        @self.app.get("/v1/stats")
        async def get_stats(
            x_api_key: Optional[str] = Header(None),
        ):
            """
            Get database statistics.

            Args:
                x_api_key: API key for authentication (if required).

            Returns:
                Database statistics including run counts and storage size.
            """
            self._check_auth(x_api_key)

            try:
                stats = self._database.get_stats()
                return stats
            except Exception as e:
                logger.error(f"Failed to get stats: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve statistics",
                )

        @self.app.get("/v1/runs")
        async def list_runs(
            limit: int = Query(
                100, ge=1, le=1000, description="Maximum number of runs to return"
            ),
            offset: int = Query(0, ge=0, description="Number of runs to skip"),
            run_status: Optional[str] = Query(
                None, description="Filter by status (running, completed, failed)"
            ),
            user_id: Optional[str] = Query(None, description="Filter by user ID"),
            session_id: Optional[str] = Query(None, description="Filter by session ID"),
            search: Optional[str] = Query(None, description="Search in run name"),
            order_by: str = Query("started_at", description="Field to order by"),
            order_dir: str = Query(
                "DESC", pattern="^(ASC|DESC)$", description="Order direction"
            ),
            x_api_key: Optional[str] = Header(None),
        ):
            """
            List runs with filtering and pagination.

            Args:
                limit: Maximum number of runs to return.
                offset: Number of runs to skip.
                run_status: Filter by status.
                user_id: Filter by user ID.
                session_id: Filter by session ID.
                search: Search in run name.
                order_by: Field to order by.
                order_dir: Order direction (ASC or DESC).
                x_api_key: API key for authentication.

            Returns:
                List of runs matching the filters.
            """
            self._check_auth(x_api_key)

            try:
                runs = self._database.list_runs(
                    limit=limit,
                    offset=offset,
                    status=run_status,
                    user_id=user_id,
                    session_id=session_id,
                    search=search,
                    order_by=order_by,
                    order_dir=order_dir,
                )

                return {
                    "runs": runs,
                    "total": len(runs),
                    "limit": limit,
                    "offset": offset,
                }
            except Exception as e:
                logger.error(f"Failed to list runs: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve runs",
                )

        @self.app.get("/v1/runs/{run_id}")
        async def get_run(
            run_id: str,
            x_api_key: Optional[str] = Header(None),
        ):
            """
            Get details for a specific run.

            Args:
                run_id: ID of the run.
                x_api_key: API key for authentication.

            Returns:
                Run details including metadata and status.
            """
            self._check_auth(x_api_key)

            try:
                run = self._database.get_run(run_id)
                if not run:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Run {run_id} not found",
                    )

                # Parse metadata if it's a string
                if isinstance(run.get("metadata"), str):
                    import json

                    run["metadata"] = json.loads(run["metadata"])

                return run
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to get run {run_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve run details",
                )

        @self.app.get("/v1/runs/{run_id}/steps")
        async def get_run_steps(
            run_id: str,
            limit: Optional[int] = Query(
                None, ge=1, le=1000, description="Maximum number of steps to return"
            ),
            offset: int = Query(0, ge=0, description="Number of steps to skip"),
            event_type: Optional[str] = Query(None, description="Filter by event type"),
            x_api_key: Optional[str] = Header(None),
        ):
            """
            Get all steps for a run.

            Args:
                run_id: ID of the run.
                limit: Maximum number of steps to return.
                offset: Number of steps to skip.
                event_type: Filter by event type.
                x_api_key: API key for authentication.

            Returns:
                List of steps for the run with decoded data.
            """
            self._check_auth(x_api_key)

            try:
                # Verify run exists
                run = self._database.get_run(run_id)
                if not run:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Run {run_id} not found",
                    )

                # Get steps
                steps = self._database.get_run_steps(
                    run_id=run_id,
                    limit=limit,
                    offset=offset,
                    event_type=event_type,
                )

                # Decode step data through pipeline
                decoded_steps = []
                for step in steps:
                    step_data = step.copy()
                    if step_data.get("data"):
                        try:
                            # Decode through pipeline (decrypt -> decompress -> deserialize)
                            decoded_data = self._pipeline.reverse(step_data["data"])
                            step_data["data"] = decoded_data
                        except Exception as e:
                            logger.warning(
                                f"Failed to decode step {step_data.get('id')}: {e}"
                            )
                            step_data["data"] = None
                    decoded_steps.append(step_data)

                return {
                    "steps": decoded_steps,
                    "total": len(decoded_steps),
                    "limit": limit,
                    "offset": offset,
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to get steps for run {run_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve run steps",
                )

        @self.app.get("/v1/runs/{run_id}/timeline")
        async def get_run_timeline(
            run_id: str,
            include_data: bool = Query(False, description="Include full event data"),
            x_api_key: Optional[str] = Header(None),
        ):
            """
            Get timeline data for a run (optimized for UI).

            Args:
                run_id: ID of the run.
                include_data: Whether to include full event data.
                x_api_key: API key for authentication.

            Returns:
                Timeline events ordered by timestamp.
            """
            self._check_auth(x_api_key)

            try:
                # Verify run exists
                run = self._database.get_run(run_id)
                if not run:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Run {run_id} not found",
                    )

                # Get timeline
                timeline = self._database.get_run_timeline(
                    run_id=run_id,
                    include_data=include_data,
                )

                # Decode data if requested
                if include_data:
                    for event in timeline:
                        if event.get("data"):
                            try:
                                event["data"] = self._pipeline.reverse(event["data"])
                            except Exception as e:
                                logger.warning(
                                    f"Failed to decode event {event.get('id')}: {e}"
                                )
                                event["data"] = None

                return {
                    "run_id": run_id,
                    "events": timeline,
                    "total": len(timeline),
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to get timeline for run {run_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve timeline",
                )

        @self.app.get("/v1/runs/{run_id}/steps/{step_id}/data")
        async def get_step_data(
            run_id: str,
            step_id: str,
            x_api_key: Optional[str] = Header(None),
        ):
            """
            Get raw BLOB data for a specific step.

            Args:
                run_id: ID of the run.
                step_id: ID of the step.
                x_api_key: API key for authentication.

            Returns:
                Decoded step data.
            """
            self._check_auth(x_api_key)

            try:
                # Verify run exists
                run = self._database.get_run(run_id)
                if not run:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Run {run_id} not found",
                    )

                # Get raw data
                raw_data = self._database.get_step_data(step_id)
                if not raw_data:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Step {step_id} not found",
                    )

                # Decode through pipeline
                decoded_data = self._pipeline.reverse(raw_data)

                return {
                    "step_id": step_id,
                    "data": decoded_data,
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to get step data {step_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve step data",
                )

    def _check_auth(self, api_key: Optional[str]):
        """
        Check API key authentication if required.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            api_key: API key from request header.

        Raises:
            HTTPException: If authentication fails.
        """
        if self.config.api_key_required:
            if not api_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key required",
                )

            if self.config.api_key:
                # Use constant-time comparison to prevent timing attacks
                import hmac

                if not hmac.compare_digest(api_key, self.config.api_key):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Invalid API key",
                    )
            else:
                # API key is required but not configured
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="API key authentication misconfigured",
                )

    def run(self, host: Optional[str] = None, port: Optional[int] = None):
        """
        Run the API server.

        Args:
            host: Host to bind to (overrides config).
            port: Port to bind to (overrides config).
        """
        host = host or self.config.api_host
        port = port or self.config.api_port

        logger.info(f"Starting API server on {host}:{port}")
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level=self.config.log_level.lower(),
        )


def get_api_server() -> APIServer:
    """
    Get the global API server instance.

    Creates a new instance if none exists.

    Returns:
        APIServer instance.
    """
    global _api_app
    if _api_app is None:
        config = get_config()
        _api_app = APIServer(config)
    return _api_app


def run_server(
    host: Optional[str] = None,
    port: Optional[int] = None,
):
    """
    Convenience function to run the API server.

    Args:
        host: Host to bind to.
        port: Port to bind to.
    """
    api_server = get_api_server()
    api_server.run(host=host, port=port)
