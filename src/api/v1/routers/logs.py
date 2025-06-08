# src/api/v1/routers/logs.py
from fastapi import APIRouter, Query, Depends, HTTPException
from typing import Dict, Any

from src.activity_log_context.application.log_service import LogService
from ..schemas.activity_log_schemas import PaginatedActivityLogResponse # ActivityLogResponseItem (for future GET by ID)
from src.auth_context.domain.user import User as DomainUser # For current_user type hint
from src.api.dependencies import get_current_active_user # Dependency for protected routes


router = APIRouter()

def get_log_service():
    return LogService()

@router.get("/",
            response_model=PaginatedActivityLogResponse,
            summary="Retrieve activity logs (requires authentication).",
            response_description="A paginated list of activity logs.")
async def get_activity_logs(
    page: int = Query(1, ge=1, description="Page number to retrieve."),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page (max 100)."),
    sort_by: str = Query('logged_at', description="Field to sort by (e.g., 'logged_at', 'subject')."),
    sort_order: str = Query('desc', regex='^(asc|desc)$', description="Sort order: 'asc' or 'desc'."),
    log_service: LogService = Depends(get_log_service),
    current_user: DomainUser = Depends(get_current_active_user) # Secure this endpoint
):
    """
    Retrieves a paginated and sorted list of activity logs from the system.
    Requires user to be authenticated and active.
    User '{current_user.username}' is requesting the logs. (Example of using current_user)
    """
    print(f"User '{current_user.username}' (ID: {current_user.id}) is requesting activity logs.")
    try:
        paginated_data = log_service.get_activity_logs_paginated(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order_str=sort_order
        )
        return paginated_data
    except Exception as e:
        print(f"Error in GET /logs endpoint for user {current_user.username}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while retrieving logs: {str(e)}"
        )

# Example for GET by ID (also secured)
# from ..schemas.activity_log_schemas import ActivityLogResponseItem
# @router.get("/{record_id}", response_model=ActivityLogResponseItem)
# async def get_activity_log_by_id(
#       record_id: str,
#       log_service: LogService = Depends(get_log_service),
#       current_user: DomainUser = Depends(get_current_active_user)
# ):
#     print(f"User '{current_user.username}' requesting log ID: {record_id}")
#     # Assume LogService has a method like get_log_as_dict(record_id)
#     # activity_record_dict = log_service.get_log_as_dict(record_id)
#     # if not activity_record_dict:
#     #     raise HTTPException(status_code=404, detail="Activity log not found")
#     # return activity_record_dict
#     raise HTTPException(status_code=501, detail="Not implemented yet")
