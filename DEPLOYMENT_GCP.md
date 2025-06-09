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

## 3. Core GCP Services Overview

*   **Artifact Registry:** Stores application Docker images.
*   **Cloud Run:** Serverless platform for the FastAPI web application (main service) and Celery workers (as separate Cloud Run services).
*   **MongoDB Solution:**
    *   **MongoDB Atlas on GCP (Recommended):** Managed service.
    *   **Self-managed on Compute Engine (Advanced).**
*   **Memorystore for Redis (Recommended):** Managed Redis service for Celery broker and result backend. Alternatively, other Redis hosting options can be used.
*   **Secret Manager:** Stores all sensitive configurations (DB URIs, API keys, JWT secrets, Azure credentials, Redis URL).
*   **Cloud Logging & Cloud Monitoring:** For logs and metrics from Cloud Run services (web app and workers).
*   **Cloud Build:** Automates Docker image builds and deployments via `cloudbuild.yaml`.
*   **IAM:** Manages permissions.

## 4. Deployment Workflow

### Step 4.1: Initial Setup & Configuration

1.  **MongoDB Setup:**
    *   Provision MongoDB (MongoDB Atlas recommended). Obtain the connection string.

2.  **Redis Setup (Memorystore for Redis):**
    *   Enable the Memorystore for Redis API.
    *   Create a Memorystore for Redis instance. Choose an appropriate tier and region.
    *   Configure a VPC Network and Serverless VPC Access connector if your Redis instance is not publicly accessible and Cloud Run services need to connect to it via private IP. This is the recommended secure approach.
    *   Note the Redis instance's IP address and port. Construct the `REDIS_URL` (e.g., `redis://<redis_ip>:<redis_port>/0`).

3.  **Secret Configuration in Secret Manager:**
    *   Create secrets for ALL sensitive environment variables. Names should align with those used in `cloudbuild.yaml` and Cloud Run service definitions.
    *   **Key Secrets:**
        *   `MONGO_URI_ACTIVITY_LOGGER`
        *   `AUTH_MONGO_DB_NAME_ACTIVITY_LOGGER`
        *   `JWT_SECRET_KEY_ACTIVITY_LOGGER`
        *   `REDIS_URL_ACTIVITY_LOGGER` (for Celery broker/backend)
        *   `ACCESS_TOKEN_EXPIRE_MINUTES_ACTIVITY_LOGGER`
        *   Azure credentials (if Graph ingestion is used): `AZURE_CLIENT_ID_ACTIVITY_LOGGER`, etc.
    *   Use `scripts/setup_gcp_secrets.sh` as a template, ensuring to add `REDIS_URL_ACTIVITY_LOGGER`.

4.  **IAM Permissions (Summary - Ensure comprehensive review):**
    *   **User performing initial setup:** Project Owner/Editor, Secret Manager Admin, Artifact Registry Admin, Cloud Run Admin, Cloud Build Editor, Compute Network User (for VPC Access).
    *   **Cloud Build Service Account (`[PROJECT_NUMBER]@cloudbuild.gserviceaccount.com`):**
        *   Artifact Registry Writer
        *   Cloud Run Admin
        *   Secret Manager Secret Accessor
        *   Service Account User (on Cloud Run runtime SA)
        *   Compute Network User (if Cloud Build needs to interact with VPC for any reason)
    *   **Cloud Run Runtime Service Account (for both Web App and Celery Worker services):**
        *   Secret Manager Secret Accessor (for its own runtime secrets)
        *   Cloud Logging Writer
        *   Cloud Monitoring Metric Writer
        *   Serverless VPC Access User (if using VPC connector for Redis/MongoDB)
        *   (Any other GCP services the application/tasks need to access)

### Step 4.2: CI/CD Setup with Cloud Build

1.  **Artifact Registry Repository:** Ensure it's created (e.g., `app-images` in `us-central1`).

2.  **`Dockerfile.prod`:** This is used for building both the web app and worker images (as they share the same codebase).

