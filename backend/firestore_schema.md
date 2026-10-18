# Firestore schema

```text
users/{uid}/projects/{projectId}             project metadata
projects/{projectId}/sources/{sourceId}      source metadata and evidence excerpts
projects/{projectId}/entities/{entityId}    typed facts and provenance
projects/{projectId}/relationships/{edgeId} typed, evidenced graph edges
projects/{projectId}/findings/{findingId}   findings with confidence and evidence IDs
projects/{projectId}/schedules/{scheduleId}  schedule snapshots (reserved)
```

Seeded entity IDs are stable. Extracted entity IDs are deterministic UUID5 values derived from type and normalized name. Each child record stores `owner_uid`. The API verifies Firebase ID tokens before upload and ingestion when `FIREBASE_PROJECT_ID` is configured. Firestore access uses the Cloud Run service identity; browser clients do not receive service credentials. The local seeded project is read-only without an account.

The extracted JSON is validated with Pydantic. Confidence must be in `[0,1]`; relationship types are allow-listed; endpoints must resolve to seeded or extracted entity names. Extracted records retain evidence excerpts and upload source IDs. Uploaded source files are held in process memory only; configure a Cloud Storage adapter before durable source retention.
