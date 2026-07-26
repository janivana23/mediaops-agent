#!/usr/bin/env bash
# Deploy MediaOps Agent to Cloud Run: backend + Postgres (Cloud SQL) +
# frontend, as two separate Cloud Run services.
#
# Builds happen via `gcloud builds submit` (Cloud Build) — no local Docker
# daemon required, which matters if, like on the machine this was written
# on, Docker Desktop is unreliable. Everything here is a real gcloud
# command, but it has NOT been run end-to-end against a live GCP project
# (no credentials were available in the environment this was written in) —
# read it before running it, the way you would any deploy script someone
# handed you.
#
# Prerequisites:
#   gcloud auth login
#   gcloud config set project "$PROJECT_ID"
#   gcloud services enable run.googleapis.com sqladmin.googleapis.com \
#       artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com
#
# Usage:
#   PROJECT_ID=my-gcp-project REGION=asia-southeast1 ./deploy/cloudrun-deploy.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-asia-southeast1}"
BACKEND_SERVICE="${BACKEND_SERVICE:-mediaops-backend}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-mediaops-frontend}"
REPO="${REPO:-mediaops}"

IMAGE_BACKEND="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/backend"
IMAGE_FRONTEND="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/frontend"

echo "== Artifact Registry repo (idempotent) =="
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker --location="$REGION" --quiet || true

echo "== Building backend image via Cloud Build =="
gcloud builds submit backend --tag "$IMAGE_BACKEND"

echo "== Deploying backend to Cloud Run =="
# --- Database ---------------------------------------------------------
# SQLite (this project's zero-config default) does NOT survive on Cloud
# Run: the filesystem is ephemeral per-instance and wiped on every cold
# start / scale-to-zero / redeploy. For anything beyond a one-off demo,
# point DATABASE_URL at Cloud SQL Postgres instead:
#
#   gcloud sql instances create mediaops-db --database-version=POSTGRES_16 \
#       --tier=db-f1-micro --region="$REGION"
#   gcloud sql databases create mediaops --instance=mediaops-db
#   gcloud sql users create mediaops --instance=mediaops-db --password=<pick one>
#
# then add to the --set-env-vars line below:
#   DATABASE_URL=postgresql+psycopg2://mediaops:<password>@/mediaops?host=/cloudsql/${PROJECT_ID}:${REGION}:mediaops-db
# and to the deploy command:
#   --add-cloudsql-instances "${PROJECT_ID}:${REGION}:mediaops-db"
#
# --- Generated output storage ------------------------------------------
# Same ephemeral-filesystem problem applies to backend/outputs/ — a real
# deployment should write generated assets to a GCS bucket instead of
# local disk (swap app/config.OUTPUT_DIR + the StaticFiles mount in
# app/main.py for a GCS-backed equivalent). Not implemented here: doing
# it without being able to test against a real bucket would be guessing,
# not engineering. Documented rather than silently glossed over.
#
# --- Secrets -------------------------------------------------------------
# Put real secrets in Secret Manager, not --set-env-vars:
#   echo -n "sk-or-v1-..." | gcloud secrets create openrouter-api-key --data-file=-
#   echo -n "$(openssl rand -hex 32)" | gcloud secrets create mediaops-api-key --data-file=-
gcloud run deploy "$BACKEND_SERVICE" \
  --image "$IMAGE_BACKEND" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "AUTO_APPROVE_THRESHOLD_CENTS=100,CORS_ORIGINS=*" \
  --set-secrets "OPENROUTER_API_KEY=openrouter-api-key:latest,API_KEY=mediaops-api-key:latest"

BACKEND_URL=$(gcloud run services describe "$BACKEND_SERVICE" --region "$REGION" --format='value(status.url)')
echo "Backend deployed at: $BACKEND_URL"

echo "== Building frontend image via Cloud Build (baking in backend URL) =="
# An *unquoted* heredoc, deliberately: bash expands BACKEND_URL/IMAGE_FRONTEND
# into literal values below before the YAML is ever written, so this doesn't
# need (and doesn't fight with) Cloud Build's own ${_VAR} substitution syntax.
FRONTEND_BUILD_CONFIG="$(mktemp)"
cat > "$FRONTEND_BUILD_CONFIG" <<EOF
steps:
  - name: gcr.io/cloud-builders/docker
    args:
      - build
      - --build-arg
      - VITE_API_BASE_URL=${BACKEND_URL}
      - --build-arg
      - VITE_API_KEY=${MEDIAOPS_API_KEY:-}
      - -t
      - ${IMAGE_FRONTEND}
      - .
images:
  - ${IMAGE_FRONTEND}
EOF
gcloud builds submit frontend --config "$FRONTEND_BUILD_CONFIG"
rm -f "$FRONTEND_BUILD_CONFIG"

echo "== Deploying frontend to Cloud Run =="
gcloud run deploy "$FRONTEND_SERVICE" \
  --image "$IMAGE_FRONTEND" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated

FRONTEND_URL=$(gcloud run services describe "$FRONTEND_SERVICE" --region "$REGION" --format='value(status.url)')
echo ""
echo "Done."
echo "Backend:  $BACKEND_URL"
echo "Frontend: $FRONTEND_URL"
echo ""
echo "CORS_ORIGINS above was set to '*' to get the frontend URL working"
echo "before it existed — tighten it to \"$FRONTEND_URL\" and redeploy the"
echo "backend once you have it, rather than leaving it wide open."
