import unittest

# Adjust import path
from src.summarization.summarizer import summarize_text

class TestSummarizer(unittest.TestCase):

    def test_summarize_basic(self):
        text = "This is the first sentence. This is the second sentence. This is the third sentence."
        summary = summarize_text(text, num_sentences=2)
        expected_summary = "This is the first sentence. This is the second sentence."
        self.assertEqual(summary, expected_summary)

    def test_summarize_short_text(self):
        text = "This is a single sentence."
        summary = summarize_text(text, num_sentences=2)
        expected_summary = "This is a single sentence."
        self.assertEqual(summary, expected_summary)

    def test_summarize_empty_text(self):
        text = ""
        summary = summarize_text(text, num_sentences=2)
        expected_summary = ""
        self.assertEqual(summary, expected_summary)

    def test_summarize_custom_num_sentences(self):
        text = "Sentence one. Sentence two. Sentence three. Sentence four."
        summary = summarize_text(text, num_sentences=3)
        expected_summary = "Sentence one. Sentence two. Sentence three."
        self.assertEqual(summary, expected_summary)

    def test_summarize_no_periods(self):
        text = "This is a long text without any periods just one continuous line"
        summary = summarize_text(text, num_sentences=1)
        # Current implementation splits by '.', so this will be treated as one sentence.
        expected_summary = "This is a long text without any periods just one continuous line."
        self.assertEqual(summary, expected_summary)

    def test_summarize_text_with_leading_trailing_spaces_in_sentences(self):
        text = "  Sentence one.   Sentence two  . Sentence three. "
        summary = summarize_text(text, num_sentences=2)
        expected_summary = "Sentence one. Sentence two."
        self.assertEqual(summary, expected_summary)

    def test_summarize_text_fewer_sentences_than_requested(self):
        text = "Just one sentence here."
        summary = summarize_text(text, num_sentences=5)
        expected_summary = "Just one sentence here."
        self.assertEqual(summary, expected_summary)

    def test_summarize_text_with_multiple_dots(self):
        text = "First sentence... Second one. Third."
        # Current implementation: "First sentence", "", "", " Second one", " Third"
        summary = summarize_text(text, num_sentences=2)
        expected_summary = "First sentence. Second one." # After stripping empty ones
        self.assertEqual(summary, expected_summary)

if __name__ == '__main__':
    unittest.main()
