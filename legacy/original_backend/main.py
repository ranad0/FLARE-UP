from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.catalog import investigations_catalog
from app.config import ALLOWED_ORIGINS, GROQ_API_KEY
from app.rag import ask_flare_up
from app.retrieval import search_text
from app.router import route_question
from app.scenario import closest_scenario_matches, evidence_level, visual_state
from app.structured_data import search_structured, structured_stats
from app.vector_store import index_stats

app = FastAPI(
    title="FLARE UP SI",
    version="1.0.0",
    description="Evidence-grounded hybrid intelligence for NASA microgravity combustion research.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2500)


class ScenarioRequest(BaseModel):
    gravity: str = Field(default="microgravity", pattern="^(earth|microgravity)$")
    oxygen_percent: float = Field(default=21.0, ge=15.0, le=40.0)
    pressure_psi: float = Field(default=14.7, ge=4.3, le=14.7)
    airflow: float = Field(default=0.5, ge=0.0, le=3.0)
    airflow_direction_degrees: float = Field(default=0.0, ge=0.0, le=360.0)
    sample_type: str = Field(default="liquid fuel")


@app.get("/")
def root():
    return {
        "name": "FLARE UP SI",
        "status": "running",
        "version": "1.0.0",
        "capabilities": ["text", "structured", "hybrid", "scenario"],
    }


@app.get("/health")
def health():
    try:
        vector = index_stats()
        structured = structured_stats()
        return {
            "status": "ok",
            "vector_index": vector,
            "structured_records": structured["record_count"],
            "groq_configured": bool(GROQ_API_KEY and not GROQ_API_KEY.startswith("gsk_your")),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/stats")
def stats():
    return {
        "vector": index_stats(),
        "structured": structured_stats(),
        "investigations": investigations_catalog(),
    }


@app.get("/investigations")
def investigations():
    return {"investigations": investigations_catalog()}


@app.post("/route")
def route(request: AskRequest):
    return {"question": request.question, **route_question(request.question)}


@app.post("/search")
def search(request: AskRequest):
    try:
        return {"question": request.question, "results": search_text(request.question)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/structured-search")
def structured_search(request: AskRequest):
    try:
        return search_structured(request.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/ask")
def ask(request: AskRequest):
    try:
        return ask_flare_up(request.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/scenario/analyze")
def analyze_scenario(request: ScenarioRequest):
    matches = closest_scenario_matches(
        oxygen_percent=request.oxygen_percent,
        pressure_psi=request.pressure_psi,
        gravity=request.gravity,
        sample_type=request.sample_type,
    )
    level = evidence_level(matches, request.sample_type)
    question = (
        f"For a {request.gravity} fire scenario with {request.oxygen_percent:.1f}% oxygen, "
        f"{request.pressure_psi:.1f} psi pressure, airflow level {request.airflow:.1f}, "
        f"and sample type {request.sample_type}, what NASA evidence is closest, "
        "what trends are directly supported, and what is not established?"
    )
    rag = ask_flare_up(question)
    return {
        "scenario": request.model_dump(),
        "evidence_match": level,
        "closest_records": matches,
        "visual_state": visual_state(
            gravity=request.gravity,
            oxygen_percent=request.oxygen_percent,
            pressure_psi=request.pressure_psi,
            airflow=request.airflow,
            material=request.sample_type,
        ),
        "question": question,
        "analysis": rag,
        "scientific_disclaimer": "Evidence-informed visualization — not a numerical combustion simulation.",
    }
