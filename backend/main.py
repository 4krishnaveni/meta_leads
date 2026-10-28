import os
import hmac
import hashlib
import asyncio
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
APP_SECRET = os.getenv("APP_SECRET")
PAGE_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
GRAPH = "https://graph.facebook.com/v26.0"  # use the current Graph API version

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=[
                   "*"], allow_methods=["*"], allow_headers=["*"])

leads: list[dict] = []          # in-memory store (see assumptions)
seen_ids: set[str] = set()      # dedupe, Meta can retry webhooks


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        for ws in list(self.active):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(ws)


manager = ConnectionManager()


@app.get("/webhook")
async def verify(request: Request):
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(p.get("hub.challenge"))
    raise HTTPException(status_code=403, detail="Verification failed")


def valid_signature(raw: bytes, header: str | None) -> bool:
    if not header or not APP_SECRET:
        return False
    expected = "sha256=" + \
        hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


async def fetch_and_broadcast(leadgen_id: str):
    if leadgen_id in seen_ids:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{GRAPH}/{leadgen_id}", params={"access_token": PAGE_TOKEN})
    if r.status_code != 200:
        print("Graph API error:", r.text)
        return
    data = r.json()
    fields = {f["name"]: ", ".join(f.get("values", []))
              for f in data.get("field_data", [])}
    lead = {
        "id": data["id"],
        "created_time": data.get("created_time"),
        "form_id": data.get("form_id"),
        "fields": fields,
    }
    seen_ids.add(leadgen_id)
    leads.insert(0, lead)
    await manager.broadcast({"type": "new_lead", "lead": lead})


@app.post("/webhook")
async def receive(request: Request):
    raw = await request.body()
    if not valid_signature(raw, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=403, detail="Bad signature")
    payload = await request.json()
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "leadgen":
                leadgen_id = change["value"]["leadgen_id"]
                asyncio.create_task(fetch_and_broadcast(leadgen_id))
    # respond fast, do the work in the background
    return {"status": "ok"}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    # existing leads on connect
    await ws.send_json({"type": "snapshot", "leads": leads})
    try:
        while True:
            await ws.receive_text()  # keep connection open
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ---------- Debug helper: fake a lead without Meta (for local testing only) ----------
@app.post("/debug/fake-lead")
async def fake_lead():
    import time
    lead = {"id": str(time.time()), "created_time": "now", "form_id": "debug",
            "fields": {"full_name": "Test User", "email": "test@example.com", "phone_number": "9999999999"}}
    leads.insert(0, lead)
    await manager.broadcast({"type": "new_lead", "lead": lead})
    return lead
