#!/bin/bash
# Stop execution on any error
set -e

# Support overriding the target GCP Project ID via environment variable
GCP_PROJECT=${GOOGLE_CLOUD_PROJECT:-project-75366ce0-f637-4d56-bcb}

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
