# Automated Activity Logger

## Description

This project automatically processes and logs activity from various engagement data sources. Initially focused on email (.eml) files (processed via local upload or from Microsoft 365 mailboxes using Microsoft Graph API), it can be extended for other data sources.

The system is architected using Domain-Driven Design (DDD) principles. An event-driven approach (currently in-process) decouples different stages of processing. For potentially long-running tasks like email ingestion, asynchronous processing is handled by Celery with Redis as the message broker and result backend, significantly improving API responsiveness.

It extracts key information, summarizes content, classifies it based on keywords, and logs these activities into a MongoDB database. A FastAPI web application provides an API for interactions and a basic frontend interface for user registration, login, data submission, and viewing results.

## Features

*   **Domain-Driven Design:** Organized into Bounded Contexts (`IngestionContext`, `AnalysisContext`, `ActivityLogContext`, `AuthContext`, `TaskQueue`) for clear separation of concerns.
*   **Event-Driven Architecture:** Uses an in-process event dispatcher (`shared_kernel.events`) for decoupled communication between contexts after initial data processing.
*   **Asynchronous Task Processing:** Utilizes Celery with Redis as a message broker and result backend for handling email ingestion tasks asynchronously. This makes API endpoints for data submission non-blocking.
*   **FastAPI Web App:**
    *   Backend API for user registration, login (JWT-based), asynchronous email ingestion (file upload & cloud sync), activity log retrieval (paginated), and Celery task status checking.
    *   Basic Jinja2-templated frontend for user interaction: registration, login/logout, dashboard with EML upload form, cloud sync trigger, and activity log display.
*   **Email Ingestion Sources:**
    *   Local `.eml` file uploads (processed asynchronously via Celery).
    *   Cloud email ingestion from Microsoft 365 mailboxes via Microsoft Graph API (processed asynchronously via Celery).
*   **Core Processing:** Email parsing, text summarization, and keyword-based content classification.
*   **MongoDB Storage:** For user credentials and processed activity records, accessed via a repository pattern.
*   **Redis:** As Celery message broker and result backend.
*   **JWT Authentication:** Secures API endpoints using JSON Web Tokens (Bearer tokens).
*   **Containerized Environment:**
    *   `Dockerfile` for local development (FastAPI with Uvicorn auto-reload).
    *   `Dockerfile.prod` optimized for production builds (non-root user, no auto-reload).
    *   `docker-compose.yml` for easy local development setup of the FastAPI app, MongoDB, Redis, and Celery worker(s).
*   **CI/CD & Deployment:**
    *   `cloudbuild.yaml` for automated builds and deployments to Google Cloud Platform.
    *   `DEPLOYMENT_GCP.md` providing a detailed deployment plan for GCP.
    *   `gcp_configs/cloudrun/service.yaml` as an example declarative configuration for Cloud Run.
*   **Modular and Testable:** Core functionalities are well-defined and supported by unit tests.

## Architecture

The system is designed with several Bounded Contexts:
*   **`IngestionContext`**: Handles initial data intake (parsing local EML files, fetching emails from Microsoft Graph). Its operations are now primarily executed as asynchronous Celery tasks.
*   **`AnalysisContext`**: Performs content analysis (summarization, classification). Triggered by events after ingestion.
*   **`ActivityLogContext`**: Manages storage and retrieval of processed activity records in MongoDB. Triggered by events after analysis.
*   **`AuthContext`**: Handles user authentication (registration, login, password management) and JWT generation/validation.
*   **`TaskQueueContext`**: Defines and configures the Celery application, using Redis as the broker and result backend. This context enables asynchronous execution of tasks, such as those in `IngestionContext`.
*   **`SharedKernel`**: Contains shared code, notably the in-process event dispatcher for communication *after* initial task processing (e.g., from ingestion service to analysis service if they were not part of the same Celery task chain).

