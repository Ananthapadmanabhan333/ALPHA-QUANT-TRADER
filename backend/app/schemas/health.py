from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    status: str = Field(..., description="Database status: healthy or unhealthy")
    connected: bool = Field(..., description="Whether a live DB connection was made")
    latency_ms: Optional[float] = Field(None, description="Query roundtrip latency in ms")
    dialect: Optional[str] = Field(None, description="Database dialect name")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class HealthResponse(BaseModel):
    status: str = Field(..., description="System overall health status")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Runtime environment")
    timestamp: datetime = Field(..., description="Current server UTC timestamp")


class ReadinessResponse(BaseModel):
    status: str = Field(..., description="Readiness status: ready or not_ready")
    ready: bool = Field(..., description="Boolean readiness indicator")
    timestamp: datetime = Field(..., description="Current server UTC timestamp")
    components: Dict[str, Any] = Field(..., description="Subsystem readiness details")


class SystemInfoResponse(BaseModel):
    project_name: str
    version: str
    environment: str
    debug: bool
    timestamp: datetime
    uptime_seconds: float
    database: DatabaseHealth
