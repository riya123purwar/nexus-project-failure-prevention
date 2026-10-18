"""NEXUS deterministic demo API. Local mode is self-contained and uses seeded data."""
from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path
from typing import Any
import json, os

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "demo_data" / "aether_ev.json").read_text())
RELATIONSHIP_TYPES={"depends_on","blocks","implements","requires","contradicts","supersedes","supported_by","scheduled_before","impacts"}

def validate_extraction_links(extraction:dict[str,Any]) -> None:
    """Reject unsupported links and dangling endpoints after structured schema validation."""
    names={str(e.get("name","")).strip().casefold() for e in extraction.get("entities",[])}
    names.update(e["name"].strip().casefold() for e in DATA["entities"])
    for edge in extraction.get("relationships",[]):
        if edge.get("type") not in RELATIONSHIP_TYPES: raise ValueError(f"Unsupported relationship type: {edge.get('type')}")
        for field in ("source_name","target_name"):
            if edge.get(field,"").strip().casefold() not in names: raise ValueError(f"Unresolved relationship {field}: {edge.get(field)}")
        if not 0 <= float(edge.get("confidence",-1)) <= 1: raise ValueError("Relationship confidence must be between 0 and 1")

def graph_order(activities: list[dict], extra_delay: dict[str, int] | None = None):
    by_id = {a["id"]: a for a in activities}
    indegree = {k: 0 for k in by_id}; children = {k: [] for k in by_id}
    for a in activities:
        for p in a.get("depends_on", []):
            if p not in by_id: raise ValueError(f"Unknown prerequisite {p} for {a['id']}")
            children[p].append(a["id"]); indegree[a["id"]] += 1
    ready = sorted(k for k,v in indegree.items() if not v); order=[]
    while ready:
        n=ready.pop(0); order.append(n)
        for c in children[n]:
            indegree[c]-=1
            if indegree[c]==0: ready.append(c); ready.sort()
    if len(order) != len(by_id): raise ValueError("Dependency cycle detected; schedule cannot be calculated")
    starts={}; finishes={}; parent={}
    for key in order:
        a=by_id[key]; preds=a.get("depends_on", [])
        p=max(preds, key=lambda x: finishes[x]) if preds else None
        starts[key]=finishes[p] if p else 0; parent[key]=p
        finishes[key]=starts[key]+a["duration_days"]+(extra_delay or {}).get(key,0)
    end=max(finishes.values()); latest_finish={k:end for k in by_id}; latest_start={}
    for k in reversed(order):
        if children[k]: latest_finish[k]=min(latest_start[c] for c in children[k])
        latest_start[k]=latest_finish[k]-by_id[k]["duration_days"]-(extra_delay or {}).get(k,0)
    rows=[]
    for k in order:
        a=by_id[k]; rows.append({**a,"earliest_start_day":starts[k],"earliest_finish_day":finishes[k],"latest_start_day":latest_start[k],"latest_finish_day":latest_finish[k],"slack_days":latest_start[k]-starts[k],"critical":latest_start[k]==starts[k]})
    return rows, end, parent, children

def compute_scenario(delay_days: int = 21):
    if delay_days < 0 or delay_days > 180: raise ValueError("Delay must be between 0 and 180 days")
    acts=DATA["activities"]; base,base_end,_,_=graph_order(acts)
    delayed,delay_end,parent,children=graph_order(acts,{"battery_arrival":delay_days})
    base_date=date.fromisoformat(DATA["project"]["start_date"])
    changed={r["id"]:r for r in delayed}; original={r["id"]:r for r in base}
    impacted=[r for r in delayed if r["earliest_start_day"]>original[r["id"]]["earliest_start_day"] or r["id"]=="battery_arrival"]
    chain=[]; cur="battery_arrival"
    while cur:
        chain.append(cur); nexts=[x for x in children[cur] if changed[x]["earliest_start_day"]>=changed[cur]["earliest_finish_day"]]
        cur=nexts[0] if nexts else None
    return {"delay_days":delay_days,"baseline_finish":(base_date+timedelta(days=base_end)).isoformat(),"scenario_finish":(base_date+timedelta(days=delay_end)).isoformat(),"baseline_duration_days":base_end,"scenario_duration_days":delay_end,"net_impact_days":delay_end-base_end,"activities":delayed,"baseline_activities":base,"directly_affected":[x for x in impacted if x["id"]=="battery_arrival"],"indirectly_affected":[x for x in impacted if x["id"]!="battery_arrival"],"causal_chain":chain,"assumptions":["Dependencies are finish-to-start.","No resource calendars or workday exclusions are modelled.","Durations are synthetic planning estimates; dates are scenario outputs, not commitments."]}

