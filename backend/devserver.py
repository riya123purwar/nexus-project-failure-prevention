"""Dependency-free local preview server. Production API is FastAPI in main.py."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import json, os
from email.parser import BytesParser
from email.policy import default
from backend import main

ROOT=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT/"frontend"),**kwargs)
    def send_json(self,data,status=200):
        raw=json.dumps(data).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.send_header("Access-Control-Allow-Origin","*"); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        p=self.path.split("?")[0]; prefix="/api/projects/"+main.DATA["project"]["id"]
        if p=="/health": return self.send_json({"status":"ok","mode":"demo","version":"0.1.0"})
        if p=="/api/config": return self.send_json({"firebase":{"enabled":False},"mode":"seeded-demo"})
        if p=="/api/projects": return self.send_json([main.DATA["project"]])
        if p==prefix: return self.send_json(main.project_payload())
        if p==prefix+"/graph": return self.send_json({"entities":main.DATA["entities"],"relationships":main.DATA["relationships"]})
        if p==prefix+"/findings": return self.send_json(main.findings())
        if p==prefix+"/schedule": return self.send_json(main.graph_order(main.DATA["activities"])[0])
        if p.startswith(prefix+"/evidence/"):
            evidence_id=p.rsplit("/",1)[-1]
            for source in main.DATA["sources"]:
                for ev in source["evidence"]:
                    if ev["id"]==evidence_id:return self.send_json({"source":source["name"],**ev})
            return self.send_json({"detail":"Evidence not found"},404)
        return super().do_GET()
    def do_POST(self):
        p=self.path.split("?")[0]; prefix="/api/projects/"+main.DATA["project"]["id"]
        size=int(self.headers.get("Content-Length","0")); raw=self.rfile.read(size)
        if p==prefix+"/upload":
            msg=BytesParser(policy=default).parsebytes((f"Content-Type: {self.headers.get('Content-Type','')}\r\nMIME-Version: 1.0\r\n\r\n".encode())+raw)
            for part in msg.iter_parts():
                if part.get_filename():
                    name=part.get_filename(); content=part.get_payload(decode=True) or b""
                    if Path(name).suffix.lower() not in {".txt",".csv"}:return self.send_json({"detail":"Local demo accepts TXT and CSV only."},415)
                    try:text=content.decode("utf-8")
                    except UnicodeDecodeError:return self.send_json({"detail":"File must be UTF-8 text."},422)
                    if len(text)>2_000_000:return self.send_json({"detail":"File exceeds 2 MB demo limit."},413)
                    import uuid
                    if not hasattr(self.server,"uploads"):self.server.uploads={}
                    uid=str(uuid.uuid4()); self.server.uploads[uid]=text
                    return self.send_json({"upload_id":uid,"filename":name,"characters":len(text),"preview":text[:500],"mode":"uploaded source; awaiting Gemini extraction"})
            return self.send_json({"detail":"No file provided."},422)
        try:data=json.loads(raw or b"{}")
        except json.JSONDecodeError:return self.send_json({"detail":"Expected JSON body."},400)
        if p==prefix+"/simulate":
            try:return self.send_json(main.compute_scenario(int(data.get("delay_days",21))))
            except (ValueError,TypeError) as e:return self.send_json({"detail":str(e)},422)
        if p==prefix+"/recover":return self.send_json(main.recoveries())
        if p==prefix+"/ingest":return self.send_json({"detail":"Gemini Vertex AI is not configured in the local preview server; use seeded demo analysis or start FastAPI with cloud credentials."},503)
        return self.send_json({"detail":"Route unavailable in the dependency-free preview; use FastAPI for uploads and cloud ingestion."},501)

if __name__=="__main__":
    port=int(os.getenv("PORT","18765")); print(f"NEXUS local demo: http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1",port),Handler).serve_forever()
