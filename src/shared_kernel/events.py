# src/shared_kernel/events.py
from typing import Callable, Dict, List, Type, Any
import dataclasses

@dataclasses.dataclass
class DomainEvent:
    """Base class for domain events."""
    pass

# Revised Event Definitions (as per step 8 of the plan)

@dataclasses.dataclass
class EmailIngestedEvent(DomainEvent):
    raw_email_id: str          # Unique ID for the ingested email
    sender: str | None
    recipient: str | None
    subject: str | None
    body: str | None               # The main text content to be analyzed
    received_at: str           # ISO timestamp string
    source_identifier: str     # e.g., file path or original EML Message-ID
    # Optional: Add full raw content if needed by early subscribers, but prefer specific fields
    # raw_eml_content: str | None = None

@dataclasses.dataclass
class ContentAnalyzedEvent(DomainEvent):
    raw_email_id: str          # Corresponds to the EmailIngestedEvent.raw_email_id
    sender: str | None
    recipient: str | None
    subject: str | None
    body: str | None               # Original body, for reference or if LogService needs it
    received_at: str           # ISO timestamp of ingestion
    source_identifier: str     # Original source identifier

    summary: str
    disposition: str
    keywords_found: List[str] = dataclasses.field(default_factory=list)
    analyzed_at: str           # ISO timestamp for when analysis was completed

    # Optional: Could add reference to the full raw content if needed for logging,
    # but ActivityRecord's full_content_reference might cover this.

# Simple In-Process Event Dispatcher
class EventDispatcher:
    def __init__(self):
        self._handlers: Dict[Type[DomainEvent], List[Callable[[DomainEvent], None]]] = {}
        print("EventDispatcher initialized.")

    def subscribe(self, event_type: Type[DomainEvent], handler: Callable[[DomainEvent], None]):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        print(f"Handler {handler.__name__} subscribed to {event_type.__name__}")

    def publish(self, event: DomainEvent):
        event_type = type(event)
        print(f"Publishing event: {event_type.__name__} with data: {event}")
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                try:
                    print(f"Calling handler: {handler.__name__} for event {event_type.__name__}")
                    handler(event)
                except Exception as e:
                    # Basic error logging for the handler
                    print(f"Error in event handler {handler.__name__} for {event_type.__name__}: {e}")
        else:
            print(f"No handlers registered for event type: {event_type.__name__}")

# Global dispatcher instance (simple approach for in-process communication)
# In a larger application, dependency injection might be used to provide this.
dispatcher = EventDispatcher()

if __name__ == '__main__':
    # Example of using the dispatcher
    print("\n--- Event Dispatcher Demonstration ---")

    @dataclasses.dataclass
    class TestEvent(DomainEvent):
        message: str

    def test_event_handler1(event: TestEvent):
        print(f"TestEvent Handler 1 received: {event.message}")

    def test_event_handler2(event: TestEvent):
        print(f"TestEvent Handler 2 received (and will raise error): {event.message}")
        raise ValueError("Simulated error in handler2")

    def email_ingested_test_handler(event: EmailIngestedEvent):
        print(f"EmailIngestedEvent Test Handler received ID: {event.raw_email_id}, Subject: {event.subject}")

    # Subscribe handlers
    dispatcher.subscribe(TestEvent, test_event_handler1)
    dispatcher.subscribe(TestEvent, test_event_handler2) # This one will show error logging
    dispatcher.subscribe(EmailIngestedEvent, email_ingested_test_handler)

    # Publish events
    print("\nPublishing TestEvent...")
    test_event_instance = TestEvent(message="Hello, Events!")
    dispatcher.publish(test_event_instance)

    print("\nPublishing EmailIngestedEvent...")
    email_event_instance = EmailIngestedEvent(
        raw_email_id="test-id-001",
        sender="sender@example.com",
        recipient="receiver@example.com",
        subject="Test Subject for Event",
        body="This is the email body for event testing.",
        received_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), # Need to import datetime for this
        source_identifier="/path/to/email.eml"
    )
    # Need to import datetime for the above example to run directly
    import datetime # Added for the __main__ example
    dispatcher.publish(email_event_instance)

    print("\n--- End of Event Dispatcher Demonstration ---")
