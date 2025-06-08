# Automated Activity Logger

## Description

This project automatically processes and logs activity from various engagement data sources, starting with email (.eml) files. It is architected using Domain-Driven Design (DDD) principles and an event-driven approach to decouple different stages of processing. It extracts key information, summarizes content, classifies it based on keywords, and logs these activities into a MongoDB database. An API is also provided for programmatic interaction.

## Features

*   **Domain-Driven Design:** Organized into Bounded Contexts (`Ingestion`, `Analysis`, `ActivityLog`, `Auth`) for clear separation of concerns.
*   **Event-Driven Architecture:** Uses an in-process event dispatcher (`shared_kernel.events`) to signal completion of tasks (e.g., `EmailIngestedEvent`, `ContentAnalyzedEvent`) and trigger downstream processes.
*   **FastAPI Web API:** Provides endpoints for ingesting emails, retrieving activity logs, user registration, and login.
*   **Email Parsing:** Parses `.eml` files (local upload or from Microsoft Graph).
*   **Cloud Email Ingestion:** Supports fetching emails from Microsoft 365 mailboxes via Microsoft Graph API.
*   **Text Summarization:** Generates a concise summary of the email body.
*   **Content Classification:** Categorizes emails based on keywords to determine disposition.
*   **MongoDB Storage:** Uses MongoDB for storing user credentials and processed activity records.
*   **JWT Authentication:** Secures API endpoints using JSON Web Tokens.
*   **Containerized:** Provides `Dockerfile` and `docker-compose.yml` for easy setup and deployment.
*   **Modular and Testable:** Core functionalities are well-defined and supported by unit tests.

## Architecture

The system is divided into several Bounded Contexts: `IngestionContext`, `AnalysisContext`, `ActivityLogContext`, `AuthContext`, and a `SharedKernel` for eventing. (Refer to previous descriptions for details on each context and the event flow).

## Project Structure

```
.
├── data/                     # Sample data (e.g., sample_email.eml)
├── src/                      # Source code
│   ├── activity_log_context/
│   ├── analysis_context/
│   ├── api/                    # FastAPI application (src.api.main:app)
│   │   ├── v1/
│   │   │   ├── routers/
│   │   │   └── schemas/
│   │   └── main.py
│   ├── auth_context/
│   ├── frontend/             # Jinja2 templates, static files, frontend routers
│   │   ├── routers/
│   │   ├── static/
│   │   └── templates/
│   ├── ingestion_context/
│   ├── shared_kernel/
│   ├── __init__.py
│   └── main.py               # CLI entry point (src.main:main)
├── tests/
├── .dockerignore             # Files to ignore in Docker image
├── Dockerfile                # Instructions to build the application image
├── docker-compose.yml        # Defines services, networks, and volumes for Docker
├── DEPLOYMENT_GCP.md         # Example deployment plan for Google Cloud Platform
├── README.md
└── requirements.txt
```

## Setup

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd <repository_name>
    ```

2.  **Install Docker and Docker Compose:**
    *   If you plan to run the application using Docker (recommended for a consistent environment), ensure you have Docker Desktop (for Mac/Windows) or Docker Engine & Docker Compose (for Linux) installed.
    *   See [Docker documentation](https://docs.docker.com/get-docker/) for installation instructions.

3.  **Install MongoDB (if not using Docker's MongoDB service):**
    *   If you prefer to run MongoDB natively, install it from the [official MongoDB website](https://www.mongodb.com/try/download/community) and ensure it's running. You'll need to adjust `MONGO_URI` environment variable accordingly if not using `mongodb://mongo:27017`.

4.  **Create a Virtual Environment (for local development without Docker):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

5.  **Install Dependencies (for local development without Docker):**
    ```bash
    pip install -r requirements.txt
    ```
    This installs `pymongo`, `fastapi`, `uvicorn`, `passlib[bcrypt]`, `python-jose[cryptography]`, `msal`, `jinja2`, `httpx`, etc.

