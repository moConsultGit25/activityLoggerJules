# Deployment Plan: Automated Activity Logger on Google Cloud Platform (GCP)

## 1. Introduction

This document outlines a plan for deploying the containerized "Automated Activity Logger" application to Google Cloud Platform (GCP). It assumes the application has been containerized (as per `Dockerfile.prod`) and that `cloudbuild.yaml` and `gcp_configs/cloudrun/service.yaml` are available as starting points for CI/CD and declarative service configuration.

The primary goal is to deploy a scalable, secure, and maintainable version of the application on GCP.

## 2. Prerequisites

*   **Google Cloud SDK (`gcloud` CLI):** Installed and authenticated with appropriate permissions for your GCP project. ([Installation Guide](https://cloud.google.com/sdk/docs/install))
*   **GCP Project:** A Google Cloud Project created with billing enabled. Note your `PROJECT_ID`.
*   **Docker:** Docker installed locally if you need to build and test images locally before pushing or using Cloud Build.
*   **Enabled APIs:** Ensure the following APIs are enabled in your GCP project:
    *   Artifact Registry API (to store Docker images)
    *   Cloud Run API (to run the service)
    *   Secret Manager API (to store sensitive configurations)
    *   Cloud Build API (for CI/CD automation)
    *   IAM API (to manage permissions)

## 3. Core GCP Services Overview

*   **Artifact Registry:** Private Docker container registry for storing and managing application images built by Cloud Build or pushed manually.
*   **Cloud Run:** Serverless platform to run the containerized FastAPI application. Handles auto-scaling (including to zero), HTTPS, and integrates with other GCP services.
*   **MongoDB Solution:**
    *   **MongoDB Atlas on GCP (Recommended):** Managed MongoDB service via GCP Marketplace. Simplifies database operations.
    *   **Self-managed on Compute Engine (Advanced):** More control, higher operational effort.
*   **Secret Manager:** For secure storage of all sensitive data (database URIs, API keys, JWT secrets, Azure credentials).
*   **Cloud Logging & Cloud Monitoring:** For centralized logging, metrics, and alerting.
*   **Cloud Build:** To automate building Docker images from source (using `Dockerfile.prod`) and deploying to Cloud Run, as defined in `cloudbuild.yaml`.
*   **IAM (Identity and Access Management):** To manage permissions for users and service accounts.

## 4. Deployment Workflow

This workflow emphasizes automation using Cloud Build and declarative configurations where possible.

### Step 4.1: Initial Setup & Configuration

1.  **MongoDB Setup:**
    *   Provision your chosen MongoDB solution (MongoDB Atlas on GCP is recommended).
    *   Securely obtain the connection string. This will be stored as a secret.

2.  **Secret Configuration in Secret Manager:**
    *   Using the GCP Console or `gcloud` CLI (referencing `scripts/setup_gcp_secrets.sh` for examples), create secrets in Secret Manager for ALL environment variables that contain sensitive data. These secret names must match those referenced in `cloudbuild.yaml` and `gcp_configs/cloudrun/service.yaml`. Example secret names (from `cloudbuild.yaml` substitutions):
        *   `MONGO_URI_ACTIVITY_LOGGER`
        *   `AUTH_MONGO_DB_NAME_ACTIVITY_LOGGER`
        *   `JWT_SECRET_KEY_ACTIVITY_LOGGER`
        *   `AZURE_CLIENT_ID_ACTIVITY_LOGGER`
        *   `AZURE_CLIENT_SECRET_ACTIVITY_LOGGER`
        *   `AZURE_TENANT_ID_ACTIVITY_LOGGER`
        *   `GRAPH_TARGET_USER_ID_ACTIVITY_LOGGER`
        *   `ACCESS_TOKEN_EXPIRE_MINUTES_ACTIVITY_LOGGER` (if treated as a secret)
        *   `GRAPH_MAIL_FOLDER_ACTIVITY_LOGGER` (if treated as a secret)
    *   **Crucial:** The names used here (e.g., `MONGO_URI_ACTIVITY_LOGGER`) are the *names of the secrets in Secret Manager*. The `cloudbuild.yaml` and `service.yaml` will refer to these names.

3.  **IAM Permissions (Summary):**
    A summary of key roles needed:
    *   **User performing initial setup/manual steps:**
        *   Project Owner/Editor (for enabling APIs, creating resources broadly).
        *   Secret Manager Admin (to create and manage secrets).
        *   Artifact Registry Administrator (to create repositories).
        *   Cloud Run Admin (to deploy services manually or set up initial service).
        *   Cloud Build Editor (to trigger builds manually or set up triggers).
    *   **Cloud Build Service Account (`[PROJECT_NUMBER]@cloudbuild.gserviceaccount.com`):**
        *   Artifact Registry Writer (to push images to Artifact Registry).
        *   Cloud Run Admin (to deploy and manage Cloud Run services).
        *   Secret Manager Secret Accessor (to access secrets during deployment for Cloud Run env vars).
        *   Service Account User (on the Cloud Run runtime service account, if a non-default one is used).
    *   **Cloud Run Runtime Service Account (either default Compute Engine SA or a dedicated one):**
        *   Secret Manager Secret Accessor (to access the application's runtime secrets).
        *   Cloud Logging Writer (for application logs).
        *   Cloud Monitoring Metric Writer (for application metrics).
        *   (Any other GCP services the application needs to interact with at runtime).
    Grant these roles using the IAM page in the GCP Console.

### Step 4.2: CI/CD Setup with Cloud Build

This is the recommended approach for ongoing deployments.

1.  **Artifact Registry Repository:**
    *   Create a Docker repository in Artifact Registry if you haven't already (see `scripts/setup_gcp_secrets.sh` for gcloud command example, or use Console).
    *   Example: `gcloud artifacts repositories create app-images --repository-format=docker --location=us-central1` (match `_ARTIFACT_REGISTRY_REPO` and `_ARTIFACT_REGISTRY_REGION` in `cloudbuild.yaml`).

2.  **Review `Dockerfile.prod`:**
    *   This file is specifically designed for production builds (non-root user, no Uvicorn reload). It will be used by Cloud Build.

3.  **Review and Customize `cloudbuild.yaml`:**
    *   This file defines the build, push, and deploy steps.
    *   Ensure substitution variables (like `_SERVICE_NAME`, `_ARTIFACT_REGISTRY_REGION`, `_ARTIFACT_REGISTRY_REPO`, `_CLOUD_RUN_REGION`, and all `_SECRET_NAME` variables) are correctly defined with defaults or are intended to be overridden in your Cloud Build trigger configuration.
    *   The `cloudbuild.yaml` is configured to use `Dockerfile.prod`.

4.  **Configure Cloud Build Trigger:**
    *   Navigate to Cloud Build in the GCP Console.
    *   Create a new trigger, connecting it to your Git repository.
    *   Configure the trigger event (e.g., push to `main` branch).
    *   Set the Build Configuration to use your `cloudbuild.yaml` file.
    *   In the "Advanced" section -> "Substitution variables", define any values that need to override the defaults in `cloudbuild.yaml` (e.g., specific secret names if they differ from the defaults in `cloudbuild.yaml`). `PROJECT_ID` and `COMMIT_SHA` are typically available as built-in substitutions.

### Step 4.3: Initial Deployment / Manual Deployment (If not using full CI/CD trigger initially)

1.  **Manual Image Build & Push (if not using Cloud Build for first time):**
    *   Follow Step 4.3 in the previous "Deployment Steps Outline" (using `docker build -f Dockerfile.prod ...` and `docker push ...`).

2.  **Declarative Service Deployment with `service.yaml`:**
    *   Customize `gcp_configs/cloudrun/service.yaml`:
        *   Replace ALL placeholders: `YOUR_PROJECT_ID`, `YOUR_CLOUD_RUN_SERVICE_ACCOUNT_EMAIL` (if using a specific one, otherwise remove the line to use default), the full `image` URI from Artifact Registry (pointing to your pushed image, e.g., from the manual build or a Cloud Build run), and ensure secret names match those created in Secret Manager.
    *   Deploy using `gcloud`:
        ```bash
        gcloud run services replace gcp_configs/cloudrun/service.yaml --region YOUR_CLOUD_RUN_REGION
        # Example: gcloud run services replace gcp_configs/cloudrun/service.yaml --region us-central1
        ```
    This command is useful for creating the service with all its configurations or for updating it declaratively.

3.  **Manual Cloud Build Trigger (using `scripts/trigger_cloud_build.sh`):**
    *   If you want to test the Cloud Build pipeline manually or for one-off deployments:
    *   Customize and run `scripts/trigger_cloud_build.sh` as described in its comments and the "Example Deployment Scripts" section below. This will use `cloudbuild.yaml` to build and deploy.

### Step 4.4: Networking, Logging, and Monitoring

*   Follow "Step 4.5: Configure Networking" and "Step 4.6: Set up Logging & Monitoring" from the previous general outline. These are standard Cloud Run practices.

## 5. Example Deployment Scripts

The `scripts/` directory contains helper scripts:

*   **`scripts/setup_gcp_secrets.sh`:**
    *   **Purpose:** Assists in creating the necessary secrets in Google Secret Manager.
    *   **Usage:** Customize with your `PROJECT_ID` and actual secret values (do not commit real values). Run `chmod +x` and then execute. This script helps ensure your Secret Manager secrets match the names expected by `cloudbuild.yaml` and `service.yaml`.
*   **`scripts/trigger_cloud_build.sh`:**
    *   **Purpose:** Manually triggers a Cloud Build using `cloudbuild.yaml`.
    *   **Usage:** Customize with your `PROJECT_ID` and any necessary substitution overrides. Run `chmod +x` and then execute from the project root.

Review these scripts and their internal comments carefully before use.

## 6. Security Considerations

*   **IAM & Least Privilege:** Strictly adhere to the principle of least privilege for all service accounts (Cloud Build SA, Cloud Run runtime SA) and users.
*   **Secret Management:** All sensitive data MUST be stored in Secret Manager. Ensure secret names in your configurations (`cloudbuild.yaml`, `service.yaml`) accurately reference the created secrets.
*   **Container Security:** Use `Dockerfile.prod` for production images. Regularly scan images for vulnerabilities.
*   **API Security:** HTTPS is handled by Cloud Run. JWT authentication is implemented. Consider additional API security measures (rate limiting, WAF) if needed.
*   **Network Security:** If not using Serverless VPC Access for MongoDB, ensure MongoDB Atlas IP whitelisting is configured correctly. Cloud Run default ingress is "all traffic".

## 7. Cost Considerations

*   Monitor costs via GCP Billing. Set up budget alerts.
*   Cloud Run (scale-to-zero can be cost-effective), MongoDB Atlas (free tier available), Artifact Registry, Secret Manager, Cloud Build, Logging/Monitoring all have their own pricing models and potential free tiers.

This revised plan emphasizes automation and best practices for deploying to GCP.
```
