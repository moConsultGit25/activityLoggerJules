# tests/analysis_context/application/test_analysis_service.py
import unittest
from unittest.mock import patch
import datetime

from src.analysis_context.application.analysis_service import AnalysisService
from src.analysis_context.domain.analyzed_content import AnalyzedContent

class TestAnalysisService(unittest.TestCase):

    @patch('src.analysis_context.application.analysis_service.generate_summary_from_text')
    @patch('src.analysis_context.application.analysis_service.determine_content_disposition')
    def test_analyze_text_content_success(self, mock_determine_disposition, mock_generate_summary):
        # --- Arrange ---
        raw_email_id = "test_raw_email_id_123"
        text_to_analyze = "This is the main body of the email. It contains important information that needs summarization and classification."
        subject_text = "Important Subject for Analysis"

        # Mock return values for the tools
        expected_summary = "This is the main body of the email."
        mock_generate_summary.return_value = expected_summary

        expected_disposition_details = {'category': "Sales Inquiry", 'keywords_matched': ["important", "information"]}
        mock_determine_disposition.return_value = expected_disposition_details

        service = AnalysisService()

        # --- Act ---
        result_analyzed_content = service.analyze_text_content(
            raw_email_id=raw_email_id,
            text_to_analyze=text_to_analyze,
            subject_text=subject_text
        )

        # --- Assert ---
        # 1. Verify tools were called correctly
        mock_generate_summary.assert_called_once_with(text_to_analyze, num_sentences=2)
        mock_determine_disposition.assert_called_once_with(f"{subject_text} {text_to_analyze}".strip())

        # 2. Verify AnalyzedContent object is created correctly
        self.assertIsNotNone(result_analyzed_content)
        self.assertIsInstance(result_analyzed_content, AnalyzedContent)
        self.assertEqual(result_analyzed_content.raw_email_id, raw_email_id)
        self.assertEqual(result_analyzed_content.summary, expected_summary)
        self.assertEqual(result_analyzed_content.disposition, expected_disposition_details['category'])
        self.assertEqual(result_analyzed_content.keywords_found, expected_disposition_details['keywords_matched'])
        self.assertIsNotNone(result_analyzed_content.analysis_timestamp) # Should be set by default factory

    @patch('src.analysis_context.application.analysis_service.generate_summary_from_text')
    @patch('src.analysis_context.application.analysis_service.determine_content_disposition')
    def test_analyze_text_content_empty_inputs(self, mock_determine_disposition, mock_generate_summary):
        # --- Arrange ---
        raw_email_id = "empty_input_test_id"
        text_to_analyze = ""
        subject_text = ""

        mock_generate_summary.return_value = "" # Expected for empty text
        mock_determine_disposition.return_value = {'category': "General Inquiry", 'keywords_matched': []} # Expected for empty

        service = AnalysisService()

        # --- Act ---
        result = service.analyze_text_content(raw_email_id, text_to_analyze, subject_text)

        # --- Assert ---
        mock_generate_summary.assert_called_once_with("", num_sentences=2)
        mock_determine_disposition.assert_called_once_with("")

        self.assertIsNotNone(result)
        self.assertEqual(result.summary, "")
        self.assertEqual(result.disposition, "General Inquiry")

    def test_analyze_text_content_no_raw_email_id(self):
        # --- Arrange ---
        service = AnalysisService()
        # --- Act ---
        result = service.analyze_text_content(raw_email_id="", text_to_analyze="Some text", subject_text="Sub")
        # --- Assert ---
        self.assertIsNone(result) # Service should return None if raw_email_id is missing


if __name__ == '__main__':
    unittest.main()
