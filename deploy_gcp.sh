#!/bin/bash
# Stop execution on any error
set -e

# Load deployment config from the gitignored .env file in the project root.
# The .env file is expected to contain:
#   GOOGLE_CLOUD_PROJECT=your-gcp-project-id
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$SCRIPT_DIR/.env"
  set +a
fi

GCP_PROJECT="${GOOGLE_CLOUD_PROJECT:-}"

if [ -z "$GCP_PROJECT" ]; then
  echo "ERROR: GOOGLE_CLOUD_PROJECT is not set."
  echo "Add GOOGLE_CLOUD_PROJECT=your-gcp-project-id to .env or export it as an environment variable."
  exit 1
fi

echo "Starting deployment to Google Cloud Run..."
echo "Project: $GCP_PROJECT"
echo "Service: gasoline-dashboard"
echo "Region:  europe-west3"
echo "========================================="

# Deploy the application using local gcloud credentials
gcloud run deploy gasoline-dashboard \
    --source . \
    --region europe-west3 \
    --allow-unauthenticated \
    --project "$GCP_PROJECT"
