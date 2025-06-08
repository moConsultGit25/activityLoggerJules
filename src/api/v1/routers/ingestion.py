# src/api/v1/routers/ingestion.py
import shutil
import tempfile
import os
import asyncio # For async operations if needed, though IngestionService handles it
from fastapi import APIRouter, HTTPException, UploadFile, File, status, Depends, Query
from typing import Annotated, List, Dict, Any

from src.ingestion_context.application.ingestion_service import IngestionService
from src.auth_context.domain.user import User as DomainUser
from src.api.dependencies import get_current_active_user

router = APIRouter()

# Instantiate service - consider dependency injection for more complex apps
ingestion_service = IngestionService()

@router.post("/process-eml/",
             summary="Process an EML file (requires authentication).",
             response_description="Details of the ingestion process outcome.")
async def process_eml_upload(
    file: Annotated[UploadFile, File(description="An EML file to be processed.")],
    current_user: DomainUser = Depends(get_current_active_user)
):
    print(f"User '{current_user.username}' (ID: {current_user.id}) is processing an EML file via upload.")
    if not file.filename or not file.filename.endswith(".eml"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file type. Only .eml files are accepted.")

    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".eml", prefix="api_upload_") as tmp_file_obj:
            shutil.copyfileobj(file.file, tmp_file_obj)
            temp_file_path = tmp_file_obj.name

        raw_email_obj = ingestion_service.ingest_email_from_file(temp_file_path)

        if raw_email_obj:
            return {
                "message": "EML file processed successfully.",
                "uploader_username": current_user.username,
                "raw_email_id": raw_email_obj.message_id,
                "subject": raw_email_obj.subject,
                "detail": "Ingestion complete, analysis and logging triggered."
            }
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process EML file.")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in process_eml_upload: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try: os.remove(temp_file_path)
            except Exception as e_remove: print(f"Error cleaning temp file {temp_file_path}: {e_remove}")
        await file.close()


@router.post("/trigger-cloud-mailbox-sync/",
             summary="Trigger sync of unread emails from configured cloud mailbox (requires authentication).",
             response_description="Outcome of the cloud mailbox sync operation.")
async def trigger_cloud_mailbox_sync(
    current_user: DomainUser = Depends(get_current_active_user),
    max_emails: int = Query(10, ge=1, le=50, description="Maximum number of emails to process."),
    mark_as_read: bool = Query(True, description="Mark processed emails as read in the mailbox.")
) -> Dict[str, Any]:
    """
    Triggers the ingestion of unread emails from the configured Microsoft Graph mailbox.
    - Requires authentication.
    - Processes a defined maximum number of emails.
    - Optionally marks processed emails as read.
    """
    print(f"User '{current_user.username}' (ID: {current_user.id}) triggered cloud mailbox sync.")
    try:
        # IngestionService.process_emails_from_target_mailbox is an async method
        processed_ids = await ingestion_service.process_emails_from_target_mailbox(
            max_emails=max_emails,
            mark_as_read=mark_as_read
        )

        if processed_ids is None: # Should not happen if service handles errors by returning empty list
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Cloud mailbox sync failed. Graph client might not be configured or encountered an error.")

        return {
            "message": f"Cloud mailbox sync triggered by {current_user.username}. Processed {len(processed_ids)} emails.",
            "processed_raw_email_ids": processed_ids,
            "details": "Each processed email should have triggered analysis and logging events."
        }
    except ValueError as ve: # Catch errors like Graph client not configured
        print(f"Configuration error during cloud sync: {ve}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        print(f"Unexpected error in trigger_cloud_mailbox_sync: {e}")
        # Log the full error for debugging: import traceback; traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An unexpected error occurred during cloud sync: {str(e)}")