6.  **Environment Variables for Configuration:**
    *   Create a `.env` file in the project root for local development (this file is in `.gitignore`). Docker Compose will automatically pick it up.
    *   **Example `.env` file content:**
        ```env
        # MongoDB
        MONGO_URI="mongodb://mongo:27017/activity_db_docker_dev" # Use 'mongo' as hostname for Docker Compose service
        # MONGO_URI="mongodb://localhost:27017/activity_db_local_dev" # For local MongoDB
        AUTH_MONGO_DB_NAME="auth_db_docker_dev"
        # AUTH_MONGO_DB_NAME="auth_db_local_dev" # For local MongoDB

        # JWT Authentication
        JWT_SECRET_KEY="a_very_strong_and_random_secret_key_for_development_only" # CHANGE THIS!
        ACCESS_TOKEN_EXPIRE_MINUTES="60"

        # Microsoft Graph API (Optional - for cloud email ingestion)
        # Obtain these from your Azure App Registration
        AZURE_CLIENT_ID=""
        AZURE_CLIENT_SECRET=""
        AZURE_TENANT_ID=""
        GRAPH_TARGET_USER_ID="" # e.g., user@yourdomain.com or Azure AD User Object ID
        GRAPH_MAIL_FOLDER="Inbox" # Optional, defaults to Inbox
        ```
    *   **Important Notes on Environment Variables:**
        *   For Dockerized deployment, these variables are typically set within the `docker-compose.yml` or injected by the deployment platform. The `docker-compose.yml` provided uses `${VAR_NAME}` substitution, which means it will try to get values from your shell environment or a `.env` file in the same directory as `docker-compose.yml`.
        *   `JWT_SECRET_KEY`: **Crucial for production.** Must be a strong, unique, random string.
        *   Azure credentials are required only if you intend to use the Microsoft Graph email ingestion feature. Your Azure AD App Registration needs appropriate API permissions (e.g., `Mail.Read` for the application).

7.  **NLTK Data (for Summarization - future use):**
    The current summarizer is simple. For advanced `nltk.sent_tokenize`:
    ```python
    import nltk
    nltk.download('punkt')
    ```

## Running with Docker (Recommended for Development & Production-like Environment)

1.  **Ensure Docker and Docker Compose are installed.** (See Setup step 2).
2.  **Set up Environment Variables:**
    *   Create a `.env` file in the project root as described in "Setup" (step 6), especially for `JWT_SECRET_KEY` and any Azure credentials if you plan to test Graph ingestion. The `docker-compose.yml` is configured to use these.
3.  **Build and Run the Services:**
    Navigate to the project root directory (where `docker-compose.yml` is located) and run:
    ```bash
    docker-compose up --build
    ```
    *   `--build`: Forces Docker to rebuild the `backend` image if `Dockerfile` or application code has changed.
    *   This command will start two services: `backend` (your FastAPI application) and `mongo` (the MongoDB database).
    *   The `backend` service's port 8000 is mapped to port 8000 on your host machine.
    *   MongoDB's port 27017 is mapped to port 27017 on your host.
    *   MongoDB data will be persisted in a Docker named volume (`mongodb_data`), so it survives container restarts.
4.  **Accessing the Application:**
    *   **API:** `http://localhost:8000` (API root, returns JSON message)
    *   **API Docs (Swagger UI):** `http://localhost:8000/docs`
    *   **API Docs (ReDoc):** `http://localhost:8000/redoc`
    *   **Frontend Web Interface:** `http://localhost:8000/app/` (e.g., `http://localhost:8000/app/login`)
5.  **Stopping the Application:**
    Press `Ctrl+C` in the terminal where `docker-compose up` is running. To remove the containers (but not the MongoDB data volume):
    ```bash
    docker-compose down
    ```
    To remove containers AND the data volume (useful for a clean start):
    ```bash
    docker-compose down -v
    ```

## Usage (Local Development without Docker)

If you are not using Docker:

1.  Ensure MongoDB is running locally and accessible (adjust `MONGO_URI` in your environment or `.env` file if not using `mongodb://localhost:27017/`).
2.  Set all required environment variables (see Setup step 6).
3.  **Run the API server:**
    ```bash
    uvicorn src.api.main:app --reload
    ```
    Access points are the same as with Docker (API at `http://localhost:8000`, Frontend at `http://localhost:8000/app/`).
4.  **CLI for Email File Processing:**
    ```bash
    python src/main.py --email-file data/sample_email.eml
    ```

Check console output for logs. Verify data in your MongoDB instance.

## Running Tests

To run unit tests (mocking external dependencies):
```bash
python -m unittest discover tests
```

## Deployment

For an example deployment plan to Google Cloud Platform (GCP), detailing the use of services like Cloud Run, Artifact Registry, MongoDB Atlas, and Secret Manager, see [DEPLOYMENT_GCP.md](DEPLOYMENT_GCP.md).

## Future Enhancements
(List remains largely the same as previous version, with "Containerization" now implemented)
*   **Full User Authentication API Endpoints:** (Partially done, needs e.g. /users/me, password reset etc.)
*   **Asynchronous Event Handling.**
*   **Robust Eventing System (RabbitMQ/Kafka).**
*   **API for Querying Specific Logs with advanced filtering.**
*   **IMAP Integration.**
*   **Advanced NLP.**
*   **Comprehensive Configuration Management.**
*   **Repositories for `RawEmail` and `AnalyzedContent`.**
*   **Web Interface (more features beyond login, register, dashboard).**
*   **Batch Processing.**
*   **Attachment Handling.**
*   **Distributed Tracing & Monitoring.**
```
