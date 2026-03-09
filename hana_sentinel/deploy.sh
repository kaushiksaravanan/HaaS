#!/bin/bash
echo "Deploying HANA Sentinel to Google App Engine..."
gcloud app deploy app.yaml --project=ai-connect-sap26blr-325 --quiet
echo "Deployment initiated."
