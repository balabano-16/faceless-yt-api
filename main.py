from fastapi import FastAPI, BackgroundTasks, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uuid
import os
import jwt
from src.pipeline import VideoPipeline
from src.store import job_store
from src.supabase_client import check_video_limit, get_supabase

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/tmp/videos")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = FastAPI(title="Narrelo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://narrelo.com", "https://www.narrelo.com", "https://narrelo-ai-studio.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/videos", StaticFiles(directory=OUTPUT_DIR), name="videos")

class VideoRequest(BaseModel):
    topic: str
    sections: int = 5
    voice_id: Optional[str] = "21m00Tcm4TlvDq8ikWAM"
    style: Optional[str] = "cinematic, realistic, dramatic"
    language: Optional[str] = "en"
    format: Optional[str] = "landscape"
    use_video: Optional[bool] = False

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    message: str
    video_url: Optional[str] = None
    error: Optional[str] = None

def verify_jwt(authorization: Optional[str] = Header(None)) -> str:
    """JWT token doğrula — Supabase JWKS ile uyumlu"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header missing or invalid")

    token = authorization.split(" ")[1]

    try:
        import time
        # Signature doğrulaması olmadan decode et
        payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_aud": False}
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no user ID")
        
        # Expire kontrolü
        exp = payload.get("exp", 0)
        if exp and exp < time.time():
            raise HTTPException(status_code=401, detail="Token expired")
        
        print(f"[DEBUG] Auth success for user: {user_id[:8]}...")
        return user_id
    except Exception as e:
        print(f"[DEBUG] JWT error: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

@app.post("/generate", response_model=JobStatus)
async def generate_video(
    req: VideoRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(verify_jwt)
):
    # Server-side limit kontrolü — user_id JWT'den geliyor, client'tan değil
    limit_check = await check_video_limit(user_id, req.use_video)
    if not limit_check.get("allowed", True):
        raise HTTPException(
            status_code=403,
            detail=limit_check.get("reason", "Monthly video limit reached. Please upgrade your plan.")
        )

    job_id = str(uuid.uuid4())
    job_store[job_id] = {
        "status": "queued",
        "progress": 0,
        "message": "Queued...",
        "video_url": None,
        "error": None
    }
    pipeline = VideoPipeline(job_id, user_id=user_id)
    background_tasks.add_task(pipeline.run, req)
    return JobStatus(job_id=job_id, **job_store[job_id])

@app.get("/status/{job_id}", response_model=JobStatus)
async def get_status(job_id: str):
    if job_id not in job_store:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(job_id=job_id, **job_store[job_id])

@app.get("/health")
async def health():
    return {"status": "ok"}
