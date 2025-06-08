# Automated Activity Logger

## Description

This project automatically processes and logs activity from various engagement data sources, starting with email (.eml) files. It is architected using Domain-Driven Design (DDD) principles and an event-driven approach to decouple different stages of processing. It extracts key information, summarizes content, classifies it based on keywords, and logs these activities into a MongoDB database.

## Features

*   **Domain-Driven Design:** Organized into Bounded Contexts (`Ingestion`, `Analysis`, `ActivityLog`) for clear separation of concerns.
*   **Event-Driven Architecture:** Uses an in-process event dispatcher (`shared_kernel.events`) to signal completion of tasks (e.g., `EmailIngestedEvent`, `ContentAnalyzedEvent`) and trigger downstream processes.
*   **Email Parsing:** Parses `.eml` files to extract sender, recipient, subject, body, and other metadata.
*   **Text Summarization:** Generates a concise summary of the email body.
*   **Content Classification:** Categorizes emails based on keywords to determine disposition (e.g., "Sales Inquiry", "Support Request").
*   **MongoDB Logging:** Stores processed activity records in a MongoDB database using a repository pattern.
*   **Modular and Testable:** Core functionalities are well-defined within their contexts and layers, supported by unit tests.

## Architecture

The system is divided into several Bounded Contexts, each with its own domain, application services, and infrastructure components:

*   **`IngestionContext`**:
    *   **Responsibilities**: Handles the initial intake and parsing of raw data. Currently focused on `.eml` files.
    *   **Key Components**: `EmailParser` (infrastructure), `IngestionService` (application), `RawEmail` (domain model).
    *   **Output**: Publishes an `EmailIngestedEvent` containing data from the parsed email.

*   **`AnalysisContext`**:
    *   **Responsibilities**: Performs content analysis on ingested data. This includes text summarization and disposition classification.
    *   **Key Components**: `ContentAnalyzerTools` (application-level tools for summarization/disposition), `AnalysisService` (application), `AnalyzedContent` (domain model).
    *   **Input**: Subscribes to `EmailIngestedEvent`.
    *   **Output**: Publishes a `ContentAnalyzedEvent` with the analysis results.

*   **`ActivityLogContext`**:
    *   **Responsibilities**: Manages the storage and retrieval of finalized activity records.
    *   **Key Components**: `MongoActivityRepository` (infrastructure for MongoDB interaction), `LogService` (application), `ActivityRecord` (domain model).
    *   **Input**: Subscribes to `ContentAnalyzedEvent`.
    *   **Output**: Stores `ActivityRecord` instances in MongoDB.

*   **`SharedKernel`**:
    *   **Responsibilities**: Contains code shared across multiple contexts, primarily the eventing mechanism.
    *   **Key Components**: `DomainEvent` base class, specific event classes (`EmailIngestedEvent`, `ContentAnalyzedEvent`), and the `EventDispatcher`.

**Event Flow:**
1.  An email file is processed by `IngestionService`.
2.  Upon successful parsing, `IngestionService` publishes an `EmailIngestedEvent`.
3.  `AnalysisContext` (via `handle_email_ingested` handler) receives this event.
4.  `AnalysisService` is invoked to summarize and classify the content.
5.  `AnalysisContext` then publishes a `ContentAnalyzedEvent`.
6.  `ActivityLogContext` (via `handle_content_analyzed` handler) receives this event.
7.  `LogService` is invoked to create an `ActivityRecord` and store it in MongoDB via `MongoActivityRepository`.

## Project Structure

```
.
├── data/                     # Sample data (e.g., sample_email.eml)
├── src/                      # Source code
│   ├── activity_log_context/ # Manages storing activity records
│   │   ├── application/
│   │   ├── domain/
│   │   ├── infrastructure/
│   │   └── interfaces/       # Event handlers
│   ├── analysis_context/     # Content analysis (summarization, disposition)
│   │   ├── application/
│   │   ├── domain/
│   │   └── interfaces/       # Event handlers
│   ├── ingestion_context/    # Email parsing and initial data intake
│   │   ├── application/
│   │   ├── domain/
│   │   └── infrastructure/
│   ├── shared_kernel/        # Shared components like event dispatcher
│   │   └── events.py
│   ├── __init__.py           # Makes 'src' a package
│   └── main.py               # Main application entry point
├── tests/                    # Unit tests mirroring src structure
│   ├── activity_log_context/
│   ├── analysis_context/
│   ├── ingestion_context/
│   └── shared_kernel/
├── README.md                 # This file
└── requirements.txt          # Python dependencies (nltk, pymongo)
```

