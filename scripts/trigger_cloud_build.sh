#!/bin/bash
# scripts/trigger_cloud_build.sh
# Example script to manually trigger a Google Cloud Build using cloudbuild.yaml.
#
# PREREQUISITES:
# 1. Google Cloud SDK (gcloud) installed and authenticated with appropriate permissions.
#    (e.g., roles/cloudbuild.builds.editor to trigger builds)
# 2. Cloud Build API enabled in your GCP project.
# 3. Artifact Registry API enabled and a repository created (as per cloudbuild.yaml setup).
# 4. `cloudbuild.yaml` exists in the project root.
# 5. Your GCP Project ID is correctly set below.
# 6. (Optional) If your cloudbuild.yaml uses specific substitution variables not defined
#    with defaults in the file itself, you might need to pass them here.
#
# USAGE:
# 1. IMPORTANT: Replace the placeholder for YOUR_PROJECT_ID.
# 2. (Optional) Modify or add to the SUBSTITUTIONS string if you need to override
#    any default substitution variables defined in cloudbuild.yaml or provide
#    those that don't have defaults.
# 3. Make the script executable: chmod +x scripts/trigger_cloud_build.sh
# 4. Run the script from the project root: ./scripts/trigger_cloud_build.sh

set -e # Exit immediately if a command exits with a non-zero status.
# set -x # Uncomment for debugging

# !!! REPLACE with your GCP Project ID !!!
PROJECT_ID="your-gcp-project-id"

# --- Define Cloud Build substitutions ---
# These can override the default values in cloudbuild.yaml's 'substitutions' block.
# Format: "_VAR_NAME=value,_VAR_NAME2=value2" (comma-separated key-value pairs)
#
# The COMMIT_SHA is automatically provided by Cloud Build when run from a Git context (e.g., trigger).
# For manual submissions like this, Cloud Build will use the current HEAD commit SHA if
# the build source is a local Git repository. If submitting a packed source, it might be different.
#
# Example: Override the service name or artifact registry region
# Ensure these variable names (e.g., _SERVICE_NAME) match those in your cloudbuild.yaml
#
# SUBSTITUTIONS="_SERVICE_NAME=my-prod-logger-service"
# SUBSTITUTIONS="$SUBSTITUTIONS,_ARTIFACT_REGISTRY_REGION=europe-west1"
# SUBSTITUTIONS="$SUBSTITUTIONS,_CLOUD_RUN_REGION=europe-west1"
#
# For this example, we assume cloudbuild.yaml has sensible defaults or you've configured
# them in a Cloud Build trigger. If you need to pass many, consider a config file for substitutions.
# If your cloudbuild.yaml has all necessary defaults, this can be an empty string.
SUBSTITUTIONS=""

# You can also specify a branch or tag to build, if your source is a repo:
# For example, to build the 'main' branch:
# SOURCE_REVISION="main"
# gcloud builds submit . --project="$PROJECT_ID" --config=cloudbuild.yaml --substitutions="$SUBSTITUTIONS" --branch="$SOURCE_REVISION"

# Or to build a specific tag:
# SOURCE_TAG="v1.0.0"
# gcloud builds submit . --project="$PROJECT_ID" --config=cloudbuild.yaml --substitutions="$SUBSTITUTIONS" --tag="$SOURCE_TAG"


echo "====================================================="
echo "Triggering Cloud Build for project: $PROJECT_ID"
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" == "your-gcp-project-id" ]; then
    echo "ERROR: PROJECT_ID is not set or is still the placeholder value."
    echo "Please edit this script and set your GCP Project ID."
    exit 1
fi

if [ -n "$SUBSTITUTIONS" ]; then
  echo "Using custom substitutions: $SUBSTITUTIONS"
  # Remove leading comma if it exists (from prepending with ,_VAR_NAME=value)
  # This is a bit fragile; better to build the string carefully.
  # A safer way if building SUBSTITUTIONS string:
  #   sub_array=()
  #   sub_array+=("_VAR1=val1")
  #   sub_array+=("_VAR2=val2")
  #   SUBSTITUTIONS=$(IFS=,; echo "${sub_array[*]}")
  # For now, assuming user manages the comma correctly if multiple are added.
  effective_substitutions="--substitutions=$SUBSTITUTIONS"
else
  echo "Using default substitutions from cloudbuild.yaml (if any defined there)."
  effective_substitutions="" # Pass empty string if no script-level overrides
fi

echo "Submitting build using source from current directory ('.')"
echo "Config file: cloudbuild.yaml"
echo "====================================================="

# Submit the build. The source is the current directory.
gcloud builds submit . \
  --project="$PROJECT_ID" \
  --config=cloudbuild.yaml \
  $effective_substitutions # This will be empty if SUBSTITUTIONS is empty

echo "====================================================="
echo "Cloud Build triggered."
echo "Monitor build progress in the Google Cloud Console: https://console.cloud.google.com/cloud-build/builds?project=$PROJECT_ID"
echo "====================================================="
