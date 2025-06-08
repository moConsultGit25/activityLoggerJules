# src/analysis_context/interfaces/event_handlers.py

from src.shared_kernel.events import dispatcher, EmailIngestedEvent, ContentAnalyzedEvent
from ..application.analysis_service import AnalysisService
# RawEmail domain object is not directly used here as event carries necessary data.
# AnalyzedContent domain object is created by AnalysisService.

import datetime # For analyzed_at timestamp if needed here, though service might set it

# Initialize services - in a real app, this might use dependency injection.
# For this example, we instantiate directly.
analysis_service = AnalysisService()

def handle_email_ingested(event: EmailIngestedEvent):
    """
    Handles the EmailIngestedEvent, triggers content analysis,
    and publishes a ContentAnalyzedEvent.
    """
    print(f"\n[AnalysisContext Handler] Received EmailIngestedEvent for ID: {event.raw_email_id}")
    print(f"  Subject: {event.subject}")
    print(f"  Body to analyze (snippet): {event.body[:100] if event.body else 'N/A'}...")

    # Call the AnalysisService to process the content
    # The event.body already contains the text_content_to_analyze
    # The event.subject contains the subject_text
    analyzed_content_obj = analysis_service.analyze_text_content(
        raw_email_id=event.raw_email_id,
        text_to_analyze=event.body if event.body is not None else "", # Ensure string
        subject_text=event.subject if event.subject is not None else "" # Ensure string
    )

    if analyzed_content_obj:
        print(f"[AnalysisContext Handler] Content analysis successful for ID: {event.raw_email_id}")
        # Create and publish ContentAnalyzedEvent
        # Populate it with data from the original EmailIngestedEvent and the new AnalyzedContent
        content_analyzed_event = ContentAnalyzedEvent(
            raw_email_id=event.raw_email_id,
            sender=event.sender,
            recipient=event.recipient,
            subject=event.subject,
            body=event.body, # Original body passed through
            received_at=event.received_at,
            source_identifier=event.source_identifier,
            summary=analyzed_content_obj.summary,
            disposition=analyzed_content_obj.disposition,
            keywords_found=analyzed_content_obj.keywords_found,
            analyzed_at=analyzed_content_obj.analysis_timestamp # from AnalyzedContent default factory
        )
        dispatcher.publish(content_analyzed_event)
    else:
        print(f"[AnalysisContext Handler] Content analysis failed for ID: {event.raw_email_id}")

def register_analysis_event_handlers():
    """Call this function once at application startup to register handlers."""
    dispatcher.subscribe(EmailIngestedEvent, handle_email_ingested)
    print("Analysis event handlers registered.")

# Example of how to register and test this handler
if __name__ == '__main__':
    print("\n--- AnalysisContext Event Handler Demonstration ---")

    # Register the handler from this module
    register_analysis_event_handlers()

    # --- Setup a dummy handler for ContentAnalyzedEvent for this test ---
    def _test_local_content_analyzed_handler(event: ContentAnalyzedEvent):
        print(f"\n[LOCAL TEST HANDLER] Received ContentAnalyzedEvent:")
        print(f"  Raw Email ID: {event.raw_email_id}")
        print(f"  Summary: '{event.summary}'")
        print(f"  Disposition: {event.disposition}")
        print(f"  Analyzed At: {event.analyzed_at}")

    dispatcher.subscribe(ContentAnalyzedEvent, _test_local_content_analyzed_handler)
    # --- End of dummy handler setup ---

    # To test, we need to simulate an EmailIngestedEvent being published.
    # This would typically happen from IngestionService.
    # For a standalone test of this handler module, we can publish one directly:
    print("\nSimulating EmailIngestedEvent publication to trigger analysis handler...")
    simulated_ingested_event = EmailIngestedEvent(
        raw_email_id="analysis-handler-test-001",
        sender="test_sender@example.com",
        recipient="test_recipient@example.com",
        subject="Event Handler Test Subject",
        body="This is the body for the analysis event handler test. It should be summarized and classified.",
        received_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_identifier="/path/to/handler_test.eml"
    )
    dispatcher.publish(simulated_ingested_event)

    # Test with minimal content
    print("\nSimulating EmailIngestedEvent with minimal content...")
    simulated_ingested_event_minimal = EmailIngestedEvent(
        raw_email_id="analysis-handler-test-002",
        sender=None, recipient=None, subject=None, body=None, # Test None propagation
        received_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_identifier="/path/to/minimal.eml"
    )
    dispatcher.publish(simulated_ingested_event_minimal)

    print("\n--- End of AnalysisContext Event Handler Demonstration ---")
