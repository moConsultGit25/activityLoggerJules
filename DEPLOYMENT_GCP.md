# Deployment Plan: Automated Activity Logger on Google Cloud Platform (GCP)

## 1. Introduction
(As before)

## 2. Prerequisites
*   (As before)
*   **Azure AD App Registration:** If using Microsoft 365 OAuth, configure as per [AZURE_AD_OAUTH_SETUP.md](AZURE_AD_OAUTH_SETUP.md).
*   **Google Cloud Project & OAuth Client:** If using Google Gmail API OAuth, configure as per [GOOGLE_GMAIL_API_SETUP.md](GOOGLE_GMAIL_API_SETUP.md).

## 3. Core GCP Services Overview
(As before)

## 4. Deployment Workflow

### Step 4.1: Initial Setup & Configuration

1.  **MongoDB Setup:** (As before)
2.  **Redis Setup (Memorystore for Redis):** (As before)

3.  **Secret Configuration in Secret Manager:**
    *   Create secrets for ALL sensitive environment variables. Use consistent naming, e.g., by suffixing with `_ACTIVITY_LOGGER`.
    *   **Key Secrets to Create:**
        *   `MONGO_URI_ACTIVITY_LOGGER`
        *   `AUTH_MONGO_DB_NAME_ACTIVITY_LOGGER`
        *   `JWT_SECRET_KEY_ACTIVITY_LOGGER`
        *   `REDIS_URL_ACTIVITY_LOGGER`
        *   `ACCESS_TOKEN_EXPIRE_MINUTES_ACTIVITY_LOGGER`
        *   **Microsoft 365 OAuth & Graph API:** (Refer to `AZURE_AD_OAUTH_SETUP.md`)
            *   `AZURE_CLIENT_ID_ACTIVITY_LOGGER`
            *   `AZURE_CLIENT_SECRET_ACTIVITY_LOGGER`
            *   `AZURE_TENANT_ID_ACTIVITY_LOGGER`
            *   `M365_REDIRECT_URI_ACTIVITY_LOGGER` (Production URI)
            *   `M365_SCOPES_ACTIVITY_LOGGER`
            *   `M365_TOKEN_ENCRYPTION_KEY_ACTIVITY_LOGGER`
            *   `STATE_SERIALIZER_SECRET_KEY_ACTIVITY_LOGGER` (Can be same as JWT key for simplicity, but separate is better)
            *   `GRAPH_TARGET_USER_ID_ACTIVITY_LOGGER` (If app-only mode is still used)
            *   `GRAPH_MAIL_FOLDER_ACTIVITY_LOGGER` (Or set directly if "Inbox" is always used)
        *   **Google Gmail API OAuth:** (Refer to `GOOGLE_GMAIL_API_SETUP.md`)
            *   `GOOGLE_CLIENT_ID_ACTIVITY_LOGGER`
            *   `GOOGLE_CLIENT_SECRET_ACTIVITY_LOGGER`
            *   `GOOGLE_REDIRECT_URI_ACTIVITY_LOGGER` (Production URI for Google OAuth callback)
            *   `GOOGLE_SCOPES_ACTIVITY_LOGGER`
            *   `GOOGLE_TOKEN_ENCRYPTION_KEY_ACTIVITY_LOGGER`
            *   (Note: Google OAuth also uses a state mechanism; if a separate state signing key is used for it, add here. For now, assume it might reuse `STATE_SERIALIZER_SECRET_KEY` or a similar concept handled by its OAuth client.)
    *   Use `scripts/setup_gcp_secrets.sh` as a template. **Update this script to include all new secrets listed above.**

4.  **IAM Permissions (Summary):** (As before, ensure access to all new secrets)