def findings():
    """Evaluate deterministic blindspot rules over the seeded graph; absence stays labeled unverified."""
    entities={e["id"]:e for e in DATA["entities"]}; rel=DATA["relationships"]
    relset={(r["source"],r["target"],r["type"]) for r in rel}
    found=[]
    if ("week12-proposal" in entities and "week14-plan" in entities and
        ("week12-proposal","week14-plan","contradicts") in relset):
        found.append(DATA["findings"][0])
    if entities.get("thermal-slot",{}).get("status")=="unverified": found.append(DATA["findings"][1])
    if entities.get("alternate-supplier",{}).get("status")=="unsupported": found.append(DATA["findings"][2])
    # An unapproved test-date change without a verified readiness relation is a missing gate.
    if entities.get("week12-proposal",{}).get("status")=="extracted_unapproved" and not any(
        a=="week12-proposal" and t in {"supported_by","requires"} for a,_,t in relset):
        found.append(DATA["findings"][3])
    # Charging requirement has evidence but no activity-level verification link.
    has_charge_test=any("charge" in (entities.get(a,{}).get("name","")+" "+entities.get(b,{}).get("name","")).lower()
                        and entities.get(a,{}).get("type")=="activity" for a,b,_ in relset)
    if "req-charge" in entities and not has_charge_test: found.append(DATA["findings"][4])
    return found

def recoveries():
    base=compute_scenario(21); out=[]
    options=[("A","Expedite battery pack testing",{"battery_test":-4},"Conditional: a second qualified test shift is not confirmed in the source data."),("B","Overlap final-test preparation",{"final_vehicle_test":-3},"Conditional: the documentation owner and safety approval are unconfirmed."),("C","Use alternate battery supplier",{},"Not supported: no qualified alternate supplier or interface evidence is recorded.")]
    for code,name,adjust,prereq in options:
        valid=code!="C"
        acts=[dict(a) for a in DATA["activities"]]
        if valid:
            # Compress duration only in the hypothetical strategy; never change project data.
            for a in acts:
                if a["id"] in adjust: a["duration_days"]=max(1,a["duration_days"]+adjust[a["id"]])
            rows,end,_,_=graph_order(acts,{"battery_arrival":21})
            finish=(date.fromisoformat(DATA["project"]["start_date"])+timedelta(days=end)).isoformat()
            recovered=max(0,base["scenario_duration_days"]-end)
        else: rows=base["activities"]; finish=base["scenario_finish"]; recovered=0
        out.append({"id":code,"name":name,"feasible":False,"status":"conditional" if valid else "not supported by project data","projected_finish":finish,"days_recovered_vs_delay":recovered,"prerequisites":prereq,"risks":"Illustrative duration change only; validate resources, safety and scope before adoption." if valid else "Supplier qualification, safety evidence and interface validation are absent.","activities":[r["id"] for r in rows if r.get("critical")]})
    return {"baseline_finish":base["baseline_finish"],"delayed_finish":base["scenario_finish"],"options":out}

def project_payload():
    return {**DATA,"findings":findings(),"mode":"SEEDED DEMO · deterministic engine","integrations":{"firebase_auth":bool(os.getenv("FIREBASE_PROJECT_ID")),"firestore":bool(os.getenv("FIREBASE_PROJECT_ID")),"gemini":bool(os.getenv("GOOGLE_CLOUD_PROJECT") and os.getenv("GOOGLE_GENAI_USE_VERTEXAI")),"cloud_run":bool(os.getenv("K_SERVICE"))}}

