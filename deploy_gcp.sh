#!/bin/bash
# Stop execution on any error
set -e

echo "Starting deployment to Google Cloud Run..."
echo "Project: project-75366ce0-f637-4d56-bcb"
echo "Service: gasoline-dashboard"
echo "Region:  europe-west3"
echo "========================================="

# Deploy the application using local gcloud credentials
gcloud run deploy gasoline-dashboard \
    --source . \
    --region europe-west3 \
    --allow-unauthenticated \
    --project project-75366ce0-f637-4d56-bcb
