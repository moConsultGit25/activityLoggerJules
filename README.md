# Automated Activity Logger

## Description

This project automatically processes and logs activity from various engagement data sources. Initially focused on email (.eml) files (processed via local upload or from Microsoft 365 mailboxes using Microsoft Graph API), it can be extended for other data sources.

The system is architected using Domain-Driven Design (DDD) principles. An event-driven approach (currently in-process) decouples different stages of processing. For potentially long-running tasks like email ingestion, asynchronous processing is handled by Celery with Redis as the message broker and result backend, significantly improving API responsiveness.

It extracts key information, summarizes content, classifies it based on keywords, and logs these activities into a MongoDB database. A FastAPI web application provides an API for interactions and a basic frontend interface for user registration, login, data submission, and viewing results.

## Features

*   **Domain-Driven Design:** Organized into Bounded Contexts for clear separation of concerns.
*   **Event-Driven Architecture:** In-process event dispatcher for decoupled communication post-task processing.
*   **Asynchronous Task Processing:** Celery and Redis for background email ingestion, improving API responsiveness.
*   **FastAPI Web App:**
    *   **Backend API:** User registration, JWT-based login, M365 OAuth 2.0 flow for user mailbox connection, asynchronous email ingestion (file upload & M365 cloud sync), activity log retrieval (paginated), and Celery task status checking.
    *   **Frontend UI:** Jinja2-templated interface for registration, login/logout, dashboard, EML file upload, M365 account connection/disconnection, M365 email sync trigger, and activity log display.
*   **Email Ingestion Sources:**
    *   Local `.eml` file uploads (processed asynchronously).
    *   User-specific Microsoft 365 mailboxes via Microsoft Graph API (using OAuth 2.0 user-delegated permissions, processed asynchronously).
*   **Core Processing:** Email parsing, text summarization, keyword-based content classification.
*   **Secure Storage:**
    *   MongoDB for user credentials (hashed passwords) and activity records.
    *   Encrypted storage for user-specific M365 refresh tokens.
*   **Redis:** Celery message broker and result backend.
*   **JWT Authentication:** Secures API endpoints.
*   **Containerized Environment:** `Dockerfile` (dev), `Dockerfile.prod` (production), `docker-compose.yml` (local full stack).
*   **CI/CD & Deployment:** `cloudbuild.yaml`, `DEPLOYMENT_GCP.md`, `gcp_configs/cloudrun/service.yaml`.
*   **Modular and Testable:** Unit tests and clear separation for testability.

## Architecture
(Briefly - main contexts: Ingestion, Analysis, ActivityLog, Auth, TaskQueue, SharedKernel. See DEPLOYMENT_GCP.md for details.)

## Project Structure
```
.
├── AZURE_AD_OAUTH_SETUP.md   # Guide for Azure AD App Registration for M365 OAuth
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
│   │   │   ├── routers/      # API routers (auth, ingestion, logs, m365_auth, tasks)
│   │   │   └── schemas/      # Pydantic schemas
│   │   ├── dependencies.py
│   │   └── main.py
│   ├── auth_context/         # User authentication, M365 OAuth logic
│   │   ├── application/      # AuthService, security utils, encryption utils
│   │   ├── domain/           # User, UserM365Token models
│   │   └── infrastructure/   # Repositories, M365OAuthClient
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
├── tests/                    # Unit tests (structure mirrors src/)
│   ├── auth_context/
│   │   ├── application/
│   │   ├── infrastructure/
│   # ... other test context directories
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
*   Docker and Docker Compose
*   (Optional) Native MongoDB, Redis.
*   (Optional) Azure AD App Registration for M365 OAuth (see [AZURE_AD_OAUTH_SETUP.md](AZURE_AD_OAUTH_SETUP.md)).

### 1. Clone the Repository
```bash
git clone <repository_url>
cd <repository_name>
```

### 2. Environment Variables
Create a `.env` file in the project root (from `.env.example` if provided, or manually). `docker-compose.yml` loads this.

**Key Environment Variables (see `.env.example` or `AZURE_AD_OAUTH_SETUP.md` for full list):**
```env
# Core
MONGO_URI="mongodb://mongo:27017/activity_db_compose"
AUTH_MONGO_DB_NAME="auth_db_compose"
REDIS_URL="redis://redis:6379/0"
JWT_SECRET_KEY="!! YOUR_STRONG_JWT_SECRET_KEY !!"
ACCESS_TOKEN_EXPIRE_MINUTES="60"

