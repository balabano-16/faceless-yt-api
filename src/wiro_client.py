import httpx
import asyncio
import os
import time
import hmac
import hashlib

WIRO_API_KEY = os.environ.get("WIRO_API_KEY", "")
WIRO_API_SECRET = os.environ.get("WIRO_API_SECRET", "")
RUN_BASE = "https://api.wiro.ai/v1/Run"
TASK_URL = "https://api.wiro.ai/v1/Task/Detail"

def _auth_headers() -> dict:
    nonce = str(int(time.time()))
    signature = hmac.new(
        WIRO_API_KEY.encode(),
        f"{WIRO_API_SECRET}{nonce}".encode(),
        hashlib.sha256
    ).hexdigest()
    return {
        "x-api-key": WIRO_API_KEY,
        "x-nonce": nonce,
        "x-signature": signature,
    }

async def _poll_task(taskid: str, timeout: int = 300) -> str:
    """task_postprocess_end gelene kadar poll eder, output URL döner"""
    start = time.time()
    async with httpx.AsyncClient(timeout=30) as client:
        while time.time() - start < timeout:
            resp = await client.post(
                TASK_URL,
                headers=_auth_headers(),
                data={"taskid": taskid}
            )
            resp.raise_for_status()
            data = resp.json()
            tasklist = data.get("tasklist", [])
            if not tasklist:
                await asyncio.sleep(3)
                continue
            task = tasklist[0]
            status = task.get("status", "")
            if status == "task_postprocess_end":
                outputs = task.get("outputs", [])
                if outputs:
                    return outputs[0]["url"]
                # outputs geç dolabilir — 3s bekleyip tekrar dene
                print(f"[WARN] task_postprocess_end but no outputs for taskid={taskid}, retrying in 3s...")
                await asyncio.sleep(3)
                continue
            elif status == "task_cancel":
                raise Exception("Wiro task was cancelled")
            await asyncio.sleep(3)
    raise Exception(f"Wiro task timeout after {timeout}s")

async def generate_image(prompt: str, aspect_ratio: str = "16:9") -> str:
    """Nano Banana 2 ile görsel üretir, CDN URL döner"""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{RUN_BASE}/google/nano-banana-2",
            headers=_auth_headers(),
            data={
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "output_format": "jpeg"
            }
        )
        resp.raise_for_status()
        data = resp.json()

    taskid = data.get("taskid")
    if not taskid:
        raise Exception(f"Wiro image: no taskid in response: {data}")
    return await _poll_task(str(taskid))

async def generate_script_text(prompt: str, system: str = "", max_tokens: int = 2000) -> str:
    """Gemini 2.5 Flash ile metin üretir, ham string döner"""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{RUN_BASE}/google/gemini-2-5-flash",
            headers=_auth_headers(),
            data={
                "prompt": prompt,
                "systemInstructions": system,
                "maxOutputTokens": max_tokens,
                "temperature": "0.7",
                "thinkingBudget": 0,
            }
        )
        resp.raise_for_status()
        data = resp.json()

    taskid = data.get("taskid")
    if not taskid:
        raise Exception(f"Wiro LLM: no taskid in response: {data}")

    # LLM için poll — output text olarak gelir
    start = time.time()
    async with httpx.AsyncClient(timeout=30) as client:
        while time.time() - start < 120:
            resp = await client.post(
                TASK_URL,
                headers=_auth_headers(),
                data={"taskid": str(taskid)}
            )
            resp.raise_for_status()
            data = resp.json()
            tasklist = data.get("tasklist", [])
            if not tasklist:
                await asyncio.sleep(3)
                continue
            task = tasklist[0]
            status = task.get("status", "")
            if status == "task_postprocess_end":
                outputs = task.get("outputs", [])
                if outputs:
                    # LLM outputu text olarak döner
                    out = outputs[0]
                    return out.get("text") or out.get("url") or str(out)
                # debug output içinde olabilir
                return task.get("debugoutput") or str(task)
            elif status == "task_cancel":
                raise Exception("Wiro LLM task cancelled")
            await asyncio.sleep(3)
    raise Exception("Wiro LLM timeout")

async def generate_video_clip(prompt: str, image_url: str = "", duration: int = 5, aspect_ratio: str = "16:9") -> str:
    """
    P-Video ile video klip üretir.
    image_url varsa image-to-video, yoksa text-to-video.
    CDN URL döner (.mp4)
    """
    data = {
        "prompt": prompt,
        "ratio": aspect_ratio,
        "duration": str(duration),
        "resolution": "720p",
        "fps": "24",
        "seed": "0",
        "saveAudio": "false",
        "draft": "false",
        "promptUpsampling": "true",
    }
    if image_url:
        data["inputImage"] = image_url

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{RUN_BASE}/pruna/p-video",
            headers=_auth_headers(),
            data=data
        )
        resp.raise_for_status()
        result = resp.json()

    taskid = result.get("taskid")
    if not taskid:
        raise Exception(f"P-Video: no taskid in response: {result}")

    # Video üretimi daha uzun sürebilir — 300s timeout
    url = await _poll_task(str(taskid), timeout=300)
    # Wiro video URL bazen geç hazır olur — 5s bekle
    await asyncio.sleep(5)
    return url
