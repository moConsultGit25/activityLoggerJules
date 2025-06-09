# src/api/v1/routers/tasks.py
from fastapi import APIRouter, Depends, HTTPException, status

# Celery components
from src.task_queue.celery_app import app as celery_app # The Celery application instance
from celery.result import AsyncResult # To fetch task results

# API specific schemas and dependencies
from ..schemas.task_schemas import TaskStatusResponse
from src.auth_context.domain.user import User as DomainUser # For current_user type hint
from src.api.dependencies import get_current_active_user # For securing the endpoint

router = APIRouter()

@router.get(
    "/{task_id}/status",
    response_model=TaskStatusResponse,
    summary="Get Asynchronous Task Status and Result",
    response_description="The current status and result (if available) of the specified Celery task.",
    tags=["Tasks"] # Ensure this tag is added to FastAPI app for documentation
)
async def get_task_status_and_result( # Renamed for clarity
    task_id: str,
    current_user: DomainUser = Depends(get_current_active_user) # Secure endpoint
):
    """
    Retrieves the status and result of a Celery task identified by `task_id`.
    Requires user authentication.
    - **task_id**: The ID of the Celery task to check.
    """
    print(f"User '{current_user.username}' checking status for task ID: {task_id}")

    # Fetch the task result object from Celery using the task_id and our app instance
    task_result = AsyncResult(task_id, app=celery_app)

    response_data = {
        "task_id": task_id,
        "status": task_result.status, # PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED
        "result": None, # Default to None
        "error_info": None # Default to None
    }

    if task_result.ready(): # Task has completed (either SUCCESS or FAILURE)
        if task_result.successful():
            # The result of a successful task is stored in task_result.result
            response_data["result"] = task_result.result
            print(f"Task {task_id} completed successfully. Result: {task_result.result}")
        elif task_result.failed():
            # For failed tasks, task_result.result contains the exception object.
            # task_result.traceback contains the traceback string.
            # The tasks themselves are designed to return a dictionary on error.
            failure_result_content = task_result.result
            if isinstance(failure_result_content, dict) and 'error' in failure_result_content:
                # If task returned its own structured error
                response_data["error_info"] = {
                    "type": failure_result_content.get("error_type", "TaskExecutionError"),
                    "message": failure_result_content.get("message", "Task failed with custom error structure."),
                    "details": failure_result_content.get("error")
                }
                # Optionally include the task's custom dict as the "result" as well,
                # as it might contain partial success info or specific error codes.
                response_data["result"] = failure_result_content
            else: # Unhandled exception in task
                response_data["error_info"] = {
                    "type": type(failure_result_content).__name__, # Type of the exception
                    "message": str(failure_result_content), # Exception message
                    # "traceback": task_result.traceback # Consider security before exposing tracebacks
                }
            print(f"Task {task_id} failed. Error: {response_data['error_info']}")
        # No specific handling for REVOKED here, status will just be "REVOKED"
    else: # Task is PENDING, STARTED, or RETRY
        # For these states, task_result.result is typically None.
        # The status field already indicates the state.
        print(f"Task {task_id} is in state: {task_result.status}")
        # Optionally, if task uses custom states or progress updates via task_result.update_state(meta=...),
        # that information would be in task_result.info (or task_result.result if state is not FAILURE/SUCCESS).
        if task_result.info: # Check if there's any intermediate metadata
            response_data["result"] = task_result.info


    # Use Pydantic model for response construction and validation
    # This ensures the response conforms to the defined schema.
    try:
        return TaskStatusResponse(**response_data)
    except Exception as e: # Should not happen if response_data keys match TaskStatusResponse
        print(f"Error constructing TaskStatusResponse for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Error forming task status response.")

# Example of how to test this endpoint manually (e.g., with curl or Postman):
# 1. Queue a task via one of the ingestion endpoints (e.g., POST /api/v1/ingestion/process-eml/).
#    This will return a JSON like: {"task_id": "some-uuid-string", "status": "queued", ...}
# 2. Take the "task_id" from the response.
# 3. Make a GET request to /api/v1/tasks/{task_id}/status (with authentication token).
#    Example: GET http://localhost:8000/api/v1/tasks/some-uuid-string/status
#             Headers: Authorization: Bearer <your_jwt_token>
# 4. Observe the response, which should match the TaskStatusResponse schema.
#    Refresh a few times to see the status change from PENDING to SUCCESS/FAILURE.