# M365 User-Delegated OAuth & Token Encryption
AZURE_CLIENT_ID=""      # From your Azure AD App Registration
AZURE_TENANT_ID=""      # From your Azure AD App Registration
AZURE_CLIENT_SECRET=""  # Client Secret Value from your Azure AD App Registration
M365_REDIRECT_URI="http://localhost:8000/api/v1/auth/m365/callback" # For local dev
M365_SCOPES="Mail.Read User.Read offline_access"
M365_TOKEN_ENCRYPTION_KEY="!! YOUR_FERNET_ENCRYPTION_KEY_FOR_M365_TOKENS !!" # See generation below
STATE_SERIALIZER_SECRET_KEY="!! YOUR_STRONG_SECRET_KEY_FOR_OAUTH_STATE !!" # Can reuse/derive from JWT_SECRET_KEY for dev

# (Optional) App-Only Graph API (if a separate single-mailbox direct sync feature is maintained)
# GRAPH_TARGET_USER_ID=""
# GRAPH_MAIL_FOLDER="Inbox"
```
**Important Notes on Environment Variables:**
*   Refer to [AZURE_AD_OAUTH_SETUP.md](AZURE_AD_OAUTH_SETUP.md) for Azure AD App Registration.
*   `JWT_SECRET_KEY`, `M365_TOKEN_ENCRYPTION_KEY`, `STATE_SERIALIZER_SECRET_KEY` are critical for security. Generate strong random keys.
*   For `M365_TOKEN_ENCRYPTION_KEY` (Fernet key):
    ```python
    from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())
    ```

### 3. Running with Docker (Recommended)
(Instructions remain largely the same)

### 4. Local Development without Docker
(Instructions remain largely the same)

## Usage

*   **Web Interface:** Access `http://localhost:8000/app/`.
    *   Register and login.
    *   Connect your Microsoft 365 account via the dashboard to authorize email reading.
    *   Upload EML files or trigger cloud mailbox sync (these actions are now asynchronous).
    *   View processed activity logs.
*   **API Endpoints (see `http://localhost:8000/docs` for full details):**
    *   **Authentication:**
        *   `POST /api/v1/auth/register`: Create a new user.
        *   `POST /api/v1/auth/login`: Login to get a JWT access token.
    *   **M365 OAuth (User-Delegated):**
        *   `GET /api/v1/auth/m365/authorize`: Initiates the M365 OAuth flow (redirects to Microsoft). Called by frontend.
        *   `GET /api/v1/auth/m365/callback`: Handles the callback from Microsoft after user consent. Stores tokens. Called by Microsoft.
        *   `POST /api/v1/auth/m365/disconnect`: Disconnects the user's M365 account by deleting stored tokens. Requires JWT auth.
        *   `GET /api/v1/auth/m365/status`: Checks if the current user has a connected M365 account. Requires JWT auth.
    *   **Ingestion (Asynchronous - return Task ID):**
        *   `POST /api/v1/ingestion/process-eml/`: Upload an `.eml` file. Requires JWT auth.
        *   `POST /api/v1/ingestion/trigger-cloud-mailbox-sync/`: Trigger sync for the authenticated user's connected M365 mailbox. Requires JWT auth.
    *   **Task Status:**
        *   `GET /api/v1/tasks/{task_id}/status`: Check status and result of a Celery task. Requires JWT auth.
    *   **Activity Logs:**
        *   `GET /api/v1/logs/`: Retrieve paginated activity logs. Requires JWT auth.
*   **CLI for local EML processing:** `python src.main:main --email-file data/sample_email.eml`.

## Running Tests
(Remains the same)

## Deployment
(Remains largely the same, ensure link to `DEPLOYMENT_GCP.md` is prominent. Emphasize that all new ENV VARS like `M365_TOKEN_ENCRYPTION_KEY` and `STATE_SERIALIZER_SECRET_KEY` must be configured as secrets in the cloud environment.)

## Future Enhancements
(Adjust as needed, e.g., "Full M365 OAuth integration" is now mostly complete.)
*   Frontend UI for displaying Celery task statuses and results more actively.
*   ... (other enhancements)
```
