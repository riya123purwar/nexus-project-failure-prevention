# NEXUS — The Project Failure Prevention Engine

**One change. Hundreds of possible consequences. Find them before they happen.**

NEXUS builds an evidence-linked project model and calculates downstream schedule effects when conditions change. It surfaces contradictions and unverified assumptions, traces dependencies, and compares hypothetical recovery options. The AETHER EV data is synthetic.

## Run the demo

```sh
python -m backend.devserver
```

Open `http://localhost:18765`. The seeded UI includes Project DNA, five evidence-linked blindspots, a three-week battery delay simulation, a critical-path schedule, conditional recovery options and source excerpt inspection. Scenarios never modify the baseline. This dependency-free preview accepts source upload metadata but cannot run Gemini extraction.

For FastAPI upload support, install `requirements.txt` and run `uvicorn backend.main:app --reload --port 8080`. Configure Google Cloud ADC and Firebase web app settings to enable cloud features. Never commit credentials.

## Implemented

- Deterministic finish-to-start dependency propagation and critical path with earliest/latest dates, slack, cycle and missing-edge validation.
- FastAPI project, graph, findings, evidence, schedule, simulation, recovery, upload and Vertex Gemini extraction routes.
- Provenance excerpts, source IDs, confidence and extraction state on seeded facts and findings.
- Optional Firebase email/password sign-in and ID-token verification, with user-scoped Firestore reads/writes when configured.
- Responsive browser UI served by the API; local demo mode needs no credentials.

Recovery options are hypothetical duration changes. They are marked conditional because the seed does not confirm staffing, lab availability or alternate-source qualification. No actual project plan is modified.

## API

`GET /health`, `GET /api/projects`, `GET /api/projects/{id}`, `GET /api/projects/{id}/graph`, `GET /api/projects/{id}/findings`, `GET /api/projects/{id}/schedule`, `GET /api/projects/{id}/evidence/{evidence_id}`, `POST /api/projects/{id}/upload`, `POST /api/projects/{id}/ingest`, `POST /api/projects/{id}/simulate`, `POST /api/projects/{id}/recover`.

See `docs/deployment.md`, `backend/firestore_schema.md`, `demo_data/README.md` and `architecture.mmd`. TXT / CSV source samples are in `demo_data/sources/`. Uploaded files are not retained in Cloud Storage.

## Cloud status

Code adapters are included for Firebase Authentication token verification, Firestore persistence/readback, Vertex AI Gemini structured extraction and Cloud Run hosting. These require credentials and were not connected or deployed in this workspace. No deployment is claimed.

## Tests

```sh
python -m unittest discover -s tests -v
```

The test data has known synthetic outcomes. No accuracy, productivity gain or real-world performance claim is made.

## Submission links

- Public GitHub repository: **https://github.com/riya123purwar/nexus-project-failure-prevention**

The technical documentation and deployment guidance are included in this repository.