### Step 4.2: CI/CD Setup with Cloud Build
(As before)
*   **`cloudbuild.yaml` Update for All New Secrets:**
    *   Ensure the `args` section for `gcloud run deploy` (for both web app and worker services) includes `--update-secrets` flags for all new secrets, including Google OAuth ones.
    ```yaml
              # ... existing M365 secrets ...
              - '--update-secrets=M365_TOKEN_ENCRYPTION_KEY=projects/${PROJECT_ID}/secrets/${_M365_TOKEN_ENCRYPTION_KEY_SECRET_NAME}:latest'
              - '--update-secrets=STATE_SERIALIZER_SECRET_KEY=projects/${PROJECT_ID}/secrets/${_STATE_SERIALIZER_SECRET_KEY_SECRET_NAME}:latest'
              # Google OAuth Secrets
              - '--update-secrets=GOOGLE_CLIENT_ID=projects/${PROJECT_ID}/secrets/${_GOOGLE_CLIENT_ID_SECRET_NAME}:latest'
              - '--update-secrets=GOOGLE_CLIENT_SECRET=projects/${PROJECT_ID}/secrets/${_GOOGLE_CLIENT_SECRET_SECRET_NAME}:latest'
              - '--update-secrets=GOOGLE_REDIRECT_URI=projects/${PROJECT_ID}/secrets/${_GOOGLE_REDIRECT_URI_SECRET_NAME}:latest'
              - '--update-secrets=GOOGLE_SCOPES=projects/${PROJECT_ID}/secrets/${_GOOGLE_SCOPES_SECRET_NAME}:latest'
              - '--update-secrets=GOOGLE_TOKEN_ENCRYPTION_KEY=projects/${PROJECT_ID}/secrets/${_GOOGLE_TOKEN_ENCRYPTION_KEY_SECRET_NAME}:latest'
    ```
    *   Add corresponding default substitutions in the `substitutions` block of `cloudbuild.yaml`:
    ```yaml
        substitutions:
          # ... existing substitutions ...
          _M365_TOKEN_ENCRYPTION_KEY_SECRET_NAME: 'M365_TOKEN_ENCRYPTION_KEY_ACTIVITY_LOGGER'
          _STATE_SERIALIZER_SECRET_KEY_SECRET_NAME: 'STATE_SERIALIZER_SECRET_KEY_ACTIVITY_LOGGER'
          _GOOGLE_CLIENT_ID_SECRET_NAME: 'GOOGLE_CLIENT_ID_ACTIVITY_LOGGER'
          _GOOGLE_CLIENT_SECRET_SECRET_NAME: 'GOOGLE_CLIENT_SECRET_ACTIVITY_LOGGER'
          _GOOGLE_REDIRECT_URI_SECRET_NAME: 'GOOGLE_REDIRECT_URI_ACTIVITY_LOGGER'
          _GOOGLE_SCOPES_SECRET_NAME: 'GOOGLE_SCOPES_ACTIVITY_LOGGER'
          _GOOGLE_TOKEN_ENCRYPTION_KEY_SECRET_NAME: 'GOOGLE_TOKEN_ENCRYPTION_KEY_ACTIVITY_LOGGER'
    ```

### Step 4.3: Initial Deployment / Manual Deployment
(As before)
*   **Declarative Service Deployment (`service.yaml` and `service-worker.yaml`):**
    *   Update these YAML files to include all new environment variables sourced from Secret Manager (e.g., `GOOGLE_CLIENT_ID`, etc.). Example for `service.yaml`:
    ```yaml
        # ... inside env: section ...
                    - name: M365_TOKEN_ENCRYPTION_KEY
                      valueFrom: { secretKeyRef: { name: 'M365_TOKEN_ENCRYPTION_KEY_ACTIVITY_LOGGER', key: 'latest' } }
                    - name: STATE_SERIALIZER_SECRET_KEY
                      valueFrom: { secretKeyRef: { name: 'STATE_SERIALIZER_SECRET_KEY_ACTIVITY_LOGGER', key: 'latest' } }
                    - name: GOOGLE_CLIENT_ID
                      valueFrom: { secretKeyRef: { name: 'GOOGLE_CLIENT_ID_ACTIVITY_LOGGER', key: 'latest' } }
                    - name: GOOGLE_CLIENT_SECRET
                      valueFrom: { secretKeyRef: { name: 'GOOGLE_CLIENT_SECRET_ACTIVITY_LOGGER', key: 'latest' } }
                    - name: GOOGLE_REDIRECT_URI
                      valueFrom: { secretKeyRef: { name: 'GOOGLE_REDIRECT_URI_ACTIVITY_LOGGER', key: 'latest' } }
                    - name: GOOGLE_SCOPES
                      valueFrom: { secretKeyRef: { name: 'GOOGLE_SCOPES_ACTIVITY_LOGGER', key: 'latest' } }
                    - name: GOOGLE_TOKEN_ENCRYPTION_KEY
                      valueFrom: { secretKeyRef: { name: 'GOOGLE_TOKEN_ENCRYPTION_KEY_ACTIVITY_LOGGER', key: 'latest' } }
    ```

### Step 4.4: Networking, Logging, and Monitoring
(As before)

## 5. Example Deployment Scripts
*   **`scripts/setup_gcp_secrets.sh`:** Ensure this script is updated to include creation of all listed secrets, including the Google OAuth related ones.
*   **`scripts/trigger_cloud_build.sh`:** (As before)

## 6. Security Considerations
(As before)

## 7. Cost Considerations
(As before)

This updated plan ensures all necessary configurations for both M365 and Google OAuth are covered for GCP deployment.
```