## Setup

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd <repository_name>
    ```

2.  **Install MongoDB:**
    *   This project uses MongoDB to store activity logs.
    *   Download and install MongoDB Community Edition from the [official MongoDB website](https://www.mongodb.com/try/download/community).
    *   Ensure your MongoDB server is running.

3.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    This will install `pymongo` (for MongoDB) and `nltk` (for potential future text processing enhancements).

5.  **MongoDB Configuration:**
    *   The application connects to MongoDB using the following environment variables:
        *   `MONGO_URI`: The MongoDB connection string (e.g., `mongodb://localhost:27017/`).
        *   `MONGO_DB_NAME`: The name of the database to use.
    *   If these environment variables are not set, it defaults to:
        *   URI: `mongodb://localhost:27017/`
        *   Database Name: `activity_db_default`
    *   The default collection name used is `activity_records`.

6.  **NLTK Data (for Summarization - future use):**
    The current summarizer uses a simple split-by-period method. If it's upgraded to use `nltk.sent_tokenize` for more advanced sentence tokenization, you will need to download the 'punkt' dataset:
    ```python
    # Run this in a Python interpreter after installing nltk
    import nltk
    nltk.download('punkt')
    ```

## Usage

The main script `src/main.py` is used to process a single email file, triggering the event-driven workflow.

```bash
python src/main.py --email-file path/to/your/email.eml
```

**Command-Line Arguments:**

*   `--email-file FILE_PATH` (Required): Path to the `.eml` file to be processed.
    *   Example: `data/sample_email.eml`

**Example:**
```bash
python src/main.py --email-file data/sample_email.eml
```
This will process `data/sample_email.eml`. The application will:
1.  Parse the email.
2.  Publish an `EmailIngestedEvent`.
3.  The AnalysisContext will handle this event, analyze the content, and publish a `ContentAnalyzedEvent`.
4.  The ActivityLogContext will handle this second event and store an `ActivityRecord` in MongoDB.

Check the console output for logs from the services and event handlers. Verify the data in your MongoDB instance (default database `activity_db_default`, collection `activity_records`).

## Running Tests

To run the suite of unit tests (which now mock external dependencies like MongoDB for repository tests):

```bash
python -m unittest discover tests
```
This command will automatically discover and run all tests within the `tests` directory. Ensure you have installed dependencies from `requirements.txt` first.

## Future Enhancements

*   **Asynchronous Event Handling:** Implement event handlers to run asynchronously (e.g., using `asyncio` or a task queue like Celery) for improved performance and resilience.
*   **Robust Eventing System:** Replace the in-process event dispatcher with a dedicated message broker (e.g., RabbitMQ, Kafka) for inter-service communication if the application grows into multiple services.
*   **API for Activity Logs:** Develop an API (e.g., REST or GraphQL) to query and retrieve logged activities from MongoDB.
*   **IMAP Integration for Email Ingestion:** Fetch emails directly from email servers.
*   **Advanced Text Analysis:** Incorporate more sophisticated NLP techniques for summarization (e.g., transformer models) and classification (e.g., ML models).
*   **Configuration Management:** Externalize configurations (keywords, model paths, etc.) into configuration files or environment variables more comprehensively.
*   **Full Repositories for All Contexts:** Implement repositories for `RawEmail` and `AnalyzedContent` if direct querying or persistence of these intermediate domain objects becomes necessary.
*   **Web Interface:** A simple UI for uploading emails or viewing logged activities.
*   **Batch Processing:** Support for processing multiple email files or other data sources in batch.
*   **Attachment Handling:** Extract and process information from email attachments.
*   **Distributed Tracing & Monitoring:** Implement tools for observing and debugging the event flow across contexts.
```
