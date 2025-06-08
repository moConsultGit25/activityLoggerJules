# src/analysis_context/application/analysis_service.py
from ..domain.analyzed_content import AnalyzedContent
from .content_analyzer_tools import generate_summary_from_text, determine_content_disposition
# from src.ingestion_context.domain.raw_email import RawEmail # For type hint if passing RawEmail object

import datetime # Retained for timestamping AnalyzedContent

class AnalysisService:
    """
    Application service for the Analysis Context.
    Orchestrates content analysis (summarization, disposition) using tools.
    """

    def __init__(self):
        # In a more advanced setup, specific models or configurations for the
        # analyzer tools might be injected here.
        # For example, if generate_summary_from_text used a configurable model,
        # or determine_content_disposition used configurable keyword sets.
        print("AnalysisService initialized. Using content_analyzer_tools.")

    def analyze_text_content(
        self,
        raw_email_id: str,
        text_to_analyze: str,
        subject_text: str = ""
    ) -> AnalyzedContent | None:
        """
        Analyzes text content (e.g., from an email body) to produce a summary
        and determine its disposition.

        Args:
            raw_email_id (str): The ID of the original raw content (e.g., RawEmail.message_id).
            text_to_analyze (str): The primary text content for analysis (e.g., email body).
            subject_text (str, optional): Subject line or title, used to aid disposition.

        Returns:
            AnalyzedContent | None: An AnalyzedContent domain object if successful, else None.
        """
        if not raw_email_id:
            print("Error: raw_email_id is required for analysis.")
            return None
        if not text_to_analyze and not subject_text:
            print(f"Warning: Both text_to_analyze and subject_text are empty for raw_email_id '{raw_email_id}'. Analysis will be minimal.")
            # Still proceed, might result in default summary/disposition

        print(f"Analyzing content for raw_email_id: {raw_email_id}")

        try:
            # 1. Generate Summary
            # If text_to_analyze is empty, summary will be empty.
            summary = generate_summary_from_text(text_to_analyze, num_sentences=2) # Default 2 sentences

            # 2. Determine Disposition
            # Combine subject and body for a more comprehensive disposition analysis
            combined_text_for_disposition = f"{subject_text} {text_to_analyze}".strip()
            if not combined_text_for_disposition: # Handle case where both are empty
                 combined_text_for_disposition = "" # determine_content_disposition handles empty string

            disposition_details = determine_content_disposition(combined_text_for_disposition)
            disposition_category = disposition_details['category']
            keywords_matched = disposition_details['keywords_matched']

            # 3. Create AnalyzedContent domain object
            # The analysis_timestamp is set by the default factory in AnalyzedContent
            analyzed_data = AnalyzedContent(
                raw_email_id=raw_email_id,
                summary=summary,
                disposition=disposition_category,
                keywords_found=keywords_matched
                # analysis_timestamp will be auto-generated
            )

            print(f"Analysis complete for {raw_email_id}. Summary: '{summary[:50]}...', Disposition: {disposition_category}")

            # In a real app, this AnalyzedContent might be saved via a repository,
            # or returned to be part of a larger process flow leading to logging.
            # e.g., self.analyzed_content_repo.save(analyzed_data)
            # DomainEventPublisher.publish(ContentAnalyzedEvent(analyzed_data.raw_email_id, ...))

            return analyzed_data

        except Exception as e:
            print(f"An unexpected error occurred during content analysis for {raw_email_id}: {e}")
            return None

# Example usage (for testing purposes)
if __name__ == '__main__':
    print("\n--- AnalysisService Demonstration ---")
    service = AnalysisService()

    sample_email_id_1 = "service-demo-email-001"
    sample_subject_1 = "Request for Product Quote and Demo"
    sample_body_1 = """
    Hello Sales Team,
    We are very interested in your new WidgetPro product. Could you please provide us with a detailed quote?
    We would also like to schedule a product demo at your earliest convenience.
    Our company is looking to make a purchase decision by next month.
    Thank you for your time and assistance.
    """

    print(f"\nAnalyzing content for ID: {sample_email_id_1}")
    analysis_result_1 = service.analyze_text_content(
        raw_email_id=sample_email_id_1,
        text_to_analyze=sample_body_1,
        subject_text=sample_subject_1
    )

    if analysis_result_1:
        print("\nAnalysis Result 1:")
        print(f"  Raw Email ID: {analysis_result_1.raw_email_id}")
        print(f"  Summary: '{analysis_result_1.summary}'")
        print(f"  Disposition: {analysis_result_1.disposition}")
        print(f"  Keywords Found: {analysis_result_1.keywords_found}")
        print(f"  Analysis Timestamp: {analysis_result_1.analysis_timestamp}")
        assert analysis_result_1.disposition == "Sales Inquiry"

    sample_email_id_2 = "service-demo-email-002"
    sample_subject_2 = "Problem with recent update"
    sample_body_2 = "Hi support, since the last update, the application crashes on startup. I need help to resolve this issue. This is urgent."

    print(f"\nAnalyzing content for ID: {sample_email_id_2}")
    analysis_result_2 = service.analyze_text_content(
        raw_email_id=sample_email_id_2,
        text_to_analyze=sample_body_2,
        subject_text=sample_subject_2
    )

    if analysis_result_2:
        print("\nAnalysis Result 2:")
        print(f"  Summary: '{analysis_result_2.summary}'")
        print(f"  Disposition: {analysis_result_2.disposition}")
        assert analysis_result_2.disposition == "Support Request"

    sample_email_id_3 = "service-demo-email-003"
    sample_subject_3 = "Thank you"
    sample_body_3 = "Just a quick note to say thanks for the great service!" # No strong keywords

    print(f"\nAnalyzing content for ID: {sample_email_id_3}")
    analysis_result_3 = service.analyze_text_content(
        raw_email_id=sample_email_id_3,
        text_to_analyze=sample_body_3,
        subject_text=sample_subject_3
    )
    if analysis_result_3:
        print("\nAnalysis Result 3 (General):")
        print(f"  Summary: '{analysis_result_3.summary}'")
        print(f"  Disposition: {analysis_result_3.disposition}")
        assert analysis_result_3.disposition == "General Inquiry" # Default

    print("\n--- End of AnalysisService Demonstration ---")
