# src/api/v1/routers/ingestion.py
# No longer need shutil, tempfile, os here as tasks handle file operations.
# import shutil
# import tempfile
# import os
# import asyncio # Not directly used here anymore for service calls

from fastapi import APIRouter, HTTPException, UploadFile, File, status, Depends, Query
from typing import Annotated, List, Dict, Any # Retain List, Dict, Any for response models

# Import Celery tasks
from src.ingestion_context.tasks import process_cloud_mailbox_task, process_eml_file_task

# No longer need direct IngestionService import if all actions are via tasks
# from src.ingestion_context.application.ingestion_service import IngestionService
from src.auth_context.domain.user import User as DomainUser
from src.api.dependencies import get_current_active_user

router = APIRouter()

# IngestionService is now instantiated within the Celery tasks themselves.
# If there were other synchronous utility methods from IngestionService needed by the API directly,
# it could be kept, but for these two endpoints, it's not directly used by the router anymore.
# ingestion_service = IngestionService()

@router.post("/process-eml/",
             summary="Queue an EML file for ingestion and analysis (requires authentication).",
             response_description="Confirmation that the EML processing task has been queued.")
async def queue_eml_file_for_processing( # Renamed for clarity
    file: Annotated[UploadFile, File(description="An EML file to be processed.")],
    current_user: DomainUser = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Accepts an EML file, reads its content, and queues a Celery task
    for asynchronous processing. Requires user to be authenticated and active.
    """
    print(f"User '{current_user.username}' (ID: {current_user.id}) is queueing an EML file: {file.filename}")

    if not file.filename or not file.filename.endswith(".eml"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file type. Only .eml files are accepted.")

    try:
        eml_content_bytes = await file.read()
        try:
            eml_content_str = eml_content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            try:
                # Attempt with other common encodings if UTF-8 fails
                eml_content_str = eml_content_bytes.decode('latin-1')
            except UnicodeDecodeError as ude:
                print(f"EML file '{file.filename}' has an unsupported encoding: {ude}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"EML file '{file.filename}' has an unsupported encoding.")

        original_filename = file.filename if file.filename else "unknown.eml"

        # Define a source identifier. Using filename for this example.
        # Could also be a UUID generated here or other metadata.
        source_identifier = f"upload://{original_filename}"

        # Dispatch the Celery task
        task = process_eml_file_task.apply_async(
            args=[eml_content_str, original_filename, source_identifier]
            # Example: specify a queue: kwargs={'queue': 'eml_processing'}
        )

        print(f"EML file '{original_filename}' processing task queued with ID: {task.id}")
        return {
            "task_id": task.id,
            "status": "queued",
            "message": f"EML file '{original_filename}' processing has been queued.",
            "filename": original_filename,
            "uploader_username": current_user.username
        }

    except HTTPException: # Re-raise HTTPExceptions (e.g., from encoding check)
        raise
    except Exception as e:
        print(f"Unexpected error in queue_eml_file_for_processing for file '{file.filename}': {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred while queueing the EML file: {str(e)}")
    finally:
        await file.close()


@router.post("/trigger-cloud-mailbox-sync/",
             summary="Queue a task to sync unread emails from cloud mailbox (requires authentication).",
             response_description="Confirmation that the cloud mailbox sync task has been queued.")
async def queue_cloud_mailbox_sync_task( # Renamed for clarity
    current_user: DomainUser = Depends(get_current_active_user),
    max_emails: int = Query(10, ge=1, le=50, description="Maximum number of emails to process."),
    mark_as_read: bool = Query(True, description="Mark processed emails as read in the mailbox.")
) -> Dict[str, Any]:
    """
    Queues a Celery task to ingest unread emails from the configured Microsoft Graph mailbox.
    - Requires authentication.
    """
    print(f"User '{current_user.username}' (ID: {current_user.id}) triggered cloud mailbox sync task queueing.")
    try:
        # Dispatch the Celery task
        task = process_cloud_mailbox_task.apply_async(
            args=[max_emails, mark_as_read]
            # Example: specify a queue: kwargs={'queue': 'cloud_sync'}
        )

        print(f"Cloud mailbox sync task queued with ID: {task.id}")
        return {
            "task_id": task.id,
            "status": "queued",
            "message": f"Cloud mailbox sync task (max_emails={max_emails}, mark_as_read={mark_as_read}) has been queued by {current_user.username}.",
        }
    except Exception as e: # Catch any errors during task dispatch itself (e.g., broker not available)
        print(f"Unexpected error in queue_cloud_mailbox_sync_task: {e}")
        # This might indicate an issue with Celery setup or broker connection.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Failed to queue cloud sync task: {str(e)}")