**Workflow Example (EML Upload):**
1. User uploads EML file via API/Frontend.
2. API endpoint dispatches a Celery task (`ingestion.process_eml_file_task`) with EML content and returns a `task_id`.
3. Celery worker picks up the task from the Redis queue.
4. The task (running `IngestionService`) parses the EML. On success, it publishes an `EmailIngestedEvent` (in-process).
5. `AnalysisContext` handles this event, analyzes content, and publishes `ContentAnalyzedEvent`.
6. `ActivityLogContext` handles this, creating and storing an `ActivityRecord` in MongoDB.
7. User can poll the `/api/v1/tasks/{task_id}/status` endpoint to check the outcome.

## Project Structure
```
.
├── data/                     # Sample data
├── gcp_configs/              # GCP specific configurations
│   └── cloudrun/service.yaml # Example Cloud Run service definition
├── scripts/                  # Deployment and utility scripts
│   ├── setup_gcp_secrets.sh
│   └── trigger_cloud_build.sh
├── src/                      # Source code
│   ├── activity_log_context/
│   ├── analysis_context/
│   ├── api/                    # FastAPI application (src.api.main:app)
│   │   ├── v1/
│   │   │   ├── routers/      # API routers (auth, ingestion, logs, tasks)
│   │   │   └── schemas/      # Pydantic schemas
│   │   ├── dependencies.py
│   │   └── main.py
│   ├── auth_context/
│   ├── frontend/             # Jinja2 templates, static files, frontend routers
│   ├── ingestion_context/
│   │   └── tasks.py          # Celery tasks for ingestion
│   ├── shared_kernel/
│   │   └── events.py
│   ├── task_queue/           # Celery application and configuration
│   │   ├── celery_app.py
│   │   └── celery_config.py
│   ├── __init__.py
│   └── main.py               # CLI entry point (manual EML processing)
├── tests/                    # Unit tests
├── .dockerignore
├── Dockerfile                # For development (used by docker-compose)
├── Dockerfile.prod           # For production builds
├── cloudbuild.yaml           # GCP Cloud Build configuration
├── docker-compose.yml        # Local development with Docker (app, mongo, redis, worker)
├── DEPLOYMENT_GCP.md         # Detailed GCP deployment plan
├── README.md                 # This file
└── requirements.txt          # Python dependencies
```

## Setup and Local Development

### Prerequisites
*   Python 3.11+
*   Docker and Docker Compose (highly recommended for the full local environment)
*   (Optional) Native installations of MongoDB and Redis if not using Docker.

### 1. Clone the Repository
```bash
git clone <repository_url>
cd <repository_name>
```

### 2. Environment Variables
Create a `.env` file in the project root (this is gitignored). `docker-compose.yml` will automatically load it. For local development without Docker, set these in your shell.

**Example `.env` file content:**
```env
# MongoDB (for Docker Compose 'mongo' service)
MONGO_URI="mongodb://mongo:27017/activity_db_compose"
AUTH_MONGO_DB_NAME="auth_db_compose"

# Redis (for Docker Compose 'redis' service, used by Celery)
REDIS_URL="redis://redis:6379/0"

# For local native MongoDB/Redis:
# MONGO_URI="mongodb://localhost:27017/activity_db_local"
# AUTH_MONGO_DB_NAME="auth_db_local"
# REDIS_URL="redis://localhost:6379/0"

# JWT Authentication
JWT_SECRET_KEY="!! REPLACE_WITH_A_VERY_STRONG_RANDOM_SECRET_KEY !!" # IMPORTANT: Change this!
ACCESS_TOKEN_EXPIRE_MINUTES="60"

# Microsoft Graph API (Optional - for cloud email ingestion feature)
AZURE_CLIENT_ID=""
AZURE_CLIENT_SECRET=""
AZURE_TENANT_ID=""
GRAPH_TARGET_USER_ID="" # e.g., user@yourdomain.com
GRAPH_MAIL_FOLDER="Inbox"
```

