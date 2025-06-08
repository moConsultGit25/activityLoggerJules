# src/ingestion_context/domain/raw_email.py
import dataclasses
import datetime # Added for default timestamp

@dataclasses.dataclass
class RawEmail:
    message_id: str
    sender: str
    recipient: str
    subject: str
    raw_content: str # Could be the full EML content or just the body
    received_at: str = dataclasses.field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    # Consider adding source_file_path if applicable
    source_file_path: str | None = None
