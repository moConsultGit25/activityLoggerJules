import re

# Define categories and associated keywords
# For more advanced classification, consider NLP techniques or machine learning models.
CATEGORIES_KEYWORDS = {
    'Sales Inquiry': ['quote', 'proposal', 'demo', 'pricing', 'product information'],
    'Support Request': ['help', 'issue', 'problem', 'error', 'bug', 'assistance', 'trouble'],
    'Finance': ['invoice', 'payment', 'receipt', 'billing', 'statement'],
    'Job Application': ['resume', 'cv', 'career', 'hiring', 'position'],
}

DEFAULT_CATEGORY = "General"

def classify_email_content(text_content):
    """
    Classifies email content based on keywords.

    Args:
        text_content (str): The text content to classify (e.g., email body or subject).

    Returns:
        str: The determined category name.
    """
    if not text_content:
        return DEFAULT_CATEGORY

    text_lower = text_content.lower()

    for category, keywords in CATEGORIES_KEYWORDS.items():
        for keyword in keywords:
            # Using regex for whole word matching to avoid partial matches (e.g., 'error' in 'terrorist')
            if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', text_lower):
                return category

    return DEFAULT_CATEGORY

if __name__ == '__main__':
    test_cases = [
        ("Hello, I would like to request a quote for your services.", "Sales Inquiry"),
        ("I'm having an issue with the login page, can you help?", "Support Request"),
        ("Please find attached my payment receipt for invoice #123.", "Finance"),
        ("I am writing to apply for the software engineer position. My resume is attached.", "Job Application"),
        ("Thank you for your email.", "General"),
        ("There is a problem with the latest software update, it shows an error.", "Support Request"),
        ("We need a demo of your new product.", "Sales Inquiry"),
        ("Could you please check my billing statement?", "Finance"),
        ("This email is about a general inquiry.", "General"),
        ("", "General"), # Test empty string
        ("The product pricing is very competitive.", "Sales Inquiry"), # Test another sales keyword
        ("I need assistance with setting up my account.", "Support Request"), # Test another support keyword
        ("Where can I find my career opportunities?", "Job Application") # Test another job keyword
    ]

    for i, (content, expected_category) in enumerate(test_cases):
        classified_category = classify_email_content(content)
        print(f"Test Case {i+1}:")
        print(f"Content: \"{content}\"")
        print(f"Expected: {expected_category}, Got: {classified_category}")
        assert classified_category == expected_category, f"Test Case {i+1} Failed!"
        print("-" * 20)

    print("\nAll classification tests passed!")

    # Example of multiple matches (returns the first one found based on CATEGORIES_KEYWORDS definition order)
    multi_match_content = "I need help with a payment problem and also want a quote."
    print(f"Content: \"{multi_match_content}\"")
    print(f"Classified: {classify_email_content(multi_match_content)}")
    # Expected: Support Request (because 'help'/'problem' comes before 'quote' in keyword list and category definition)

    multi_match_content_sales_first = "I want a quote and also have a payment problem."
    print(f"Content: \"{multi_match_content_sales_first}\"")
    print(f"Classified: {classify_email_content(multi_match_content_sales_first)}")
    # Expected: Sales Inquiry (because 'quote' comes before 'payment'/'problem')
