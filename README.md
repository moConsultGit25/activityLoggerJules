# Automated Activity Logger

## Description

This project automatically processes and logs activity from various engagement data sources. Initially focused on email (.eml) files (processed via local upload or from Microsoft 365 mailboxes using Microsoft Graph API), it can be extended for other data sources. The system is architected using Domain-Driven Design (DDD) principles and an event-driven approach to decouple different stages of processing. It extracts key information, summarizes content, classifies it based on keywords, and logs these activities into a MongoDB database. A FastAPI web application provides an API for interactions and a basic frontend interface.

## Features

*   **Domain-Driven Design:** Organized into Bounded Contexts (`IngestionContext`, `AnalysisContext`, `ActivityLogContext`, `AuthContext`) for clear separation of concerns.
*   **Event-Driven Architecture:** Uses an in-process event dispatcher (`shared_kernel.events`) for decoupled communication between contexts.
*   **FastAPI Web App:**
    *   Backend API for ingestion, activity log retrieval, user registration, and login.
    *   Basic Jinja2-templated frontend for user interaction (login, registration, dashboard, EML upload, cloud sync trigger).
*   **Email Ingestion Sources:**
    *   Local `.eml` file uploads via API or frontend.
    *   Cloud email ingestion from Microsoft 365 mailboxes via Microsoft Graph API (triggered via API or frontend).
*   **Core Processing:** Email parsing, text summarization, and keyword-based content classification.
*   **MongoDB Storage:** Uses MongoDB for storing user credentials and processed activity records, accessed via a repository pattern.
*   **JWT Authentication:** Secures API endpoints using JSON Web Tokens (Bearer tokens).
*   **Containerized Environment:**
    *   `Dockerfile` for local development with Uvicorn auto-reload.
    *   `Dockerfile.prod` optimized for production builds (non-root user, no auto-reload).
    *   `docker-compose.yml` for easy local development setup of the application and MongoDB.
*   **CI/CD Ready:** Includes `cloudbuild.yaml` for automated builds and deployments to Google Cloud Platform.
*   **Deployment Examples:** Provides `DEPLOYMENT_GCP.md` and `gcp_configs/cloudrun/service.yaml` for GCP deployment guidance.
*   **Modular and Testable:** Core functionalities are well-defined and supported by unit tests.

## Architecture

The system is divided into several Bounded Contexts: `IngestionContext`, `AnalysisContext`, `ActivityLogContext`, `AuthContext`, and a `SharedKernel` for eventing. The API and Frontend layers interact with these contexts, primarily via Application Services. For a detailed explanation of contexts and event flow, please see the "Architecture" section in [DEPLOYMENT_GCP.md](DEPLOYMENT_GCP.md).

## Project Structure

```
.
├── data/                     # Sample data (e.g., sample_email.eml)
├── gcp_configs/              # Google Cloud Platform specific configurations
│   └── cloudrun/
│       └── service.yaml      # Example Cloud Run service definition
├── scripts/                  # Deployment and utility scripts
│   ├── setup_gcp_secrets.sh  # Example script to create secrets in GCP Secret Manager
│   └── trigger_cloud_build.sh # Example script to manually trigger a Cloud Build
├── src/                      # Source code
│   ├── activity_log_context/ # Manages storing activity records
│   ├── analysis_context/     # Content analysis
│   ├── api/                    # FastAPI application (src.api.main:app)
│   ├── auth_context/         # User authentication and authorization
│   ├── frontend/             # Jinja2 templates, static files, frontend routers
│   ├── ingestion_context/    # Data intake and parsing
│   ├── shared_kernel/        # Shared components (e.g., event dispatcher)
│   ├── __init__.py           # Makes 'src' a package
│   └── main.py               # CLI entry point (for local .eml file processing)
├── tests/                    # Unit tests
├── .dockerignore             # Files to ignore in Docker image
├── Dockerfile                # Development Dockerfile (used by docker-compose.yml)
├── Dockerfile.prod           # Production-ready Dockerfile
├── cloudbuild.yaml           # Google Cloud Build configuration
├── docker-compose.yml        # For local development with Docker
├── DEPLOYMENT_GCP.md         # Detailed deployment plan for GCP
├── README.md                 # This file
└── requirements.txt          # Python dependencies
```

## Setup and Local Development

### Prerequisites
*   Python 3.11+
*   Docker and Docker Compose (for containerized development - recommended)
*   MongoDB (if running natively instead of using the Dockerized MongoDB service)

### 1. Clone the Repository
```bash
git clone <repository_url>
cd <repository_name>
```

### 2. Environment Variables for Configuration
For local development, create a `.env` file in the project root (this file is in `.gitignore` and should not be committed). `docker-compose.yml` will automatically load it. For non-Docker local development, ensure these variables are set in your shell environment.

