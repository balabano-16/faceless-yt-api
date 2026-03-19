from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid
import asyncio
from src.pipeline import VideoPipeline
from src.store import job_store

app = FastAPI(title="Faceless YouTube API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoRequest(BaseModel):
    topic: str
    sections: int = 5
    voice_id: Optional[str] = "pNInz6obpgDQGcFmaJgB"  # ElevenLabs Adam voice
    style: Optional[str] = "cinematic, realistic, dramatic"
    language: Optional[str] = "tr"  # tr veya en

class JobStatus(BaseModel):
    job_id: str
    status: str  # queued, generating_script, generating_assets, assembling, done, error
    progress: int  # 0-100
    message: str
    video_url: Optional[str] = None
    error: Optional[str] = None

@app.post("/generate", response_model=JobStatus)
async def generate_video(req: VideoRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    job_store[job_id] = {
        "status": "queued",
        "progress": 0,
        "message": "Kuyrukta bekleniyor...",
        "video_url": None,
        "error": None
    }
    pipeline = VideoPipeline(job_id)
    background_tasks.add_task(pipeline.run, req)
    return JobStatus(job_id=job_id, **job_store[job_id])

@app.get("/status/{job_id}", response_model=JobStatus)
async def get_status(job_id: str):
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job bulunamadı")
    return JobStatus(job_id=job_id, **job_store[job_id])

@app.get("/health")
async def health():
    return {"status": "ok"}
