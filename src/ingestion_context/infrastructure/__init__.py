# src/ingestion_context/infrastructure/__init__.py

from .email_parser import parse_eml_file_to_dict
from .graph_email_client import GraphEmailClient # For Microsoft Graph API
from .gmail_api_client import GmailApiClient     # For Google Gmail API

__all__ = [
    "parse_eml_file_to_dict",
    "GraphEmailClient",
    "GmailApiClient",
]
