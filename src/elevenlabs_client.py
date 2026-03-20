import httpx
import asyncio
import os
import time
import hmac
import hashlib

WIRO_API_KEY = os.environ.get("WIRO_API_KEY", "")
WIRO_API_SECRET = os.environ.get("WIRO_API_SECRET", "")
RUN_URL = "https://api.wiro.ai/v1/Run/elevenlabs/text-to-speech"
TASK_URL = "https://api.wiro.ai/v1/Task/Detail"

VOICE_OPTIONS = {
    "pNInz6obpgDQGcFmaJgB": "29vD33N1CtxCmqQRPOHJ",
    "21m00Tcm4TlvDq8ikWAM": "21m00Tcm4TlvDq8ikWAM",
    "TxGEqnHWrfWFTfGW9XjX": "IKne3meq5aSn9XLyUdCD",
}

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

async def _poll_task(taskid: str, timeout: int = 120) -> str:
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
                # Bazen outputs geç dolabilir, bir kez daha dene
                await asyncio.sleep(2)
                continue
            elif status == "task_cancel":
                raise Exception("TTS task cancelled")
            await asyncio.sleep(3)
    raise Exception("TTS task timeout")

async def text_to_speech(text: str, voice_id: str, output_path: str, retries: int = 3) -> str:
    """Wiro üzerinden ElevenLabs TTS, retry destekli"""
    wiro_voice = VOICE_OPTIONS.get(voice_id, "21m00Tcm4TlvDq8ikWAM")

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    RUN_URL,
                    headers=_auth_headers(),
                    data={
                        "prompt": text,
                        "model": "eleven_flash_v2_5",
                        "voice": wiro_voice,
                        "outputFormat": "mp3_44100_128",
                    }
                )
                resp.raise_for_status()
                data = resp.json()

            taskid = data.get("taskid")
            if not taskid:
                raise Exception(f"TTS: no taskid: {data}")

            audio_url = await _poll_task(str(taskid))

            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.get(audio_url)
                r.raise_for_status()
                with open(output_path, "wb") as f:
                    f.write(r.content)

            size = os.path.getsize(output_path)
            if size == 0:
                raise Exception("TTS output file is 0 bytes")

            print(f"[DEBUG] TTS done: {os.path.basename(output_path)} — {size} bytes")
            return output_path

        except Exception as e:
            print(f"[WARN] TTS attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(3)
            else:
                raise