**Example `.env` file content:**
```env
# MongoDB (used by docker-compose.yml to configure the 'backend' service)
MONGO_URI="mongodb://mongo:27017/activity_db_dev_docker"
AUTH_MONGO_DB_NAME="auth_db_dev_docker"

# If running MongoDB locally (not via docker-compose's 'mongo' service):
# MONGO_URI="mongodb://localhost:27017/activity_db_dev_local"
# AUTH_MONGO_DB_NAME="auth_db_dev_local"

# JWT Authentication
JWT_SECRET_KEY="a_very_strong_and_super_secret_random_key_for_development_lmnopqrstuvwxyz1234567890" # CHANGE THIS!
ACCESS_TOKEN_EXPIRE_MINUTES="60"

# Microsoft Graph API (Optional - only if testing cloud email ingestion)
# Obtain these from your Azure App Registration. Leave blank if not using.
AZURE_CLIENT_ID=""
AZURE_CLIENT_SECRET=""
AZURE_TENANT_ID=""
GRAPH_TARGET_USER_ID="" # e.g., user@yourdomain.com or Azure AD User Object ID
GRAPH_MAIL_FOLDER="Inbox"
```
**Important Notes on Environment Variables:**
*   `JWT_SECRET_KEY`: **Must be changed to a strong, unique, random string, especially for any non-local testing or production.** The default in `security.py` (if this `.env` var is missing) is for emergency dev fallback only.
*   Azure credentials are required *only* if you intend to use the Microsoft Graph email ingestion feature.

### 3. Running with Docker (Recommended)
This is the easiest way to get started with all services running.
1.  Ensure Docker and Docker Compose are installed.
2.  Ensure your `.env` file is created as described above.
3.  Build and run the services:
    ```bash
    docker-compose up --build
    ```
    *   This uses `Dockerfile` for development (with Uvicorn's auto-reload feature).
    *   Starts the FastAPI application (`backend` service) and MongoDB (`mongo` service).
    *   Backend available at: `http://localhost:8000` (API root)
    *   Frontend UI available at: `http://localhost:8000/app/`
    *   API Docs (Swagger): `http://localhost:8000/docs`
4.  To stop: `Ctrl+C`, then `docker-compose down` (add `-v` to remove MongoDB data volume).

### 4. Local Development without Docker
1.  Install MongoDB locally and ensure it's running.
2.  Create a Python virtual environment and activate it:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  Install dependencies: `pip install -r requirements.txt`
4.  Set environment variables (as per the `.env` example, but for your shell).
5.  Run the API server:
    ```bash
    uvicorn src.api.main:app --reload
    ```
    Access points are the same as with Docker.
6.  (Optional) NLTK Data for advanced summarization (if feature is enabled):
    ```python
    import nltk
    nltk.download('punkt')
    ```

## Usage

*   **Web Interface:** Access `http://localhost:8000/app/` (when running via Docker or Uvicorn locally). Register, login, upload EMLs, trigger cloud sync, and view logs.
*   **API:** Interact with API endpoints (e.g., using tools like Postman or curl) as documented at `http://localhost:8000/docs`.
*   **CLI for local EML processing:**
    ```bash
    python src.main:main --email-file data/sample_email.eml
    # Note: Ensure environment variables (especially for MongoDB) are set in your shell
    # if you want the CLI to log to the same DB used by the Dockerized/Uvicorn app.
    # The CLI's primary purpose is direct ingestion, which then triggers events.
    ```

## Running Tests
Ensure development dependencies are installed.
```bash
python -m unittest discover tests
```
Tests mock external dependencies like MongoDB.

## Deployment

This project is designed to be deployed as a containerized application.
*   **Production Docker Image:** Build using `Dockerfile.prod`. This image is optimized for production (non-root user, no auto-reload).
*   **Cloud Deployment (GCP Example):**
    *   A detailed deployment plan for Google Cloud Platform (GCP) is provided in [DEPLOYMENT_GCP.md](DEPLOYMENT_GCP.md).
    *   This guide covers using services like Cloud Run, Artifact Registry, MongoDB Atlas, and Secret Manager.
    *   It also includes information on setting up a CI/CD pipeline using Google Cloud Build with the provided `cloudbuild.yaml` and using helper scripts from the `scripts/` directory.
    *   Declarative service configuration for Cloud Run is exemplified in `gcp_configs/cloudrun/service.yaml`.

## Future Enhancements
*   Full implementation of remaining User Authentication API Endpoints (e.g., `/users/me`, password reset).
*   Asynchronous event handling for improved performance.
*   Integration with a robust message broker (e.g., RabbitMQ, Kafka) for eventing if scaling to microservices.
*   Advanced filtering and querying for the Activity Logs API.
*   IMAP integration for fetching emails from diverse email servers.
*   More sophisticated NLP models for summarization and classification.
*   Comprehensive configuration management solution.
*   Dedicated repositories for `RawEmail` and `AnalyzedContent` if querying these intermediate objects becomes a requirement.
*   Expanded Web Interface with more features.
*   Support for batch processing of emails/data.
*   Handling of email attachments.
*   Distributed tracing and enhanced monitoring for a microservices architecture.
```
