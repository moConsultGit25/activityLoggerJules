# Automated Activity Logger

## Description

This project automatically processes and logs activity from various engagement data sources. Initially focused on email (.eml) files (processed via local upload or from Microsoft 365 and Google Gmail mailboxes using their respective APIs), it can be extended for other data sources.

The system is architected using Domain-Driven Design (DDD) principles. An event-driven approach (currently in-process) decouples different stages of processing. For potentially long-running tasks like email ingestion, asynchronous processing is handled by Celery with Redis as the message broker and result backend, significantly improving API responsiveness.

It extracts key information, summarizes content, classifies it based on keywords, and logs these activities into a MongoDB database. A FastAPI web application provides an API for interactions and a basic frontend interface for user registration, login, data submission, and viewing results.

## Features

*   **Domain-Driven Design:** Organized into Bounded Contexts for clear separation of concerns.
*   **Event-Driven Architecture:** In-process event dispatcher for decoupled communication post-task processing.
*   **Asynchronous Task Processing:** Celery and Redis for background email ingestion.
*   **FastAPI Web App:**
    *   **Backend API:** User registration, JWT-based login, OAuth 2.0 flows for user mailbox connection (Microsoft 365 & Google Gmail), asynchronous email ingestion, activity log retrieval, and Celery task status checking.
    *   **Frontend UI:** Jinja2-templated interface for user interactions, including M365 & Google account connections.
*   **Email Ingestion Sources:**
    *   Local `.eml` file uploads (asynchronous).
    *   User-specific Microsoft 365 mailboxes via Microsoft Graph API (OAuth 2.0 user-delegated, async).
    *   (Planned) User-specific Google Gmail mailboxes via Gmail API (OAuth 2.0 user-delegated, async).
*   **Core Processing:** Email parsing, text summarization, keyword-based content classification.
*   **Secure Storage:**
    *   MongoDB for user credentials (hashed passwords) and activity records.
    *   Encrypted storage for user-specific M365 and Google refresh tokens.
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
├── GOOGLE_GMAIL_API_SETUP.md # Guide for Google Cloud Project & Gmail API OAuth Setup
├── data/
├── gcp_configs/
│   └── cloudrun/service.yaml
├── scripts/
│   ├── setup_gcp_secrets.sh
│   └── trigger_cloud_build.sh
├── src/
# ... (rest of the structure remains the same) ...
├── README.md
└── requirements.txt
```
*(Simplified structure view for brevity)*

## Setup and Local Development

### Prerequisites
*   Python 3.11+
*   Docker and Docker Compose
*   (Optional) Native MongoDB, Redis.
*   (Optional) Azure AD App Registration for M365 OAuth (see [AZURE_AD_OAUTH_SETUP.md](AZURE_AD_OAUTH_SETUP.md)).
*   (Optional) Google Cloud Project and OAuth Credentials for Gmail API (see [GOOGLE_GMAIL_API_SETUP.md](GOOGLE_GMAIL_API_SETUP.md)).

### 1. Clone the Repository
```bash
git clone <repository_url>
cd <repository_name>
```

### 2. Environment Variables
Create a `.env` file in the project root.

**Key Environment Variables (see linked setup documents for full details):**
```env
# Core
MONGO_URI="mongodb://mongo:27017/activity_db_compose"
AUTH_MONGO_DB_NAME="auth_db_compose"
REDIS_URL="redis://redis:6379/0"
JWT_SECRET_KEY="!! YOUR_STRONG_JWT_SECRET_KEY !!"
ACCESS_TOKEN_EXPIRE_MINUTES="60"

# --- Microsoft 365 User-Delegated OAuth & Token Encryption ---
AZURE_CLIENT_ID=""
AZURE_TENANT_ID=""
AZURE_CLIENT_SECRET=""
M365_REDIRECT_URI="http://localhost:8000/api/v1/auth/m365/callback"
M365_SCOPES="Mail.Read User.Read offline_access"
M365_TOKEN_ENCRYPTION_KEY="!! YOUR_FERNET_ENCRYPTION_KEY_FOR_M365_TOKENS !!"
STATE_SERIALIZER_SECRET_KEY="!! YOUR_STRONG_SECRET_KEY_FOR_OAUTH_STATE !!" # Can reuse/derive from JWT_SECRET_KEY for dev

# --- Google Gmail User-Delegated OAuth & Token Encryption ---
GOOGLE_CLIENT_ID=""
GOOGLE_CLIENT_SECRET=""
GOOGLE_REDIRECT_URI="http://localhost:8000/api/v1/auth/google/callback" # For local dev
GOOGLE_SCOPES="https://www.googleapis.com/auth/gmail.readonly openid email profile" # Space-separated
GOOGLE_TOKEN_ENCRYPTION_KEY="!! YOUR_FERNET_ENCRYPTION_KEY_FOR_GOOGLE_TOKENS !!" # Generate similarly to M365 key

# (Optional) App-Only Graph API for a single M365 mailbox (if still used)
# GRAPH_TARGET_USER_ID=""
# GRAPH_MAIL_FOLDER="Inbox"
```
**Important Notes on Environment Variables:**
*   Refer to [AZURE_AD_OAUTH_SETUP.md](AZURE_AD_OAUTH_SETUP.md) for Azure AD.
*   Refer to [GOOGLE_GMAIL_API_SETUP.md](GOOGLE_GMAIL_API_SETUP.md) for Google Cloud Project setup.
*   `JWT_SECRET_KEY`, `M365_TOKEN_ENCRYPTION_KEY`, `GOOGLE_TOKEN_ENCRYPTION_KEY`, `STATE_SERIALIZER_SECRET_KEY` are critical for security. Generate strong random keys.
*   For Fernet encryption keys (e.g., `M365_TOKEN_ENCRYPTION_KEY`, `GOOGLE_TOKEN_ENCRYPTION_KEY`):
    ```python
    from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())
    ```

### 3. Running with Docker (Recommended)
(Instructions remain largely the same)

### 4. Local Development without Docker
(Instructions remain largely the same)

## Usage
(As previously described, noting new M365 and planned Google OAuth flows in API and frontend)

### Microsoft 365 / Google Connection Issues
(Section updated to be more generic if applicable, or keep M365 specific and add a Google one later)
If you find that your connected cloud email account (Microsoft 365 or Google) is no longer syncing, or if the dashboard unexpectedly shows "Status: Not Connected" after you previously connected it, your authorization tokens stored by this application may have become invalid. This can happen for various reasons (token expiry/revocation, key changes, etc.).

Our application automatically detects these invalid token scenarios. For your security, if an invalid refresh token is detected, the application will remove the old token information.

**To resolve this, you will need to re-authorize the application:**
1.  Go to the **Dashboard**.
2.  In the relevant connection section (Microsoft 365 or Google), click "Disconnect" if available, then "Connect".
3.  Follow the prompts to sign in to your Microsoft/Google account and grant permissions.

## Deployment
See [DEPLOYMENT_GCP.md](DEPLOYMENT_GCP.md). Ensure all necessary environment variables, including those for M365 and Google OAuth, are configured as secrets in your cloud environment.

## Future Enhancements
*   Full implementation of Google Gmail OAuth flow (backend and frontend).
*   ... (other enhancements)
```
