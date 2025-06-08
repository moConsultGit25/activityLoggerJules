import unittest

# Adjust import path
from src.disposition.classifier import classify_email_content, CATEGORIES_KEYWORDS, DEFAULT_CATEGORY

class TestClassifier(unittest.TestCase):

    def test_classify_keywords_sales(self):
        text = "I would like to get a quote for your amazing product."
        self.assertEqual(classify_email_content(text), "Sales Inquiry")

        text_proposal = "Please find attached our proposal documents."
        self.assertEqual(classify_email_content(text_proposal), "Sales Inquiry")

    def test_classify_keywords_support(self):
        text = "I'm having an issue with the login, can you help?"
        self.assertEqual(classify_email_content(text), "Support Request")

        text_error = "The system shows an error message frequently."
        self.assertEqual(classify_email_content(text_error), "Support Request")

    def test_classify_keywords_finance(self):
        text = "Where can I find my latest invoice?"
        self.assertEqual(classify_email_content(text), "Finance")

        text_payment = "We have processed the payment for order #123."
        self.assertEqual(classify_email_content(text_payment), "Finance")

    def test_classify_keywords_job_application(self):
        text = "I am interested in the advertised position, my resume is attached."
        self.assertEqual(classify_email_content(text), "Job Application")

        text_cv = "Submitting my CV for the software developer role."
        self.assertEqual(classify_email_content(text_cv), "Job Application")


    def test_classify_no_keywords(self):
        text = "This is a general email without any specific actionable keywords."
        self.assertEqual(classify_email_content(text), DEFAULT_CATEGORY)

    def test_classify_case_insensitivity(self):
        text_sales_upper = "Can I get a QUOTE?"
        self.assertEqual(classify_email_content(text_sales_upper), "Sales Inquiry")

        text_support_mixed = "There is a Problem with the application."
        self.assertEqual(classify_email_content(text_support_mixed), "Support Request")

    def test_classify_empty_input(self):
        text = ""
        self.assertEqual(classify_email_content(text), DEFAULT_CATEGORY)

    def test_classify_none_input(self):
        text = None
        self.assertEqual(classify_email_content(text), DEFAULT_CATEGORY)

    def test_classify_whole_word_matching(self):
        # Ensure 'error' in 'terrorist' is not matched for 'Support Request'
        # but 'error' as a whole word is.
        text_partial_match_negative = "This email talks about a terrorist incident."
        self.assertEqual(classify_email_content(text_partial_match_negative), DEFAULT_CATEGORY)

        text_whole_word_positive = "I found an error in the report."
        self.assertEqual(classify_email_content(text_whole_word_positive), "Support Request")

        text_keyword_with_punctuation = "Need help, please!"
        self.assertEqual(classify_email_content(text_keyword_with_punctuation), "Support Request")

    def test_multiple_keywords_first_match(self):
        # Based on CATEGORIES_KEYWORDS definition order and keyword order within each category.
        # 'Support Request' keywords like 'help', 'issue', 'problem' are typically checked before 'Sales Inquiry' like 'quote'.
        # Let's check the actual definition order in classifier.py
        # CATEGORIES_KEYWORDS = {
        #    'Sales Inquiry': ['quote', ...],
        #    'Support Request': ['help', ...], ... }
        # So 'Sales Inquiry' is checked first.

        text = "I want a quote, but I also have a problem with my account."
        # 'quote' is in 'Sales Inquiry', 'problem' is in 'Support Request'.
        # 'Sales Inquiry' is defined before 'Support Request' in CATEGORIES_KEYWORDS.
        self.assertEqual(classify_email_content(text), "Sales Inquiry")

        text_reverse_order_categories = "I have a problem with my account, and I also want a quote."
        # Still 'Sales Inquiry' because it's the first *category* checked that has a match.
        self.assertEqual(classify_email_content(text_reverse_order_categories), "Sales Inquiry")

        # If we want to test preference of keywords *within* a category, that's implicit.
        # If 'help' and 'issue' are in 'Support Request', 'help' appearing first in text doesn't guarantee
        # it's found before 'issue' if 'issue' is earlier in the keyword list for that category.
        # The current code iterates categories, then keywords in that category.
        # So, the order of keywords in the list for 'Sales Inquiry' matters if multiple sales keywords are present.

if __name__ == '__main__':
    unittest.main()
