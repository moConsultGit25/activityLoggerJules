# src/activity_log_context/domain/activity_record.py
import dataclasses
import datetime # Added for default timestamps
import uuid # For default record_id
from typing import Any, Dict

@dataclasses.dataclass
class ActivityRecord:
    record_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    ingested_at: str # ISO format timestamp (when the raw data was ingested)
    source_channel: str # e.g., "email", "chat", "call_log"
    source_identifier: str # e.g., email's original message_id, file path, chat session ID

    # Information derived from RawEmail (denormalized for the log)
    sender: str | None = None
    recipient: str | None = None
    subject: str | None = None

    # Information from AnalyzedContent (denormalized for the log)
    summary: str | None = None
    disposition: str | None = None # Or a more structured type

    # Reference to the original raw content if stored elsewhere, or the content itself if small
    full_content_reference: str | None = None # e.g., path to original raw_email or ID in a raw_store

    # Timestamp for when this specific log record was finalized and written
    logged_at: str = dataclasses.field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    # Optional: metadata dict for other details not fitting the main structure
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)

    # Example of how this record might be created from other domain objects
    @classmethod
    def from_analysis(cls, raw_email: 'RawEmail', analyzed_content: 'AnalyzedContent', source_channel="email"):
        # The type hints for RawEmail and AnalyzedContent are strings to avoid circular imports
        # if this class were to be imported by those modules directly.
        # In a real scenario, these would be proper imports if structure allows.
        return cls(
            ingested_at=raw_email.received_at,
            source_channel=source_channel,
            source_identifier=raw_email.message_id, # Or raw_email.source_file_path
            sender=raw_email.sender,
            recipient=raw_email.recipient,
            subject=raw_email.subject,
            summary=analyzed_content.summary,
            disposition=analyzed_content.disposition,
            full_content_reference=raw_email.source_file_path or f"raw_email_id:{raw_email.message_id}",
            # metadata could include things like analysis_timestamp, keywords_found etc.
            metadata={
                "analysis_timestamp": analyzed_content.analysis_timestamp,
                "keywords_found": analyzed_content.keywords_found,
                "raw_email_content_snippet": raw_email.raw_content[:200] # Example snippet
            }
        )

# To use the type hint for RawEmail and AnalyzedContent in the classmethod correctly,
# you might need to put them in quotes if those classes are not yet defined or
# to avoid circular dependencies at runtime if this file is imported by them.
# For now, this structure assumes they would be available in the scope where from_analysis is called.
# from src.ingestion_context.domain.raw_email import RawEmail (example)
# from src.analysis_context.domain.analyzed_content import AnalyzedContent (example)
