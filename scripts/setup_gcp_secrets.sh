#!/bin/bash
# scripts/setup_gcp_secrets.sh
# Example script to create secrets in Google Secret Manager.
#
# PREREQUISITES:
# 1. Google Cloud SDK (gcloud) installed and authenticated with appropriate permissions.
#    (e.g., roles/secretmanager.admin or roles/secretmanager.secretVersionAdder)
# 2. Secret Manager API enabled in your GCP project.
# 3. Your GCP Project ID is correctly set below.
#
# USAGE:
# 1. IMPORTANT: Review and replace ALL placeholder values (especially YOUR_PROJECT_ID
#    and "YOUR_ACTUAL_VALUE_HERE" placeholders for secret values).
# 2. Make the script executable: chmod +x scripts/setup_gcp_secrets.sh
# 3. Run the script: ./scripts/setup_gcp_secrets.sh
#
# SECURITY WARNING:
# - This script, if placeholders are filled directly, will contain sensitive values.
# - DO NOT commit this script with actual secret values to version control.
# - For better security:
#   a) Load secret values from environment variables or a secure local file (not committed).
#   b) Use interactive prompts (read -s) to enter secret values.
#   c) Integrate with a more robust secret management workflow if available.
# - This script is for demonstration and initial setup convenience.

set -e # Exit immediately if a command exits with a non-zero status.
# set -x # Uncomment for debugging (prints commands and their arguments)

# !!! REPLACE with your GCP Project ID !!!
PROJECT_ID="your-gcp-project-id"

# Optional: Specify a region for your secrets if not using global/automatic.
# If using regional secrets, ensure your Cloud Run service is in a supported region for direct secret integration.
# LOCATION="us-central1" # Example for regional secret
# REPLICATION_POLICY="user-managed --locations=$LOCATION" # If using regional
REPLICATION_POLICY="automatic" # For automatic replication (simplest)


# --- Helper function to create a secret (if it doesn't exist) and add a version ---
create_or_update_secret() {
  local secret_id="$1" # Name of the secret in Secret Manager (e.g., MONGO_URI_ACTIVITY_LOGGER)
  local secret_value="$2" # The actual secret content

  echo "-----------------------------------------------------"
  echo "Processing secret: $secret_id"

  # Check if secret exists
  if gcloud secrets describe "$secret_id" --project="$PROJECT_ID" &>/dev/null; then
    echo "Secret '$secret_id' already exists. Adding new version."
  else
    echo "Secret '$secret_id' does not exist. Creating..."
    gcloud secrets create "$secret_id" \
      --project="$PROJECT_ID" \
      --replication-policy="$REPLICATION_POLICY" \
      # --labels="app=activity-logger,env=dev" # Optional: Add labels
    echo "Secret '$secret_id' created."
  fi

  # Add secret version from stdin. The -n ensures no trailing newline is added to the secret value.
  echo -n "$secret_value" | gcloud secrets versions add "$secret_id" \
    --project="$PROJECT_ID" \
    --data-file="-" # Reads data from stdin
  echo "New version added for secret '$secret_id'."
}

# --- Define and Create/Update Secrets ---
# IMPORTANT: Replace "YOUR_ACTUAL_VALUE_HERE" with the real secret values.
# These names should match the _SECRET_NAME substitutions in your cloudbuild.yaml
# or the secret names you configure directly in Cloud Run service definition.

echo "Starting secret setup for project: $PROJECT_ID"
echo "Make sure you have replaced placeholder values in this script!"
echo "Press Ctrl+C to cancel within 5 seconds if not ready..."
sleep 5


# Example secret names matching cloudbuild.yaml substitutions (with _ACTIVITY_LOGGER suffix)
create_or_update_secret "MONGO_URI_ACTIVITY_LOGGER" "mongodb://YOUR_MONGO_USER:YOUR_MONGO_PASSWORD@YOUR_MONGO_HOST:PORT/YOUR_DB_NAME" # !!! REPLACE !!!
create_or_update_secret "AUTH_MONGO_DB_NAME_ACTIVITY_LOGGER" "auth_db_name_example" # !!! REPLACE (e.g., auth_db_prod) !!!
create_or_update_secret "JWT_SECRET_KEY_ACTIVITY_LOGGER" "YOUR_VERY_STRONG_RANDOM_JWT_SECRET_KEY_HERE_$(date +%s)" # !!! REPLACE !!!
create_or_update_secret "ACCESS_TOKEN_EXPIRE_MINUTES_ACTIVITY_LOGGER" "60" # Example value

# Microsoft Graph API Credentials (only if feature is used)
create_or_update_secret "AZURE_CLIENT_ID_ACTIVITY_LOGGER" "YOUR_AZURE_APP_CLIENT_ID" # !!! REPLACE !!!
create_or_update_secret "AZURE_CLIENT_SECRET_ACTIVITY_LOGGER" "YOUR_AZURE_APP_CLIENT_SECRET_VALUE" # !!! REPLACE !!!
create_or_update_secret "AZURE_TENANT_ID_ACTIVITY_LOGGER" "YOUR_AZURE_AD_TENANT_ID" # !!! REPLACE !!!
create_or_update_secret "GRAPH_TARGET_USER_ID_ACTIVITY_LOGGER" "target_user_email_or_id@your_domain.com" # !!! REPLACE !!!

# GRAPH_MAIL_FOLDER is often not a secret, but if you want to manage it via Secret Manager:
# create_or_update_secret "GRAPH_MAIL_FOLDER_ACTIVITY_LOGGER" "Inbox"


echo "-----------------------------------------------------"
echo "Secret setup process completed."
echo "IMPORTANT:"
echo "1. Verify in GCP Secret Manager that secrets and versions were created as expected."
echo "2. Ensure the Cloud Build service account (if used for deployment) and the Cloud Run"
echo "   runtime service account have the 'Secret Manager Secret Accessor' IAM role"
echo "   on these specific secrets or on the project level."
echo "3. If you hardcoded any actual secret values in this script, ensure it's handled securely"
echo "   (e.g., delete after use, do not commit to version control)."
echo "-----------------------------------------------------"
