# GCP Cloud Run Deployment Guide

This guide explains how to deploy the German gasoline price analysis dashboard to Google Cloud Run using the provided helper script.

## Prerequisites

Before running the deployment script, ensure you have the following set up on your local machine:

1. **Google Cloud SDK**:
   Install the `gcloud` CLI tool. On macOS, you can install it using Homebrew:
   ```bash
   brew install --cask google-cloud-sdk
   ```
2. **Docker**:
   Ensure Docker is installed and running on your system (e.g., Docker Desktop).

## Authentication & Setup

1. **Log in to Google Cloud**:
   Authenticate the `gcloud` CLI with your Google account:
   ```bash
   gcloud auth login
   ```
2. **Configure IAM Permissions** (if not already set up):
   Ensure your account or build service account has the necessary permissions. You may need to run commands like:
   ```bash
   gcloud projects add-iam-policy-binding project-75366ce0-f637-4d56-bcb \
       --member="serviceAccount:751243983026-compute@developer.gserviceaccount.com" \
       --role="roles/artifactregistry.writer"
   ```

## Deploying the Dashboard

A deployment script [deploy_gcp.sh](file:///Users/l1/Desktop/1_Project_German_GasolinePrices21.05/deploy_gcp.sh) has been provided in the project root.

1. **Make the script executable**:
   ```bash
   chmod +x deploy_gcp.sh
   ```
2. **Run the script**:
   ```bash
   ./deploy_gcp.sh
   ```

The script will automatically build a Docker container from the `Dockerfile` in the root, push it to Google Artifact Registry, and deploy it to Google Cloud Run as a public, unauthenticated service.