try:
    from fastapi import FastAPI, HTTPException, Header, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
    app=FastAPI(title="NEXUS",version="0.1.0")
    app.add_middleware(CORSMiddleware,allow_origins=os.getenv("CORS_ORIGINS","*").split(","),allow_methods=["*"],allow_headers=["*"])
    class SimulationRequest(BaseModel): delay_days:int=Field(default=21,ge=0,le=180)
    class ExtractedEntity(BaseModel): type:str; name:str; description:str; evidence_excerpt:str; confidence:float=Field(ge=0,le=1)
    class ExtractedRelationship(BaseModel): source_name:str; target_name:str; type:str; evidence_excerpt:str; confidence:float=Field(ge=0,le=1)
    class Extraction(BaseModel): entities:list[ExtractedEntity]; relationships:list[ExtractedRelationship]
    UPLOADS:dict[str,dict[str,str]]={}
    def owner_from_auth(authorization:str|None):
        if not os.getenv("FIREBASE_PROJECT_ID"): return None
        if not authorization or not authorization.startswith("Bearer "): raise HTTPException(401,"Firebase ID token required")
        try:
            from backend.integrations import verify_firebase_id_token
            return verify_firebase_id_token(authorization[7:])["uid"]
        except Exception as e: raise HTTPException(401,str(e))
    @app.get("/health")
    def health(): return {"status":"ok","mode":"demo","version":"0.1.0"}
    @app.get("/api/config")
    def public_config():
        return {"firebase":{"enabled":bool(os.getenv("FIREBASE_PROJECT_ID") and os.getenv("FIREBASE_API_KEY")),"apiKey":os.getenv("FIREBASE_API_KEY"),"authDomain":os.getenv("FIREBASE_AUTH_DOMAIN"),"projectId":os.getenv("FIREBASE_PROJECT_ID")},"mode":"seeded-demo"}
    @app.get("/api/projects")
    def projects(): return [{"id":DATA["project"]["id"],"name":DATA["project"]["name"]}]
    @app.get("/api/projects/{project_id}")
    def project(project_id:str,authorization:str|None=Header(default=None)):
        if project_id!=DATA["project"]["id"]: raise HTTPException(404,"Project not found")
        owner=owner_from_auth(authorization) if authorization else None
        if owner:
            try:
                from backend.integrations import load_user_project
                saved=load_user_project(project_id,owner)
                if saved: return {**project_payload(),**saved,"mode":"FIRESTORE PROJECT · deterministic engine"}
            except Exception as e: raise HTTPException(503,f"Firestore read failed: {e}")
        return project_payload()
    @app.get("/api/projects/{project_id}/graph")
    def graph(project_id:str):
        if project_id!=DATA["project"]["id"]: raise HTTPException(404,"Project not found")
        return {"entities":DATA["entities"],"relationships":DATA["relationships"]}
    @app.get("/api/projects/{project_id}/findings")
    def get_findings(project_id:str):
        if project_id!=DATA["project"]["id"]: raise HTTPException(404,"Project not found")
        return findings()
    @app.post("/api/projects/{project_id}/simulate")
    def simulate(project_id:str,req:SimulationRequest):
        if project_id!=DATA["project"]["id"]: raise HTTPException(404,"Project not found")
        try:return compute_scenario(req.delay_days)
        except ValueError as e:raise HTTPException(422,str(e))
    @app.post("/api/projects/{project_id}/recover")
    def recover(project_id:str):
        if project_id!=DATA["project"]["id"]: raise HTTPException(404,"Project not found")
        return recoveries()
    @app.get("/api/projects/{project_id}/schedule")
    def schedule(project_id:str):
        if project_id!=DATA["project"]["id"]: raise HTTPException(404,"Project not found")
        return graph_order(DATA["activities"])[0]
    @app.get("/api/projects/{project_id}/evidence/{evidence_id}")
    def evidence(project_id:str,evidence_id:str):
        if project_id!=DATA["project"]["id"]: raise HTTPException(404,"Project not found")
        for s in DATA["sources"]:
            for e in s["evidence"]:
                if e["id"]==evidence_id:return {"source":s["name"],**e}
        raise HTTPException(404,"Evidence not found")
    @app.post("/api/projects/{project_id}/upload")
    async def upload(project_id:str,request:Request,authorization:str|None=Header(default=None)):
        if project_id!=DATA["project"]["id"]: raise HTTPException(404,"Project not found")
        owner=owner_from_auth(authorization)
        if int(request.headers.get("content-length","0"))>2_100_000: raise HTTPException(413,"File exceeds 2 MB demo limit")
        from email.parser import BytesParser
        from email.policy import default
        content_type=request.headers.get("content-type","")
        msg=BytesParser(policy=default).parsebytes((f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode())+await request.body())
        part=next((p for p in msg.iter_parts() if p.get_filename()),None)
        if part is None: raise HTTPException(422,"No source file was provided")
        filename=part.get_filename()
        suffix=Path(filename or "").suffix.lower()
        if suffix not in {".txt",".csv"}: raise HTTPException(415,"Local ingestion currently accepts TXT and CSV files.")
        raw=part.get_payload(decode=True) or b""
        if len(raw)>=2_000_000: raise HTTPException(413,"File exceeds 2 MB demo limit")
        try: content=raw.decode("utf-8")
        except UnicodeDecodeError: raise HTTPException(422,"File must be UTF-8 text")
        if len(content.strip())<20: raise HTTPException(422,"File contains too little text to analyze")
        import uuid
        upload_id=str(uuid.uuid4()); UPLOADS[upload_id]={"filename":filename or "source.txt","text":content,"owner_uid":owner or ""}
        return {"upload_id":upload_id,"filename":filename,"characters":len(content),"preview":content[:500],"mode":"uploaded source; awaiting Gemini extraction"}
    @app.post("/api/projects/{project_id}/ingest")
    async def ingest(project_id:str,body:dict[str,str],authorization:str|None=Header(default=None)):
        if project_id!=DATA["project"]["id"]: raise HTTPException(404,"Project not found")
        owner=owner_from_auth(authorization)
        if not os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GOOGLE_GENAI_USE_VERTEXAI","true").lower()!="true":
            raise HTTPException(503,"Gemini Vertex AI is not configured; seeded demo analysis remains available.")
        source=UPLOADS.get(body.get("upload_id",""),{})
        owner=owner or (source.get("owner_uid") if source else None)
        content=body.get("text","") or source.get("text","")
        if not content or len(content)>100_000: raise HTTPException(422,"Provide source text between 1 and 100,000 characters")
        try:
            from backend.integrations import extract_with_gemini, persist_project
            parsed=Extraction.model_validate(extract_with_gemini(content))
            result=parsed.model_dump()
            validate_extraction_links(result)
            extracted={**DATA,"sources":[*DATA["sources"],{"id":body.get("upload_id"),"name":source.get("filename","Uploaded source"),"type":"uploaded text","evidence":[]}],"entities":list(DATA["entities"]),"relationships":list(DATA["relationships"]),"extraction":result}
            name_to_id={e["name"].casefold():e["id"] for e in extracted["entities"]}
            import uuid
            for i,item in enumerate(result["entities"]):
                evidence_id=f"upload-e-{i}"; extracted["sources"][-1]["evidence"].append({"id":evidence_id,"location":"uploaded text","excerpt":item["evidence_excerpt"]})
                entity_id="gem-"+uuid.uuid5(uuid.NAMESPACE_URL,item["type"]+":"+item["name"].casefold()).hex[:16]
                extracted["entities"].append({"id":entity_id,"type":item["type"],"name":item["name"],"description":item["description"],"status":"extracted","confidence":item["confidence"],"source":body.get("upload_id"),"evidence":evidence_id}); name_to_id[item["name"].casefold()]=entity_id
            for i,item in enumerate(result["relationships"]):
                source_id=name_to_id.get(item["source_name"].casefold()); target_id=name_to_id.get(item["target_name"].casefold())
                if not source_id or not target_id: raise HTTPException(422,"Relationship endpoint must match an extracted or seeded entity name")
                evidence_id=f"upload-r-{i}"; extracted["sources"][-1]["evidence"].append({"id":evidence_id,"location":"uploaded text","excerpt":item["evidence_excerpt"]})
                extracted["relationships"].append({"source":source_id,"target":target_id,"type":item["type"],"status":"extracted","confidence":item["confidence"],"evidence":evidence_id})
            if owner: persist_project(extracted,owner)
            return {"mode":"vertex-gemini","extraction":result,"persisted_to_firestore":bool(owner)}
        except HTTPException: raise
        except Exception as e: raise HTTPException(502,f"Ingestion failed validation or cloud processing: {e}")
    try: app.mount("/",StaticFiles(directory=ROOT/"frontend",html=True),name="frontend")
    except RuntimeError: pass
except ImportError:
    app=None

if __name__=="__main__":
    import uvicorn
    uvicorn.run("backend.main:app",host="0.0.0.0",port=int(os.getenv("PORT","8080")))
