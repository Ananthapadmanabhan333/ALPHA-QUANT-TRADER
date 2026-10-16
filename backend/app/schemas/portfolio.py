"""
ALPHA Quant — Phase 6: Portfolio & Execution Read Schemas.
Exports unified schemas for portfolio overview, paginated order lists, and execution fills.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.paper.schemas import (
    PaperAccountResponse,
    PaperFillResponse,
    PaperOrderResponse,
    PaperPositionResponse,
    RiskStatusResponse,
)

PortfolioResponse = PaperAccountResponse
OrderResponse = PaperOrderResponse
FillResponse = PaperFillResponse
PositionResponse = PaperPositionResponse
