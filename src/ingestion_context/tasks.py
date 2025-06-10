# src/ingestion_context/tasks.py
import asyncio
import logging
import os
import tempfile # For NamedTemporaryFile specifically
from typing import Dict, Any, List

from src.task_queue.celery_app import app # Import the Celery app instance
from src.ingestion_context.application.ingestion_service import IngestionService

# Configure basic logging for tasks
# In a larger app, logging would be configured more centrally.
logger = logging.getLogger(__name__)
if not logger.handlers: # Avoid adding multiple handlers if module is reloaded
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# Placeholder for where IngestionService might be initialized if it needs complex setup
# For now, it's instantiated directly in tasks.
# def get_ingestion_service():
#     # If IngestionService had dependencies that needed to be injected (e.g., from a DI container)
#     # this would be the place to do it.
#     return IngestionService()

# Note on task naming:
# Celery task names are typically 'module_name.function_name'.
# So these will be 'src.ingestion_context.tasks.process_cloud_mailbox_task'
# and 'src.ingestion_context.tasks.process_eml_file_task'.
# The `name="ingestion.process_cloud_mailbox"` in @app.task overrides this.
# It's often good practice to let Celery auto-generate names based on module path for uniqueness.
# For this exercise, we'll use the specified names.


@app.task(bind=True, name="ingestion.process_cloud_mailbox")
def process_cloud_mailbox_task(self, user_id: str, max_emails: int = 10, mark_as_read: bool = False) -> Dict[str, Any]:
    """
    Celery task to process unread emails from the specified user's cloud mailbox
    via Microsoft Graph API, using their stored OAuth tokens.
    """
    task_id = self.request.id
    logger.info(f"[Task ID: {task_id}] Starting process_cloud_mailbox_task for user_id: {user_id}, max_emails={max_emails}, mark_as_read={mark_as_read}")

    try:
        # Instantiate IngestionService here.
        ingestion_service = IngestionService()

        # IngestionService.process_emails_from_target_mailbox is an async method.
        # asyncio.run() is suitable for calling async code from a sync Celery task.
        processed_ids: List[str] = asyncio.run(
            ingestion_service.process_emails_from_target_mailbox(
                user_id=user_id, # Pass user_id to the service method
                max_emails=max_emails,
                mark_as_read=mark_as_read
            )
        )

        result = {
            "task_id": str(task_id),
            "status": "SUCCESS",
            "message": f"Processed {len(processed_ids)} emails from cloud mailbox for user_id: {user_id}.",
            "processed_count": len(processed_ids),
            "processed_ids": processed_ids
        }
        logger.info(f"[Task ID: {task_id}] Task completed successfully. Result: {result}")
        return result

    except Exception as e:
        logger.error(f"[Task ID: {task_id}] Error during cloud mailbox processing: {e}", exc_info=True)
        result = {
            "task_id": str(task_id),
            "status": "FAILURE",
            "message": f"An error occurred: {str(e)}",
            "error": str(e)
        }
        # self.update_state(state='FAILURE', meta=result) # Optional: update task state
        return result


@app.task(bind=True, name="ingestion.process_eml_file")
def process_eml_file_task(self, eml_content_str: str, original_filename: str, source_identifier_override: Optional[str] = None) -> Dict[str, Any]:
    """
    Celery task to process EML content provided as a string.
    Saves the content to a temporary file and uses IngestionService.
    """
    task_id = self.request.id
    logger.info(f"[Task ID: {task_id}] Starting process_eml_file_task for original_filename: {original_filename}")

    temp_file_path = None
    try:
        # Create a temporary file to store the EML content
        # delete=False is important because IngestionService.ingest_email_from_file expects a path
        # to an existing file. We will manually clean it up in the finally block.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".eml", mode="w", encoding="utf-8") as tmp_file:
            tmp_file.write(eml_content_str)
            temp_file_path = tmp_file.name

        logger.info(f"[Task ID: {task_id}] EML content saved to temporary file: {temp_file_path}")

        ingestion_service = IngestionService()
        raw_email_obj = ingestion_service.ingest_email_from_file(
            file_path=temp_file_path,
            source_identifier_override=source_identifier_override or f"file://{original_filename}"
        )

        if raw_email_obj:
            result = {
                "task_id": str(task_id),
                "status": "SUCCESS",
                "message": f"EML file '{original_filename}' processed successfully.",
                "raw_email_id": raw_email_obj.message_id,
                "subject": raw_email_obj.subject,
                "source_identifier": source_identifier_override or f"file://{original_filename}"
            }
            logger.info(f"[Task ID: {task_id}] EML file task completed successfully. Result: {result}")
            return result
        else:
            logger.error(f"[Task ID: {task_id}] IngestionService failed to process temp EML file: {temp_file_path} (orig: {original_filename})")
            # This case might indicate an issue with the EML content itself or internal parsing logic
            return {
                "task_id": str(task_id),
                "status": "FAILURE",
                "message": f"Failed to process EML content for '{original_filename}'. Ingestion service returned no object.",
                "original_filename": original_filename
            }

    except Exception as e:
        logger.error(f"[Task ID: {task_id}] Error during EML file processing for '{original_filename}': {e}", exc_info=True)
        return {
            "task_id": str(task_id),
            "status": "FAILURE",
            "message": f"An error occurred: {str(e)}",
            "error": str(e),
            "original_filename": original_filename
        }
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"[Task ID: {task_id}] Cleaned up temporary file: {temp_file_path}")
            except Exception as e_cleanup:
                logger.error(f"[Task ID: {task_id}] Error cleaning up temporary file {temp_file_path}: {e_cleanup}")


@app.task(bind=True, name='ingestion.process_google_mailbox')
def process_google_mailbox_task(self, user_id: str, max_emails: int = 10, mark_as_read: bool = True) -> Dict[str, Any]:
    """
    Celery task to process unread emails from the user's connected Gmail mailbox
    using their stored Google OAuth tokens.
    """
    task_id = self.request.id
    logger.info(f"[Task ID: {task_id}] Starting Google mailbox processing for user {user_id} (max_emails={max_emails}, mark_as_read={mark_as_read})")
    try:
        ingestion_service = IngestionService() # Instantiate service inside task

        # IngestionService.process_user_google_mailbox is an async method
        processed_ids = asyncio.run(ingestion_service.process_user_google_mailbox(
            user_id=user_id,
            max_emails=max_emails,
            mark_as_read=mark_as_read
        ))

        message = f"Google mailbox processing completed for user {user_id}. Processed {len(processed_ids)} emails."
        logger.info(f"Task {task_id}: {message}")
        return {
            "task_id": str(task_id),
            "status": "SUCCESS",
            "message": message,
            "processed_count": len(processed_ids),
            "processed_ids": processed_ids
        }
    except Exception as e:
        logger.error(f"Task {task_id}: Error during Google mailbox processing for user {user_id}: {e}", exc_info=True)
        return {
            "task_id": str(task_id),
            "status": "FAILURE",
            "message": f"An error occurred during Google mailbox processing: {str(e)}",
            "error": str(e),
            "processed_count": 0
        }
