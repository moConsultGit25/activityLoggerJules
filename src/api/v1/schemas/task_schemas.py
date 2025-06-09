# src/api/v1/schemas/task_schemas.py
from pydantic import BaseModel, Field
from typing import Any, Optional, Dict

class TaskStatusResponse(BaseModel):
    """
    Represents the response model for querying the status of an asynchronous Celery task.
    """
    task_id: str = Field(..., description="The unique ID of the Celery task.")
    status: str = Field(..., description="Current status of the task (e.g., PENDING, STARTED, SUCCESS, FAILURE, RETRY).")
    result: Optional[Any] = Field(None, description="The result of the task if it completed successfully. This can be any JSON-serializable data returned by the task.")
    # error_details field is designed to hold a structured error if the task failed.
    # The task itself should return a dictionary with error information for this field.
    # If the task raises an unhandled exception, Celery's result.result will be the exception object.
    error_info: Optional[Dict[str, Any]] = Field(None, description="Details about the error if the task failed. Could include 'type', 'message', 'traceback'.")

    class Config:
        from_attributes = True # For compatibility if creating from an object with these attributes.
        # Pydantic v2 uses model_config = {"from_attributes": True}
        # For now, sticking to from_attributes for wider compatibility if environment is not strictly v2.
        # If using Pydantic v2 only, switch to model_config.
        # model_config = {"from_attributes": True} # Pydantic v2

# Example of a more detailed error structure within error_info
# class TaskErrorDetails(BaseModel):
#     type: str
#     message: str
#     traceback: Optional[str] = None # Be cautious about exposing full tracebacks in production APIs
#
# class TaskStatusResponse(BaseModel):
#     ...
#     error_info: Optional[TaskErrorDetails] = None
#     ...
