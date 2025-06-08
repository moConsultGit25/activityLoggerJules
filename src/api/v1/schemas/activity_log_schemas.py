# src/api/v1/schemas/activity_log_schemas.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# This model should mirror the fields of ActivityRecord domain object
# that we want to expose via the API.
class ActivityLogResponseItem(BaseModel):
    record_id: str
    ingested_at: str
    source_channel: str
    source_identifier: str
    sender: Optional[str] = None
    recipient: Optional[str] = None
    subject: Optional[str] = None
    summary: Optional[str] = None
    disposition: Optional[str] = None
    full_content_reference: Optional[str] = None
    logged_at: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # If using Pydantic v1.8+ with ORM mode for dataclasses:
    class Config:
        from_attributes = True # Renamed from orm_mode in Pydantic v2

class PaginatedActivityLogResponse(BaseModel):
    data: List[ActivityLogResponseItem]
    page: int = Field(..., gt=0, description="The current page number.")
    page_size: int = Field(..., gt=0, description="Number of items per page.")
    total_items: int = Field(..., ge=0, description="Total number of items available.")
    total_pages: int = Field(..., ge=0, description="Total number of pages.")

# Example for a potential request body for filtering (not used in this subtask, but good for context)
class ActivityLogFilterRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    disposition: Optional[str] = None
    sender: Optional[str] = None
    # ... other filterable fields
