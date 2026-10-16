"""
ALPHA Quant — Phase 6: Generic Pagination Schemas.
Provides typed pagination parameters and wrappers for API collections.
"""

from typing import Generic, List, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized paginated list wrapper for ALPHA Quant API endpoints."""
    total: int = Field(..., description="Total number of items matching filter")
    limit: int = Field(..., description="Maximum items requested in page")
    offset: int = Field(..., description="Items skipped from beginning")
    items: List[T] = Field(..., description="Collection of items in current page")
