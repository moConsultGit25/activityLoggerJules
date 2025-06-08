# Deployment Plan: Automated Activity Logger on Google Cloud Platform (GCP)

## 1. Introduction

This document outlines a plan for deploying the containerized "Automated Activity Logger" application to Google Cloud Platform (GCP). It assumes the application has been containerized using Docker and a `docker-compose.yml` is available for local development, as this informs the services and configurations needed.

The primary goal is to deploy a scalable, secure, and maintainable version of the application.

## 2. Prerequisites

*   **Google Cloud SDK (`gcloud` CLI):** Installed and configured on your local machine. ([Installation Guide](https://cloud.google.com/sdk/docs/install))
*   **GCP Project:** A Google Cloud Project created with billing enabled. Note your `PROJECT_ID`.
*   **Docker:** Docker installed locally for building and pushing container images.
*   **Required APIs Enabled:** Ensure the following APIs are enabled in your GCP project:
    *   Artifact Registry API
    *   Cloud Run API
    *   Secret Manager API
    *   Cloud Build API (if using Cloud Build for CI/CD)
    *   (Any other APIs specific to services you choose, e.g., Compute Engine if self-hosting MongoDB)

## 3. Core GCP Services to Use

*   **Artifact Registry:** Private Docker container registry to store and manage your application images.
*   **Cloud Run:** Serverless platform to run your stateless containerized FastAPI application. It scales automatically (including to zero) and simplifies deployment.
*   **MongoDB Solution:**
    *   **MongoDB Atlas on GCP (Recommended):** A managed MongoDB service available via the GCP Marketplace. Simplifies database management, backups, and scaling.
    *   **Self-managed on Compute Engine (Advanced):** Deploying MongoDB on a cluster of GCE virtual machines. Provides more control but significantly increases operational overhead.
*   **Secret Manager:** Securely store and manage sensitive configuration data like API keys, database credentials, and JWT secrets.
*   **Cloud Logging & Cloud Monitoring:** Integrated services for application logging, performance monitoring, and setting up alerts.
*   **Cloud Build (Optional, for CI/CD):** Automate the process of building Docker images and deploying them to Cloud Run upon code changes.
*   **Cloud DNS & Load Balancing (Optional):** For custom domain mapping, SSL certificate management (often handled by Cloud Run custom domains directly or by a dedicated Cloud Load Balancer for more complex setups).

## 4. Deployment Steps Outline

### Step 4.1: Set up MongoDB

Choose one of the following options:

*   **Option A: MongoDB Atlas on GCP (Recommended)**
    1.  Navigate to the GCP Marketplace and search for "MongoDB Atlas".
    2.  Follow the instructions to create a new MongoDB Atlas cluster, choosing a region close to your Cloud Run services.
    3.  Configure database users and access controls (e.g., IP Whitelisting to allow access from Cloud Run, or VPC Peering for more secure private networking).
    4.  Obtain the MongoDB connection string (SRV record). This will be stored in Secret Manager.

*   **Option B: Self-managed MongoDB on Google Compute Engine (Advanced)**
    1.  Provision a set of GCE instances.
    2.  Install and configure MongoDB, preferably as a replica set for high availability.
    3.  Set up firewall rules to control access to your MongoDB instances.
    4.  Securely note the connection string.

### Step 4.2: Configure Secret Manager

1.  Navigate to Secret Manager in the GCP Console.
2.  Create secrets for all sensitive environment variables required by your application. These include:
    *   `MONGO_URI`: The MongoDB connection string obtained in Step 4.1.
    *   `AUTH_MONGO_DB_NAME`: Name of the database for user authentication.
    *   `JWT_SECRET_KEY`: A strong, randomly generated secret for signing JWTs.
    *   `ACCESS_TOKEN_EXPIRE_MINUTES`: JWT expiration time.
    *   `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`: For Microsoft Graph API integration (if used).
    *   `GRAPH_TARGET_USER_ID`, `GRAPH_MAIL_FOLDER`: For Microsoft Graph API integration (if used).
3.  For each secret, note its "Resource ID" (e.g., `projects/PROJECT_ID/secrets/SECRET_NAME/versions/latest`).
4.  Grant the Cloud Run service's runtime service account the "Secret Manager Secret Accessor" IAM role for each secret it needs to access.

### Step 4.3: Build and Push Docker Image to Artifact Registry

1.  **Enable Artifact Registry API** in your GCP project.
2.  **Create a Docker Repository:**
    ```bash
    gcloud artifacts repositories create REPO_NAME \
        --repository-format=docker \
        --location=REGION \
        --description="Docker repository for Automated Activity Logger"
    # Example: REGION=us-central1, REPO_NAME=activity-logger-repo
    ```
3.  **Configure Docker Authentication:**
    ```bash
    gcloud auth configure-docker REGION-docker.pkg.dev
    # Example: gcloud auth configure-docker us-central1-docker.pkg.dev
    ```
4.  **Prepare Production Dockerfile:**
    *   Ensure your `Dockerfile` is optimized for production:
        *   Remove `--reload` from the Uvicorn `CMD`.
        *   Consider using a non-root user within the container.
        *   Multi-stage builds can reduce image size by separating build-time dependencies from runtime dependencies.
        *   Ensure `EXPOSE 8000` (or your app's port) is present.
        *   The `PYTHONPATH` and `PYTHONUNBUFFERED` environment variables are good practice.
5.  **Build the Docker Image:**
    ```bash
    # Replace with your specific values
    export REGION="us-central1" # Or your preferred region
    export PROJECT_ID="your-gcp-project-id"
    export REPO_NAME="activity-logger-repo"
    export IMAGE_NAME="backend-service"
    export IMAGE_TAG="latest" # Or a specific version tag, e.g., v1.0.0

    docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:${IMAGE_TAG} .
    ```
6.  **Push the Docker Image:**
    ```bash
    docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:${IMAGE_TAG}
    ```

### Step 4.4: Deploy to Cloud Run

1.  **Deploy the Container Image:**
    ```bash
    gcloud run deploy activity-logger-service \
        --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:${IMAGE_TAG} \
        --platform=managed \
        --region=${REGION} \
        --allow-unauthenticated \ # Or --no-allow-unauthenticated for internal services / authenticated access via IAM or IAP
        --port=8000 \
        # --service-account=YOUR_SERVICE_ACCOUNT_EMAIL \ # Optional: if not using default Compute Engine SA
        --set-env-vars="^##^MONGO_URI=secret:projects/${PROJECT_ID}/secrets/MONGO_URI/versions/latest##AUTH_MONGO_DB_NAME=secret:projects/${PROJECT_ID}/secrets/AUTH_MONGO_DB_NAME/versions/latest##JWT_SECRET_KEY=secret:projects/${PROJECT_ID}/secrets/JWT_SECRET_KEY/versions/latest##ACCESS_TOKEN_EXPIRE_MINUTES=secret:projects/${PROJECT_ID}/secrets/ACCESS_TOKEN_EXPIRE_MINUTES/versions/latest##AZURE_CLIENT_ID=secret:projects/${PROJECT_ID}/secrets/AZURE_CLIENT_ID/versions/latest##AZURE_CLIENT_SECRET=secret:projects/${PROJECT_ID}/secrets/AZURE_CLIENT_SECRET/versions/latest##AZURE_TENANT_ID=secret:projects/${PROJECT_ID}/secrets/AZURE_TENANT_ID/versions/latest##GRAPH_TARGET_USER_ID=secret:projects/${PROJECT_ID}/secrets/GRAPH_TARGET_USER_ID/versions/latest##GRAPH_MAIL_FOLDER=Inbox"
    # Note on --set-env-vars: The format is "KEY1=value1##KEY2=value2".
    # For secrets: "KEY=secret:projects/PROJECT_ID/secrets/SECRET_NAME/versions/VERSION"
    # Replace SECRET_NAME and VERSION (often 'latest') as appropriate.
    # Ensure the Cloud Run service account has permissions to access these secrets.
    ```
    *   Adjust `--allow-unauthenticated` based on your security requirements. If you want to protect the API with IAM or IAP, use `--no-allow-unauthenticated` and configure accordingly. API Gateway can also be used in front of Cloud Run.
    *   The environment variables are directly injected from Secret Manager.
2.  **Configure Cloud Run Service Settings (via Console or `gcloud` updates):**
    *   **CPU & Memory:** Start with defaults and adjust based on performance monitoring.
    *   **Concurrency:** Number of requests a single container instance can handle simultaneously.
    *   **Min/Max Instances:** Configure auto-scaling parameters. `min-instances=0` allows scaling to zero.
    *   **Service Account:** Ensure the runtime service account for Cloud Run has the "Secret Manager Secret Accessor" role for the secrets defined, plus "Cloud Logging Writer" and "Cloud Monitoring Metric Writer".

### Step 4.5: Configure Networking (Custom Domain & SSL - Optional)

1.  If you have a custom domain:
    *   Navigate to Cloud Run in the GCP Console, select your service.
    *   Go to "Manage custom domains".
    *   Add your domain mapping and follow the verification steps (usually involves updating DNS records).
2.  Google automatically provisions and renews SSL certificates for custom domains mapped to Cloud Run.

### Step 4.6: Set up Logging & Monitoring

1.  **Cloud Logging:** Logs from `stdout` and `stderr` in your container (e.g., Python `print()` statements, Uvicorn access logs) are automatically collected and viewable in Cloud Logging.
2.  **Cloud Monitoring:** Basic metrics (request count, latency, container CPU/memory) are automatically collected.
3.  Create custom dashboards or alerts in Cloud Monitoring for key performance indicators or error rates.

## 5. CI/CD Pipeline (Conceptual using Cloud Build)

A CI/CD pipeline can automate the build and deployment process:

1.  **Source Repository:** Use a Git repository (e.g., GitHub, Cloud Source Repositories).
2.  **Cloud Build Trigger:**
    *   Create a trigger in Cloud Build that listens for changes (e.g., pushes to `main` branch or creation of tags).
3.  **`cloudbuild.yaml` File (in your repository root):**
    Define the build steps:
    ```yaml
    steps:
    # Step 1: Build the Docker image
    - name: 'gcr.io/cloud-builders/docker'
      args:
        - 'build'
        - '-t'
        - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPO_NAME}/${_IMAGE_NAME}:${COMMIT_SHA}' # Tag with commit SHA
        - '.'
      id: 'Build Docker Image'

    # Step 2: Push the Docker image to Artifact Registry
    - name: 'gcr.io/cloud-builders/docker'
      args:
        - 'push'
        - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPO_NAME}/${_IMAGE_NAME}:${COMMIT_SHA}'
      id: 'Push to Artifact Registry'

    # Step 3: Deploy to Cloud Run
    - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
      entrypoint: gcloud
      args:
        - 'run'
        - 'deploy'
        - '${_SERVICE_NAME}' # Your Cloud Run service name
        - '--image=${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPO_NAME}/${_IMAGE_NAME}:${COMMIT_SHA}'
        - '--region=${_REGION}'
        - '--platform=managed'
        - '--quiet' # Suppress interactive prompts
        # Add other deployment flags like --set-env-vars, --service-account etc.
        # These can also use substitutions from the trigger or _variables in cloudbuild.yaml
      id: 'Deploy to Cloud Run'

    # Optional: Tag image with 'latest' or other tags
    # - name: 'gcr.io/cloud-builders/docker'
    #   args: ['tag', '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPO_NAME}/${_IMAGE_NAME}:${COMMIT_SHA}', '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPO_NAME}/${_IMAGE_NAME}:latest']
    # - name: 'gcr.io/cloud-builders/docker'
    #   args: ['push', '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPO_NAME}/${_IMAGE_NAME}:latest']

    images:
      - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPO_NAME}/${_IMAGE_NAME}:${COMMIT_SHA}'
      # - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPO_NAME}/${_IMAGE_NAME}:latest' # If tagging latest

    # Define substitutions (can also be set in the trigger configuration)
    # _REGION: 'us-central1'
    # _REPO_NAME: 'activity-logger-repo'
    # _IMAGE_NAME: 'backend-service'
    # _SERVICE_NAME: 'activity-logger-service'
    ```
    *   This `cloudbuild.yaml` uses substitutions (e.g., `_REGION`, `PROJECT_ID`, `COMMIT_SHA`). `COMMIT_SHA` is a built-in substitution. Others can be configured in the trigger.

## 6. Security Considerations

*   **Regular Updates:** Keep the Python base image and all dependencies in `requirements.txt` updated to patch vulnerabilities.
*   **Principle of Least Privilege:**
    *   Assign minimal necessary IAM roles to service accounts (e.g., Cloud Run runtime service account).
    *   Restrict access to Secret Manager secrets.
*   **Firewall Rules:** Cloud Run manages ingress firewalling. If using Compute Engine for MongoDB, configure firewall rules strictly.
*   **API Security:**
    *   Use HTTPS (handled by Cloud Run).
    *   Ensure robust authentication/authorization for API endpoints (JWT implementation is a good start).
    *   Consider rate limiting, input validation (Pydantic helps here).
*   **Secret Management:** Use Secret Manager for all sensitive data; do not hardcode secrets or commit them to version control.

## 7. Cost Considerations

*   **Cloud Run:** Priced based on vCPU-seconds, memory-seconds, number of requests, and outbound network traffic. Generous free tier usually available.
*   **MongoDB Atlas:** Pricing depends on the chosen cluster tier, storage, and data transfer. Has a free tier for small projects.
*   **Artifact Registry:** Priced based on storage and data transfer out.
*   **Secret Manager:** Priced based on the number of active secret versions and access operations.
*   **Cloud Logging/Monitoring:** Generous free tiers, costs can accrue for high-volume logging/metrics or extended retention.
*   **Cloud Build:** Priced per build-minute, with a free tier.
*   **Recommendation:** Set up budget alerts in GCP Billing to monitor and control costs. Use the GCP pricing calculator to estimate potential expenses.

This plan provides a comprehensive starting point. Specific configurations and choices will need to be adapted based on the application's exact requirements and scale.
```