3.  **`cloudbuild.yaml` Update for Celery Worker:**
    *   The existing `cloudbuild.yaml` needs a second deployment step for the Celery worker service.
    *   **Key changes for the worker deployment step:**
        *   Different service name (e.g., `${_WORKER_SERVICE_NAME}` like `activity-logger-worker`).
        *   Uses the **same image** built earlier.
        *   **Command Override:** Crucially, override the container's default command to start the Celery worker:
            ```yaml
            # Inside the worker deployment step's 'args':
            # For Cloud Run v1 API (used by gcloud run deploy by default for some time)
            # - '--command=celery'
            # - '--args=-A,src.task_queue.celery_app,worker,-l,INFO,-Q,celery,high_priority' # Example queues
            # For Cloud Run v2 API (newer gcloud versions might default to this, or use --set-args)
            # - '--set-args=celery,-A,src.task_queue.celery_app,worker,-l,INFO,-Q,celery'
            # The exact syntax for command/args override depends on the gcloud version and API target.
            # The example in cloudbuild.yaml uses:
            # - '--command=celery'
            # - '--args=-A,src.task_queue.celery_app,worker,-l,INFO'
            ```
            Ensure this matches the command syntax for your `gcloud` version.
        *   **Networking:** Typically, worker services do not need to be publicly accessible (`--no-allow-unauthenticated`).
        *   **Scaling:** Worker scaling might differ from the web app (e.g., `min-instances=1` if tasks need constant processing, or scale based on CPU/custom metrics related to queue length if possible).
        *   Environment variables (from Secret Manager) will be largely the same as the web app, especially `REDIS_URL`, `MONGO_URI`.
    *   Add new substitution variables to `cloudbuild.yaml` like `_WORKER_SERVICE_NAME`, `_REDIS_URL_SECRET_NAME`.

4.  **Configure Cloud Build Trigger:** As previously described, connect to Git, use `cloudbuild.yaml`.

### Step 4.3: Initial Deployment / Manual Deployment

1.  **Manual Image Build & Push:** Use `Dockerfile.prod`.
2.  **Declarative Service Deployment (using `service.yaml` files):**
    *   **Web App Service:** Customize and use `gcp_configs/cloudrun/service.yaml` for the main FastAPI web application. Ensure all placeholders (project ID, image URI, secret names, runtime SA) are correct.
        ```bash
        gcloud run services replace gcp_configs/cloudrun/service.yaml --region YOUR_WEB_APP_REGION
        ```
    *   **Celery Worker Service (`service-worker.yaml` - New File):**
        Create a new file, e.g., `gcp_configs/cloudrun/service-worker.yaml`, by adapting `service.yaml`.
        **Key differences for `service-worker.yaml`:**
        *   `metadata.name`: Different service name (e.g., `activity-logger-worker`).
        *   `spec.template.spec.containers[0].image`: Same image as the web app.
        *   `spec.template.spec.containers[0].command`: `["celery"]`
        *   `spec.template.spec.containers[0].args`: `["-A", "src.task_queue.celery_app", "worker", "-l", "INFO"]` (adjust queues as needed)
        *   `spec.template.metadata.annotations` (scaling) might be different.
        *   Ingress settings: Typically set to internal-only if workers don't need public URLs.
        *   Environment variables (from secrets) will be similar to the web app service.
        Deploy it:
        ```bash
        gcloud run services replace gcp_configs/cloudrun/service-worker.yaml --region YOUR_WORKER_REGION
        ```

3.  **Manual Cloud Build Trigger:** Use `scripts/trigger_cloud_build.sh` (ensure it's updated for any new substitutions like `_WORKER_SERVICE_NAME`).

### Step 4.4: Networking, Logging, and Monitoring

*   **Networking:**
    *   Web App: Configure custom domain as needed.
    *   Worker: Typically internal. Ensure it can reach MongoDB and Redis (via VPC Access Connector if they are on private IPs).
*   **Logging:** Celery worker logs (stdout/stderr) will appear in Cloud Logging, filterable by the worker service name.
*   **Monitoring:**
    *   Monitor Cloud Run metrics for both web and worker services.
    *   Monitor Redis (Memorystore) for queue length, memory usage, connections. This is crucial for understanding task backlog and worker performance.
    *   Set up alerts for high queue lengths or high error rates in Celery tasks.

## 5. Example Deployment Scripts
*   **`scripts/setup_gcp_secrets.sh`:** Update this script to include `REDIS_URL_ACTIVITY_LOGGER` (or your chosen secret name for `REDIS_URL`).
*   **`scripts/trigger_cloud_build.sh`:** Ensure this script can pass or has defaults for new substitutions like `_WORKER_SERVICE_NAME` and secret names related to Redis.

## 6. Security Considerations
*   **Redis Security:** If using Memorystore, ensure "AUTH" (password) is enabled and store the auth string securely. Control access via VPC networks and the Serverless VPC Access connector.
*   **Worker Service Security:** Cloud Run worker services should generally not have public ingress (`--no-allow-unauthenticated`).
*   Other considerations as previously listed (IAM, Secret Management, Container Security, API Security).

## 7. Cost Considerations
*   **Memorystore for Redis:** Pricing depends on instance size, tier, and network traffic.
*   Factor in costs for potentially always-on Celery workers (`min-instances=1`) if needed for responsiveness, versus scale-to-zero for cost savings if queue processing can tolerate delays.
*   Other costs as previously listed.

This updated plan incorporates Celery and Redis into the GCP deployment, focusing on running workers as a separate, scalable Cloud Run service.
```
