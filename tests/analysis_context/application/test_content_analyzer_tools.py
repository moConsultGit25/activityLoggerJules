# tests/analysis_context/application/test_content_analyzer_tools.py
import unittest
from src.analysis_context.application.content_analyzer_tools import (
    generate_summary_from_text,
    determine_content_disposition,
    DEFAULT_DISPOSITION_CATEGORY,
    DEFAULT_DISPOSITION_CATEGORIES
)

class TestContentAnalyzerTools(unittest.TestCase):

    # --- Tests for generate_summary_from_text ---
    def test_generate_summary_basic(self):
        text = "This is the first sentence. This is the second sentence. This is the third sentence."
        summary = generate_summary_from_text(text, num_sentences=2)
        expected_summary = "This is the first sentence. This is the second sentence."
        self.assertEqual(summary, expected_summary)

    def test_generate_summary_short_text(self):
        text = "This is a single sentence."
        summary = generate_summary_from_text(text, num_sentences=2)
        expected_summary = "This is a single sentence." # Returns all available sentences
        self.assertEqual(summary, expected_summary)

    def test_generate_summary_empty_text(self):
        text = ""
        summary = generate_summary_from_text(text, num_sentences=2)
        expected_summary = ""
        self.assertEqual(summary, expected_summary)

    def test_generate_summary_no_periods(self):
        text = "This is a long text without any periods just one continuous line"
        # Current simple implementation treats this as one sentence
        summary = generate_summary_from_text(text, num_sentences=1)
        expected_summary = "This is a long text without any periods just one continuous line."
        self.assertEqual(summary, expected_summary)

    def test_generate_summary_multiple_dots_and_spaces(self):
        text = "Sentence one...  Sentence two.  . Sentence three. "
        summary = generate_summary_from_text(text, num_sentences=2)
        # Expected: "Sentence one. Sentence two." (after stripping empty strings from split)
        expected_summary = "Sentence one. Sentence two."
        self.assertEqual(summary, expected_summary)

    # --- Tests for determine_content_disposition ---
    def test_determine_disposition_sales_inquiry(self):
        text = "I need a price quote for your product."
        result = determine_content_disposition(text)
        self.assertEqual(result['category'], "Sales Inquiry")
        self.assertIn("quote", result['keywords_matched'])
        self.assertIn("price", result['keywords_matched']) # Assuming 'pricing' implies 'price'

    def test_determine_disposition_support_request(self):
        text = "I'm having an issue with the login, it shows an error."
        result = determine_content_disposition(text)
        self.assertEqual(result['category'], "Support Request")
        self.assertIn("issue", result['keywords_matched'])
        self.assertIn("error", result['keywords_matched'])

    def test_determine_disposition_finance(self):
        text = "Please send me the invoice for my last payment."
        result = determine_content_disposition(text)
        self.assertEqual(result['category'], "Finance")
        self.assertIn("invoice", result['keywords_matched'])
        self.assertIn("payment", result['keywords_matched'])

    def test_determine_disposition_job_application(self):
        text = "I am applying for the advertised position, my resume is attached."
        result = determine_content_disposition(text)
        self.assertEqual(result['category'], "Job Application")
        self.assertIn("applying", result['keywords_matched']) # 'apply'
        self.assertIn("position", result['keywords_matched'])
        self.assertIn("resume", result['keywords_matched'])

    def test_determine_disposition_no_keywords(self):
        text = "This is a general email without any specific actionable items."
        result = determine_content_disposition(text)
        self.assertEqual(result['category'], DEFAULT_DISPOSITION_CATEGORY)
        self.assertEqual(len(result['keywords_matched']), 0)

    def test_determine_disposition_case_insensitivity(self):
        text = "Can I get a QUOTE for your services? Also, what is the PRICING?"
        result = determine_content_disposition(text)
        self.assertEqual(result['category'], "Sales Inquiry")
        self.assertIn("quote", result['keywords_matched'])
        self.assertIn("pricing", result['keywords_matched'])

    def test_determine_disposition_empty_input(self):
        text = ""
        result = determine_content_disposition(text)
        self.assertEqual(result['category'], DEFAULT_DISPOSITION_CATEGORY)
        self.assertEqual(len(result['keywords_matched']), 0)

    def test_determine_disposition_whole_word_matching(self):
        # 'error' in 'terrorist' should not match 'Support Request'
        text_partial_negative = "This email discusses a terrorist incident."
        result_negative = determine_content_disposition(text_partial_negative)
        self.assertEqual(result_negative['category'], DEFAULT_DISPOSITION_CATEGORY)

        text_whole_word_positive = "I found an error in the software."
        result_positive = determine_content_disposition(text_whole_word_positive)
        self.assertEqual(result_positive['category'], "Support Request")
        self.assertIn("error", result_positive['keywords_matched'])

    def test_determine_disposition_first_category_match(self):
        # 'Sales Inquiry' is defined before 'Support Request' in DEFAULT_DISPOSITION_CATEGORIES
        # 'quote' is a sales keyword, 'issue' is a support keyword.
        text_multiple_categories = "I need a quote for a new project, but I also have an issue with my current subscription."
        result = determine_content_disposition(text_multiple_categories)
        self.assertEqual(result['category'], "Sales Inquiry") # 'Sales Inquiry' should be matched first
        self.assertIn("quote", result['keywords_matched'])
        self.assertNotIn("issue", result['keywords_matched']) # Because it returns on first category match

if __name__ == '__main__':
    unittest.main()
