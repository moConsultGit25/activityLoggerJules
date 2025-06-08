# src/analysis_context/domain/analyzed_content.py
import dataclasses
import datetime # Added for default timestamp

@dataclasses.dataclass
class AnalyzedContent:
    raw_email_id: str # Corresponds to RawEmail.message_id
    summary: str
    disposition: str # This could be an enum or a value object in a richer model
    analysis_timestamp: str = dataclasses.field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    # Optional: confidence score for disposition, or list of keywords found
    keywords_found: list[str] = dataclasses.field(default_factory=list)
    disposition_confidence: float | None = None
