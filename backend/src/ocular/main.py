"""Compose settings + config + pipeline + app, and serve."""

from __future__ import annotations

import uvicorn

from .config import Settings, load_config
from .pipeline import Pipeline
from .web import create_app


def build() -> tuple[object, Settings, Pipeline]:
    settings = Settings.from_env()
    config = load_config(settings.config_path)
    pipeline = Pipeline(config, settings)
    app = create_app(pipeline, settings)

    @app.on_event("startup")
    def _startup() -> None:
        pipeline.start()

    @app.on_event("shutdown")
    def _shutdown() -> None:
        pipeline.stop()

    return app, settings, pipeline


def main() -> None:
    app, settings, _ = build()
    uvicorn.run(app, host=settings.bind_host, port=settings.bind_port, log_level="warning")