### 3. Running with Docker (Recommended)
1.  Ensure Docker and Docker Compose are installed and your `.env` file is configured.
2.  The `docker-compose.yml` defines four services: `backend` (FastAPI app), `mongo` (MongoDB), `redis` (Redis broker), and `worker` (Celery worker).
3.  Build and run all services:
    ```bash
    docker-compose up --build
    ```
    *   This uses `Dockerfile` for building the `backend` and `worker` services (optimized for development with features like Uvicorn's auto-reload for the FastAPI app).
    *   API available at: `http://localhost:8000`
    *   Frontend UI: `http://localhost:8000/app/`
    *   API Docs (Swagger): `http://localhost:8000/docs`
4.  **Viewing Logs:**
    *   Combined logs: `docker-compose logs -f`
    *   Specific service logs: `docker-compose logs -f backend`, `docker-compose logs -f worker`, etc.
    *   Celery worker logs are particularly important for observing task execution.
5.  **Task Code Changes (Celery Worker):** While the `backend` service (FastAPI app) uses Uvicorn's `--reload`, Celery workers do not automatically reload Python code for tasks. If you change task definitions in `src/`, you may need to restart the worker service: `docker-compose restart worker` or rebuild the image if dependencies change: `docker-compose up --build`.
6.  To stop: `Ctrl+C`, then `docker-compose down` (add `-v` to also remove MongoDB and Redis data volumes).

### 4. Local Development without Docker
1.  Install and run MongoDB and Redis natively.
2.  Set up Python virtualenv: `python -m venv venv && source venv/bin/activate`.
3.  Install dependencies: `pip install -r requirements.txt` (includes `celery`, `redis`, `fastapi`, `uvicorn`, etc.).
4.  Set environment variables in your shell (per `.env` example, pointing to local Redis/Mongo).
5.  Run API server: `uvicorn src.api.main:app --reload`.
6.  Run Celery worker (in a separate terminal):
    ```bash
    celery -A src.task_queue.celery_app worker -l info
    ```

## Usage

*   **Web Interface:** Access `http://localhost:8000/app/`. Register, login, upload EMLs (processed asynchronously), trigger cloud sync (asynchronous), and view logs.
*   **API Endpoints:**
    *   Authentication: `/api/v1/auth/register`, `/api/v1/auth/login`
    *   EML File Ingestion (async): `POST /api/v1/ingestion/process-eml/` (returns `task_id`)
    *   Cloud Mailbox Sync (async): `POST /api/v1/ingestion/trigger-cloud-mailbox-sync/` (returns `task_id`)
    *   Task Status: `GET /api/v1/tasks/{task_id}/status`
    *   Activity Logs: `GET /api/v1/logs/`
    *   Full documentation at `http://localhost:8000/docs`.
*   **CLI for local EML processing:** `python src.main:main --email-file data/sample_email.eml`. (Note: This direct CLI processing bypasses Celery for immediate execution and event dispatch).

## Running Tests
```bash
python -m unittest discover tests
```

## Deployment
This project is designed for containerized deployment.
*   **Production Docker Image:** Use `Dockerfile.prod` for building optimized images.
*   **Cloud Deployment (GCP Example):** Refer to [DEPLOYMENT_GCP.md](DEPLOYMENT_GCP.md) for a detailed plan using Google Cloud Run, Artifact Registry, MongoDB Atlas, managed Redis (e.g., Memorystore), Secret Manager, and CI/CD with Cloud Build (`cloudbuild.yaml`). The deployment guide also covers running Celery workers as a separate Cloud Run service.

## Future Enhancements
*   Frontend UI for displaying Celery task statuses and results.
*   More specific Celery queues for different types of tasks and worker prioritization.
*   Integration of Flower for Celery monitoring.
*   Full implementation of remaining User Authentication API Endpoints (e.g., `/users/me`, password reset).
*   Transition from in-process events to Celery tasks for inter-context communication where appropriate (e.g., after analysis, trigger logging via a Celery task).
*   ... (other enhancements from previous comprehensive list)

```
