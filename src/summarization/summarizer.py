# TODO: Upgrade to nltk.sent_tokenize for more robust sentence tokenization.
# import nltk
# nltk.download('punkt') # Ensure the 'punkt' tokenizer models are downloaded

def summarize_text(text, num_sentences=2):
    """
    Summarizes the given text by returning the first few sentences.

    Args:
        text (str): The text to summarize.
        num_sentences (int): The number of sentences to include in the summary.

    Returns:
        str: The summarized text.
    """
    if not text:
        return ""

    # Simple sentence splitting by period.
    # For more robust tokenization, consider using nltk.sent_tokenize.
    sentences = text.split('.')

    # Remove any empty strings that may result from multiple periods (e.g., "Hello... World")
    # or leading/trailing periods.
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return ""

    # Ensure num_sentences does not exceed the available number of sentences
    num_to_return = min(num_sentences, len(sentences))

    summary_sentences = sentences[:num_to_return]

    # Join the sentences back, adding a period at the end of each,
    # and ensure the last sentence also has a period.
    summary = ". ".join(summary_sentences)
    if summary and not summary.endswith('.'):
        summary += '.'

    return summary

if __name__ == '__main__':
    example_text_short = "This is a single sentence."
    example_text_long = "This is the first sentence. This is the second sentence. This is the third sentence. And this is the fourth sentence, which will be ignored."
    example_text_very_short = "One."
    example_text_empty = ""
    example_text_no_periods = "This is a text without any periods but it is still one sentence"

    print(f"Original: '{example_text_short}'")
    print(f"Summary (1 sentence): '{summarize_text(example_text_short, 1)}'")
    print(f"Summary (2 sentences): '{summarize_text(example_text_short, 2)}'\n")

    print(f"Original: '{example_text_long}'")
    print(f"Summary (default = 2 sentences): '{summarize_text(example_text_long)}'")
    print(f"Summary (1 sentence): '{summarize_text(example_text_long, 1)}'")
    print(f"Summary (3 sentences): '{summarize_text(example_text_long, 3)}'\n")

    print(f"Original: '{example_text_very_short}'")
    print(f"Summary (2 sentences): '{summarize_text(example_text_very_short, 2)}'\n")

    print(f"Original: '{example_text_empty}'")
    print(f"Summary (2 sentences): '{summarize_text(example_text_empty, 2)}'\n")

    print(f"Original: '{example_text_no_periods}'")
    print(f"Summary (2 sentences): '{summarize_text(example_text_no_periods, 2)}'\n")

    example_text_with_dots = "First sentence... Second one. Third."
    print(f"Original: '{example_text_with_dots}'")
    print(f"Summary (2 sentences): '{summarize_text(example_text_with_dots, 2)}'\n")
