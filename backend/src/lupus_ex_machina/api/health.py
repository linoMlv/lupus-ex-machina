"""Liveness probe consumed by the container HEALTHCHECK and by the platform."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Answer of the liveness probe."""

    status: Literal["ok"] = "ok"


@router.get("/health", summary="Report that the service is up")
async def read_health() -> HealthResponse:
    """Return a constant payload proving the process can answer requests."""
    return HealthResponse()
