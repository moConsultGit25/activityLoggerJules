# Deployment Plan: Automated Activity Logger on Google Cloud Platform (GCP)

## 1. Introduction

This document outlines a plan for deploying the containerized "Automated Activity Logger" application to Google Cloud Platform (GCP). It assumes the application has been containerized (using `Dockerfile.prod`), uses Celery for asynchronous tasks with Redis as a broker, and has configurations like `cloudbuild.yaml` and `gcp_configs/cloudrun/service.yaml` as starting points.

The primary goal is to deploy a scalable, secure, and maintainable version of the application, including its web server, API, and background Celery workers.

## 2. Prerequisites

*   **Google Cloud SDK (`gcloud` CLI):** Installed and authenticated.
*   **GCP Project:** Created with billing enabled. Note your `PROJECT_ID`.
*   **Docker:** Installed locally (for potential local image builds/tests).
*   **Enabled APIs:**
    *   Artifact Registry API
    *   Cloud Run API
    *   Secret Manager API
    *   Cloud Build API
    *   IAM API
    *   Memorystore for Redis API (if using managed Redis)
*   **Azure AD App Registration:** If using Microsoft 365 OAuth 2.0 for user-delegated email access, an Azure AD App Registration must be configured as per [AZURE_AD_OAUTH_SETUP.md](AZURE_AD_OAUTH_SETUP.md).

## 3. Core GCP Services Overview
(As previously defined, including Memorystore for Redis)

## 4. Deployment Workflow

### Step 4.1: Initial Setup & Configuration

1.  **MongoDB Setup:** (As previously defined)
2.  **Redis Setup (Memorystore for Redis):** (As previously defined)

3.  **Secret Configuration in Secret Manager:**
    *   Create secrets in Secret Manager for ALL sensitive environment variables. These secret names should align with those used in `cloudbuild.yaml` (e.g., `_MONGO_URI_SECRET_NAME`) and Cloud Run service definitions (e.g., `MONGO_URI_ACTIVITY_LOGGER`).
    *   **Key Secrets to Create (ensure names are consistent with your `cloudbuild.yaml` and `service.yaml`):**
        *   `MONGO_URI_ACTIVITY_LOGGER`
        *   `AUTH_MONGO_DB_NAME_ACTIVITY_LOGGER`
        *   `JWT_SECRET_KEY_ACTIVITY_LOGGER`
        *   `REDIS_URL_ACTIVITY_LOGGER`
        *   `ACCESS_TOKEN_EXPIRE_MINUTES_ACTIVITY_LOGGER`
        *   **Microsoft Graph API & M365 OAuth:**
            *   `AZURE_CLIENT_ID_ACTIVITY_LOGGER`
            *   `AZURE_CLIENT_SECRET_ACTIVITY_LOGGER`
            *   `AZURE_TENANT_ID_ACTIVITY_LOGGER`
            *   `GRAPH_TARGET_USER_ID_ACTIVITY_LOGGER` (If app-only mode for a specific mailbox is still used)
            *   `GRAPH_MAIL_FOLDER_ACTIVITY_LOGGER` (Can be a direct value like "Inbox" or a secret)
            *   `M365_REDIRECT_URI_ACTIVITY_LOGGER` (Production redirect URI for M365 OAuth)
            *   `M365_SCOPES_ACTIVITY_LOGGER` (e.g., "Mail.Read User.Read offline_access")
            *   `M365_TOKEN_ENCRYPTION_KEY_ACTIVITY_LOGGER` (Fernet key for encrypting stored M365 refresh tokens)
            *   `STATE_SERIALIZER_SECRET_KEY_ACTIVITY_LOGGER` (Secret for signing OAuth state cookie, can reuse/derive from JWT secret for simplicity if secure enough)
    *   Use `scripts/setup_gcp_secrets.sh` as a template. **Crucially, update this script to include all necessary secrets, especially the new ones like `REDIS_URL...`, `M365_TOKEN_ENCRYPTION_KEY...`, and `STATE_SERIALIZER_SECRET_KEY...`**
    *   Refer to [AZURE_AD_OAUTH_SETUP.md](AZURE_AD_OAUTH_SETUP.md) for Azure AD app registration.

4.  **IAM Permissions (Summary):** (As previously defined, ensure Cloud Run SA can access all new secrets)

