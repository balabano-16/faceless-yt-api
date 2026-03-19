import hmac
import hashlib
import time
import httpx
import asyncio
import os
from typing import Optional

WIRO_API_KEY = os.environ.get("WIRO_API_KEY", "")
WIRO_API_SECRET = os.environ.get("WIRO_API_SECRET", "")
BASE_URL = "https://api.wiro.ai/v1"
SOCKET_URL = "wss://socket.wiro.ai/v1"

def _make_headers() -> dict:
    nonce = str(int(time.time() * 1000))
    signature_raw = WIRO_API_SECRET + nonce
    signature = hmac.new(
        WIRO_API_KEY.encode(),
        signature_raw.encode(),
        hashlib.sha256
    ).hexdigest()
    return {
        "x-api-key": WIRO_API_KEY,
        "x-nonce": nonce,
        "x-signature": signature,
        "Content-Type": "application/json"
    }

async def generate_image(prompt: str, aspect_ratio: str = "16:9") -> str:
    """Nano Banana 2 ile görsel üretir, URL döner"""
    headers = _make_headers()
    payload = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "output_format": "jpeg"
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{BASE_URL}/Run/google/nano-banana-2",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        task_token = data.get("socketAccessToken") or data.get("taskToken")
        if task_token:
            return await _wait_for_result(task_token)
        return data.get("output") or data.get("image_url")

async def generate_video_from_image(image_url: str, prompt: str = "") -> str:
    """Seedance Lite ile image-to-video üretir"""
    headers = _make_headers()
    payload = {
        "image_url": image_url,
        "prompt": prompt,
        "duration": 5,
        "resolution": "720p"
    }
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{BASE_URL}/Run/bytedance/image-to-video-seedance-lite-v1",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        task_token = data.get("socketAccessToken") or data.get("taskToken")
        if task_token:
            return await _wait_for_result(task_token)
        return data.get("output") or data.get("video_url")

async def _wait_for_result(task_token: str, timeout: int = 300) -> str:
    """WebSocket üzerinden task sonucunu bekler"""
    import websockets
    import json
    result_url = None
    start = time.time()
    try:
        async with websockets.connect(SOCKET_URL) as ws:
            await ws.send(json.dumps({"type": "task_info", "tasktoken": task_token}))
            while time.time() - start < timeout:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10)
                    data = json.loads(msg)
                    if data.get("type") == "task_done":
                        result_url = data.get("output") or data.get("url")
                        break
                    elif data.get("type") == "task_error":
                        raise Exception(f"Wiro task error: {data}")
                except asyncio.TimeoutError:
                    continue
    except Exception as e:
        raise Exception(f"WebSocket bağlantı hatası: {e}")
    if not result_url:
        raise Exception("Wiro task zaman aşımına uğradı")
    return result_url
