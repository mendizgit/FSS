"""Uvicorn entrypoint: `uvicorn tss.entrypoints.api:app`."""

from tss.api.app import create_app

app = create_app()
