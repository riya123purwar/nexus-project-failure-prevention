"""Optional Google Cloud adapters. Never reports a live integration without a successful client call."""
from __future__ import annotations
import os
from typing import Any

def verify_firebase_id_token(token: str) -> dict[str, Any]:
    try:
        import firebase_admin
        from firebase_admin import auth
        if not firebase_admin._apps:
            firebase_admin.initialize_app(options={"projectId": os.environ["FIREBASE_PROJECT_ID"]})
        return auth.verify_id_token(token, check_revoked=True)
    except Exception as exc:
        raise RuntimeError(f"Firebase token verification failed: {exc}") from exc

def firestore_client():
    from google.cloud import firestore
    return firestore.Client(project=os.environ["FIREBASE_PROJECT_ID"])

def persist_project(project: dict[str, Any], owner_uid: str) -> None:
    """Write project-scoped records separately; caller must authenticate owner_uid."""
    db=firestore_client(); pid=project["project"]["id"]
    db.collection("users").document(owner_uid).collection("projects").document(pid).set(project["project"])
    for collection,key in (("sources","id"),("entities","id"),("relationships",None),("findings","id"),("schedules","id")):
        for i,item in enumerate(project.get(collection, [])):
            docid=item.get(key) if key else f"{item.get('source','')}-{item.get('target','')}-{item.get('type','')}-{i}"
            db.collection("projects").document(pid).collection(collection).document(str(docid)).set({**item,"owner_uid":owner_uid})

def load_user_project(project_id: str, owner_uid: str) -> dict[str, Any] | None:
    db=firestore_client(); ref=db.collection("users").document(owner_uid).collection("projects").document(project_id)
    snapshot=ref.get()
    if not snapshot.exists:return None
    result={"project":snapshot.to_dict(),"id":project_id}
    for collection in ("sources","entities","relationships","findings","schedules"):
        result[collection]=[doc.to_dict() for doc in db.collection("projects").document(project_id).collection(collection).where("owner_uid","==",owner_uid).stream()]
    return result

def extract_with_gemini(text: str) -> dict[str, Any]:
    """Use Vertex AI Gemini structured JSON output; caller validates response before persistence."""
    from google import genai
    from google.genai import types
    client=genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"], location=os.getenv("GOOGLE_CLOUD_LOCATION","us-central1"))
    schema={"type":"OBJECT","properties":{"entities":{"type":"ARRAY","items":{"type":"OBJECT","properties":{"type":{"type":"STRING"},"name":{"type":"STRING"},"description":{"type":"STRING"},"evidence_excerpt":{"type":"STRING"},"confidence":{"type":"NUMBER"}},"required":["type","name","description","evidence_excerpt","confidence"]}},"relationships":{"type":"ARRAY","items":{"type":"OBJECT","properties":{"source_name":{"type":"STRING"},"target_name":{"type":"STRING"},"type":{"type":"STRING"},"evidence_excerpt":{"type":"STRING"},"confidence":{"type":"NUMBER"}},"required":["source_name","target_name","type","evidence_excerpt","confidence"]}}},"required":["entities","relationships"]}
    response=client.models.generate_content(model=os.getenv("GEMINI_MODEL","gemini-2.5-flash"),contents="Extract only facts supported by this text. Do not infer a relationship without explicit evidence. Preserve short verbatim evidence excerpts.\n\n"+text,config=types.GenerateContentConfig(response_mime_type="application/json",response_schema=schema,temperature=0))
    import json
    if not response.text: raise RuntimeError("Gemini returned an empty response")
    return json.loads(response.text)