### Step 4.2: CI/CD Setup with Cloud Build
(As previously defined)
*   **`cloudbuild.yaml` Update for New Secrets:**
    *   Ensure the `args` section for `gcloud run deploy` (for both web app and worker services) includes `--update-secrets` flags for all new secrets:
    ```yaml
              # ... existing secrets ...
              - '--update-secrets=REDIS_URL=projects/${PROJECT_ID}/secrets/${_REDIS_URL_SECRET_NAME}:latest'
              - '--update-secrets=M365_REDIRECT_URI=projects/${PROJECT_ID}/secrets/${_M365_REDIRECT_URI_SECRET_NAME}:latest'
              - '--update-secrets=M365_SCOPES=projects/${PROJECT_ID}/secrets/${_M365_SCOPES_SECRET_NAME}:latest'
              - '--update-secrets=M365_TOKEN_ENCRYPTION_KEY=projects/${PROJECT_ID}/secrets/${_M365_TOKEN_ENCRYPTION_KEY_SECRET_NAME}:latest'
              - '--update-secrets=STATE_SERIALIZER_SECRET_KEY=projects/${PROJECT_ID}/secrets/${_STATE_SERIALIZER_SECRET_KEY_SECRET_NAME}:latest'
    ```
    *   Add corresponding default substitutions in the `substitutions` block of `cloudbuild.yaml`:
    ```yaml
        substitutions:
          # ... existing substitutions ...
          _REDIS_URL_SECRET_NAME: 'REDIS_URL_ACTIVITY_LOGGER'
          _M365_REDIRECT_URI_SECRET_NAME: 'M365_REDIRECT_URI_ACTIVITY_LOGGER'
          _M365_SCOPES_SECRET_NAME: 'M365_SCOPES_ACTIVITY_LOGGER'
          _M365_TOKEN_ENCRYPTION_KEY_SECRET_NAME: 'M365_TOKEN_ENCRYPTION_KEY_ACTIVITY_LOGGER'
          _STATE_SERIALIZER_SECRET_KEY_SECRET_NAME: 'STATE_SERIALIZER_SECRET_KEY_ACTIVITY_LOGGER'
    ```

### Step 4.3: Initial Deployment / Manual Deployment
(As previously defined)
*   **Declarative Service Deployment (`service.yaml` and `service-worker.yaml`):**
    *   Update these YAML files to include all new environment variables sourced from Secret Manager (e.g., `REDIS_URL`, `M365_REDIRECT_URI`, `M365_SCOPES`, `M365_TOKEN_ENCRYPTION_KEY`, `STATE_SERIALIZER_SECRET_KEY`). Example for `service.yaml`:
    ```yaml
        # ... inside env: section ...
                    - name: REDIS_URL
                      valueFrom: { secretKeyRef: { name: 'REDIS_URL_ACTIVITY_LOGGER', key: 'latest' } }
                    - name: M365_REDIRECT_URI
                      valueFrom: { secretKeyRef: { name: 'M365_REDIRECT_URI_ACTIVITY_LOGGER', key: 'latest' } }
                    - name: M365_SCOPES
                      valueFrom: { secretKeyRef: { name: 'M365_SCOPES_ACTIVITY_LOGGER', key: 'latest' } }
                    - name: M365_TOKEN_ENCRYPTION_KEY
                      valueFrom: { secretKeyRef: { name: 'M365_TOKEN_ENCRYPTION_KEY_ACTIVITY_LOGGER', key: 'latest' } }
                    - name: STATE_SERIALIZER_SECRET_KEY
                      valueFrom: { secretKeyRef: { name: 'STATE_SERIALIZER_SECRET_KEY_ACTIVITY_LOGGER', key: 'latest' } }
    ```

### Step 4.4: Networking, Logging, and Monitoring
(As previously defined)

## 5. Example Deployment Scripts
*   **`scripts/setup_gcp_secrets.sh`:** Crucially, update this script to include prompts or placeholders for creating all secrets, including `REDIS_URL...`, `M365_TOKEN_ENCRYPTION_KEY...`, and `STATE_SERIALIZER_SECRET_KEY...`.
*   **`scripts/trigger_cloud_build.sh`:** Ensure it can pass or has defaults for any new substitutions added to `cloudbuild.yaml`.

## 6. Security Considerations
(As previously defined)

## 7. Cost Considerations
(As previously defined)

This updated plan ensures all necessary configurations for M365 OAuth and token encryption are covered for GCP deployment.
```
