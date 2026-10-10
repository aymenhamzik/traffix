"""
Backend API for the React frontend. The frontend only talks to this server,
which reads from the supermaster's live run; it never reaches the masters or SUMO.

  GET  /api/scenarios                       list of scenarios
  POST /api/start?scenario=rain&speed=4     start a live run
  POST /api/stop
  GET  /api/state                           full live snapshot
  GET  /api/network                         map geometry
  GET  /api/notifications?persona=bus_driver
  GET  /api/decisions?limit=200&q=ambulance
  POST /api/ask  {"question": "..."}        explainer agent (Synapse)
  GET  /api/results                         experiment summary (if available)
  GET  /api/models                          training metrics
"""
import json
import os

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..agents.network.explainer import ExplainerAgent
from ..core import config
from .live import LiveRun

app = FastAPI(title="TraffiX API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
RUN = {"live": None}


class Question(BaseModel):
    question: str


def live():
    if RUN["live"] is None:
        raise HTTPException(409, "No live run. POST /api/start first.")
    return RUN["live"]


@app.get("/api/scenarios")
def scenarios():
    return [{"id": k, "start": v["start"], "description": v.get("description", ""),
             "events": list((v.get("events") or {}).keys())} for k, v in config.scenarios().items()]


@app.post("/api/start")
def start(scenario: str = "morning_peak", speed: float = 4.0, seed: int = 1):
    if scenario not in config.scenarios():
        raise HTTPException(404, f"Unknown scenario {scenario}")
    if RUN["live"]:
        RUN["live"].stop()
    RUN["live"] = LiveRun(scenario, seed, speed)
    RUN["live"].start()
    return {"started": scenario, "speed": speed}


@app.post("/api/stop")
def stop():
    if RUN["live"]:
        RUN["live"].stop()
    return {"stopped": True}


@app.get("/api/state")
def state():
    return live().state() if RUN["live"] else {"status": "idle"}


@app.get("/api/network")
def network():
    return live().geometry


@app.get("/api/notifications")
def notifications(persona: str = "operator", limit: int = 50):
    items = [n for n in live().state().get("notifications", []) if n["persona"] == persona]
    return items[-limit:][::-1]


@app.get("/api/decisions")
def decisions(limit: int = 200, q: str = ""):
    entries = live().log.entries
    if q:
        entries = [e for e in entries if q.lower() in json.dumps(e).lower()]
    return entries[-limit:][::-1]


@app.post("/api/ask")
def ask(body: Question):
    return ExplainerAgent(list(live().log.entries)).ask(body.question)


@app.get("/api/results")
def results():
    p = config.path("results", "summary_by_persona.csv")
    return pd.read_csv(p).to_dict("records") if os.path.exists(p) else []


@app.get("/api/models")
def models():
    p = config.path("models", "metrics.json")
    return json.load(open(p)) if os.path.exists(p) else {}


dist = config.path("frontend", "dist")
if os.path.isdir(dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist, "assets")), name="assets")

    @app.get("/{page:path}")
    def spa(page: str):
        """Any non-API path returns the React app, which handles the routing."""
        return FileResponse(os.path.join(dist, "index.html"))
