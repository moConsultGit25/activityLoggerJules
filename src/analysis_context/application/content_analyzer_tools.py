# src/analysis_context/application/content_analyzer_tools.py
import re
from typing import List, Dict, Any # Added for clarity

# --- Summarization Logic ---
# TODO: Upgrade to nltk.sent_tokenize for more robust sentence tokenization.
# import nltk
# nltk.download('punkt') # Ensure the 'punkt' tokenizer models are downloaded

def generate_summary_from_text(text: str, num_sentences: int = 2) -> str:
    """
    Generates a summary from the given text by returning the first few sentences.

    Args:
        text (str): The text to summarize.
        num_sentences (int): The number of sentences to include in the summary.

    Returns:
        str: The summarized text.
    """
    if not text:
        return ""

    # Simple sentence splitting by period.
    sentences = text.split('.')

    # Remove any empty strings and strip whitespace
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return ""

    num_to_return = min(num_sentences, len(sentences))
    summary_sentences = sentences[:num_to_return]

    summary = ". ".join(summary_sentences)
    if summary and not summary.endswith('.'):
        summary += '.'

    return summary

# --- Disposition Logic ---

# Define categories and associated keywords
# These could be loaded from a configuration file or a database in a more advanced system.
DEFAULT_DISPOSITION_CATEGORIES: Dict[str, List[str]] = {
    'Sales Inquiry': ['quote', 'proposal', 'demo', 'pricing', 'product information', 'buy', 'purchase'],
    'Support Request': ['help', 'issue', 'problem', 'error', 'bug', 'assistance', 'trouble', 'cannot', 'unable'],
    'Finance': ['invoice', 'payment', 'receipt', 'billing', 'statement', 'refund'],
    'Job Application': ['resume', 'cv', 'career', 'hiring', 'position', 'apply', 'job'],
    'Feedback': ['feedback', 'suggestion', 'opinion', 'improvement'],
    'Information Request': ['information', 'details', 'question', 'how to'],
}

DEFAULT_DISPOSITION_CATEGORY = "General Inquiry"

def determine_content_disposition(
    text_content: str,
    categories_keywords: Dict[str, List[str]] = None
) -> Dict[str, Any]:
    """
    Determines the disposition of email content based on keywords.

    Args:
        text_content (str): The text content to classify (e.g., email body or subject).
        categories_keywords (Dict[str, List[str]], optional): Custom categories and keywords.
            Defaults to DEFAULT_DISPOSITION_CATEGORIES.

    Returns:
        Dict[str, Any]: A dictionary containing:
            'category' (str): The determined category name.
            'keywords_matched' (List[str]): List of keywords that led to the classification.
    """
    if categories_keywords is None:
        categories_keywords = DEFAULT_DISPOSITION_CATEGORIES

    if not text_content:
        return {'category': DEFAULT_DISPOSITION_CATEGORY, 'keywords_matched': []}

    text_lower = text_content.lower()
    matched_keywords_overall: List[str] = []

    for category, keywords in categories_keywords.items():
        category_matched_keywords: List[str] = []
        for keyword in keywords:
            # Using regex for whole word matching
            if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', text_lower):
                category_matched_keywords.append(keyword)

        if category_matched_keywords:
            # For simplicity, return the first category that has any keyword match.
            # A more sophisticated system might score or prioritize.
            return {'category': category, 'keywords_matched': category_matched_keywords}

    return {'category': DEFAULT_DISPOSITION_CATEGORY, 'keywords_matched': []}


# Example usage for direct testing of these tools (can be kept or removed)
if __name__ == '__main__':
    print("--- Testing content_analyzer_tools ---")

    # Test Summarizer
    print("\nTesting generate_summary_from_text:")
    test_summary_text = "This is sentence one. This is sentence two. This is sentence three, which should be cut off."
    summary = generate_summary_from_text(test_summary_text, 2)
    print(f"Original: '{test_summary_text}'")
    print(f"Summary (2 sentences): '{summary}'")
    assert summary == "This is sentence one. This is sentence two."

    summary_short = generate_summary_from_text("One sentence only.", 2)
    print(f"Original: 'One sentence only.'")
    print(f"Summary (2 sentences for short text): '{summary_short}'")
    assert summary_short == "One sentence only."

    # Test Disposition
    print("\nTesting determine_content_disposition:")
    test_disposition_text_sales = "I would like to request a new quote for your services."
    disposition_result_sales = determine_content_disposition(test_disposition_text_sales)
    print(f"Text: '{test_disposition_text_sales}' -> Disposition: {disposition_result_sales}")
    assert disposition_result_sales['category'] == 'Sales Inquiry'
    assert 'quote' in disposition_result_sales['keywords_matched']

    test_disposition_text_support = "I have an issue with my account login."
    disposition_result_support = determine_content_disposition(test_disposition_text_support)
    print(f"Text: '{test_disposition_text_support}' -> Disposition: {disposition_result_support}")
    assert disposition_result_support['category'] == 'Support Request'
    assert 'issue' in disposition_result_support['keywords_matched']

    test_disposition_text_general = "Just saying hello."
    disposition_result_general = determine_content_disposition(test_disposition_text_general)
    print(f"Text: '{test_disposition_text_general}' -> Disposition: {disposition_result_general}")
    assert disposition_result_general['category'] == DEFAULT_DISPOSITION_CATEGORY
    assert not disposition_result_general['keywords_matched']

    print("\n--- End of content_analyzer_tools tests ---")
