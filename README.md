# Automated Activity Logger

## Description

This project provides a suite of tools to automatically process and log activity from various engagement data sources, starting with email (.eml) files. It extracts key information, summarizes content, classifies it based on keywords, and logs these activities into a structured CSV format.

## Features

*   **Email Parsing:** Parses `.eml` files to extract sender, recipient, subject, and body content.
*   **Text Summarization:** Generates a concise summary of the email body (currently first N sentences).
*   **Content Classification:** Categorizes emails based on keywords found in their content (e.g., "Sales Inquiry", "Support Request").
*   **CSV Logging:** Logs processed data, including timestamps, email details, summary, and classification, to a CSV file.
*   **Modular Design:** Core functionalities (ingestion, summarization, disposition, logging) are separated into distinct modules.
*   **Unit Tested:** Includes a suite of unit tests for core components.

## Project Structure

```
.
├── data/                     # Directory for sample data, log outputs
│   └── sample_email.eml
├── src/                      # Source code
│   ├── ingestion/            # Email parsing module
│   │   └── email_processor.py
│   ├── summarization/        # Text summarization module
│   │   └── summarizer.py
│   ├── disposition/          # Content classification module
│   │   └── classifier.py
│   ├── logging/              # Activity logging module
│   │   └── logger.py
│   ├── __init__.py
│   └── main.py               # Core orchestration script
├── tests/                    # Unit tests
│   ├── ingestion/
│   ├── summarization/
│   ├── disposition/
│   ├── logging/
│   └── __init__.py
├── README.md                 # This file
└── requirements.txt          # Python dependencies
```

*   `data/`: Contains sample data for testing and is the default output directory for logs.
*   `src/`: Contains the main application Python modules.
*   `tests/`: Contains unit tests for the modules in `src/`.

## Setup

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd <repository_name>
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **NLTK Data (for Summarization):**
    The current summarizer uses a simple split-by-period method. If it's upgraded to use `nltk.sent_tokenize` for more advanced sentence tokenization, you will need to download the 'punkt' dataset:
    ```python
    import nltk
    nltk.download('punkt')
    ```
    Run this in a Python interpreter after installing `nltk`.

## Usage

The main script `src/main.py` is used to process a single email file and log its activity.

```bash
python src/main.py --email-file path/to/your/email.eml --log-file path/to/your/logfile.csv
```

**Command-Line Arguments:**

*   `--email-file FILE_PATH` (Required): Path to the `.eml` file to be processed.
    *   Example: `data/sample_email.eml`
*   `--log-file LOG_PATH` (Optional): Path to the CSV file where activity will be logged.
    *   Defaults to: `data/activity_log.csv`

**Example:**

```bash
python src/main.py --email-file data/sample_email.eml
```
This will process `data/sample_email.eml` and save the log to `data/activity_log.csv`.

To use a custom log file:
```bash
python src/main.py --email-file data/sample_email.eml --log-file custom_logs/my_activity.csv
```
*(Ensure the `custom_logs` directory exists or the script has permissions to create it if it's part of the logger's capability, which it is for the immediate parent directory of the log file).*

## Running Tests

To run the suite of unit tests, navigate to the project root directory and execute:

```bash
python -m unittest discover tests
```
This command will automatically discover and run all tests within the `tests` directory. Ensure you have installed dependencies from `requirements.txt` first.

## Future Enhancements

*   **IMAP Integration:** Add functionality to fetch emails directly from an email server (e.g., Gmail, Outlook) via IMAP.
*   **Advanced Summarization:** Implement more sophisticated summarization techniques (e.g., TF-IDF, TextRank, or transformer-based models).
*   **Machine Learning Classification:** Replace or augment keyword-based classification with a machine learning model for improved accuracy and flexibility.
*   **Database Logging:** Option to log activities to a database (e.g., SQLite, PostgreSQL) instead of/in addition to CSV.
*   **Web Interface:** A simple web interface (e.g., using Flask or Django) to upload emails or view logged activities.
*   **Batch Processing:** Support for processing multiple email files from a directory.
*   **Configuration File:** Manage settings like categories, keywords, and log paths through a configuration file.
*   **Attachment Handling:** Extract and process information from email attachments.
```
