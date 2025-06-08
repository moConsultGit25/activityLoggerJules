# src/ingestion_context/infrastructure/__init__.py

from .email_parser import parse_eml_file_to_dict

__all__ = [
    "parse_eml_file_to_dict",
]
