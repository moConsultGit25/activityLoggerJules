# src/activity_log_context/interfaces/event_handlers.py

from src.shared_kernel.events import dispatcher, ContentAnalyzedEvent
from ..application.log_service import LogService
# ActivityRecord is created by LogService.

import datetime # For type checking or if any date logic was here

# Initialize services - in a real app, this might use dependency injection.
# For this example, we instantiate directly.
# This will initialize LogService, which in turn initializes MongoActivityRepository.
# If MongoDB is not available, connection errors will be printed by the repository.
log_service_instance = LogService()

def handle_content_analyzed(event: ContentAnalyzedEvent):
    """
    Handles the ContentAnalyzedEvent and triggers the LogService to record the activity.
    """
    print(f"\n[ActivityLogContext Handler] Received ContentAnalyzedEvent for ID: {event.raw_email_id}")
    print(f"  Subject: {event.subject}, Disposition: {event.disposition}")

    # Call the appropriate method on LogService to record the activity.
    # This method is designed to take event data directly.
    activity_record = log_service_instance.record_activity_from_event_data(event)

    if activity_record:
        print(f"[ActivityLogContext Handler] Successfully processed event. ActivityRecord ID: {activity_record.record_id} saved/attempted save.")
    else:
        print(f"[ActivityLogContext Handler] Failed to process event or save ActivityRecord for raw_email_id: {event.raw_email_id}")


def register_activity_log_event_handlers():
    """Call this function once at application startup to register handlers."""
    dispatcher.subscribe(ContentAnalyzedEvent, handle_content_analyzed)
    print("Activity Log event handlers registered with shared dispatcher.")

# Example of how to register and test this handler
if __name__ == '__main__':
    print("\n--- ActivityLogContext Event Handler Demonstration ---")

    # Register the handler from this module
    register_activity_log_event_handlers()

    # To test, we need to simulate a ContentAnalyzedEvent being published.
    # This would typically happen from the analysis_context's handler.
    # For a standalone test of this handler module, we can publish one directly:
    print("\nSimulating ContentAnalyzedEvent publication to trigger activity log handler...")

    # Note: This test will attempt to connect to MongoDB via LogService -> MongoActivityRepository.
    # Ensure MongoDB is running if you want to see successful database operations.
    # If not, connection errors will be printed, and the 'add' operation will likely fail silently
    # or as per MongoActivityRepository's error handling.

    simulated_analyzed_event = ContentAnalyzedEvent(
        raw_email_id="log-handler-test-001",
        sender="log_sender@example.com",
        recipient="log_recipient@example.com",
        subject="Event for Logging Test",
        body="This is the original body content for the logging test. It is useful for context.",
        received_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_identifier="/path/to/log_test_event.eml",
        summary="This is the generated summary from analysis to be logged.",
        disposition="TestDispositionForLog",
        keywords_found=["log", "test", "event"],
        analyzed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    dispatcher.publish(simulated_analyzed_event)

    # Example with minimal data to ensure robustness
    print("\nSimulating another ContentAnalyzedEvent with potentially fewer fields...")
    simulated_analyzed_event_minimal = ContentAnalyzedEvent(
        raw_email_id="log-handler-test-002",
        sender=None, # Test how Nones are handled
        recipient=None,
        subject="Minimal Subject",
        body=None,
        received_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_identifier="/path/to/minimal_log_event.eml",
        summary="Minimal summary.",
        disposition="MinimalDisposition",
        # keywords_found uses default_factory=list
        analyzed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    dispatcher.publish(simulated_analyzed_event_minimal)

    print("\n--- End of ActivityLogContext Event Handler Demonstration ---")
