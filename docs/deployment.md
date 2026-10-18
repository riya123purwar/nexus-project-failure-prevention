# Deployment guide

## Google Cloud setup

1. Create a Google Cloud project and enable billing.
2. Enable Cloud Run, Artifact Registry, Firestore, Vertex AI and Cloud Build APIs.
3. Create a Firestore Native mode database and deploy `firestore.rules`.
4. Enable Email/Password in Firebase Authentication; add the deployed Cloud Run origin to authorized domains. Set the Firebase web app configuration in Cloud Run environment variables.
5. Grant the Cloud Run runtime service account `roles/datastore.user` and `roles/aiplatform.user`. Grant Storage permissions only if a Cloud Storage upload adapter is added.
6. Set `FIREBASE_PROJECT_ID`, `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` and `GOOGLE_GENAI_USE_VERTEXAI=true`.

## Build and deploy

Set `PROJECT_ID`, `REGION`, `FIREBASE_API_KEY` and `FIREBASE_AUTH_DOMAIN`, then run:

```sh
gcloud config set project "$PROJECT_ID"
gcloud builds submit --tag "$REGION-docker.pkg.dev/$PROJECT_ID/nexus/nexus:latest"
gcloud run deploy nexus \
  --image "$REGION-docker.pkg.dev/$PROJECT_ID/nexus/nexus:latest" \
  --region "$REGION" --allow-unauthenticated \
  --service-account "nexus-runtime@$PROJECT_ID.iam.gserviceaccount.com" \
  --set-env-vars "FIREBASE_PROJECT_ID=$PROJECT_ID,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION,GOOGLE_GENAI_USE_VERTEXAI=true,FIREBASE_API_KEY=$FIREBASE_API_KEY,FIREBASE_AUTH_DOMAIN=$FIREBASE_AUTH_DOMAIN"
```

Never put a service-account key in the image. Cloud Run uses its service identity and Application Default Credentials. Verify `/health`, sign in with a Firebase test user, then test a text upload. These are deployment instructions; this repository has not been deployed.

## Local runs

Dependency-free seeded preview:

```sh
python -m backend.devserver
```

Open `http://localhost:18765`.

Full FastAPI service:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8080
```

Without cloud variables the seeded project, deterministic simulation and recovery comparison work locally. Gemini extraction returns 503 until Vertex AI is configured. Firebase Auth and Firestore require a Firebase project and ADC credentials. Uploaded sources are not durably stored in Cloud Storage.
