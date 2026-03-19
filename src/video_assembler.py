import subprocess
import os
import asyncio
import httpx
import traceback
from pathlib import Path

async def download_file(url: str, dest: str) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            f.write(resp.content)
    
    # Dosya boyutunu kontrol et
    size = os.path.getsize(dest)
    print(f"[DEBUG] Downloaded {dest} — {size} bytes")
    if size == 0:
        raise Exception(f"Downloaded file is 0 bytes: {dest} from {url}")
    return dest

def get_audio_duration(audio_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        duration = float(result.stdout.strip())
        print(f"[DEBUG] Audio duration: {duration}s — {audio_path}")
        return duration
    except:
        print(f"[WARN] Could not get duration, defaulting to 5s. ffprobe output: {result.stderr}")
        return 5.0

def validate_inputs(image_path: str, audio_path: str):
    """Input dosyalarının varlığını ve boyutunu kontrol et"""
    for path in [image_path, audio_path]:
        if not os.path.exists(path):
            raise Exception(f"Input file not found: {path}")
        size = os.path.getsize(path)
        if size == 0:
            raise Exception(f"Input file is 0 bytes: {path}")
        print(f"[DEBUG] Validated: {path} — {size} bytes")

def add_ken_burns(image_path: str, audio_path: str, output_path: str, duration: float):
    """Tek slayt: görsel + ses + Ken Burns efekti"""
    validate_inputs(image_path, audio_path)
    
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,format=yuv420p",
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        "-t", str(duration + 0.5),
        "-loglevel", "warning",
        output_path
    ]
    
    print(f"[DEBUG] Running FFmpeg for slide: {output_path}")
    print(f"[DEBUG] CMD: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"[DEBUG] FFmpeg stdout: {result.stdout[-500:]}")
        print(f"[DEBUG] FFmpeg stderr: {result.stderr[-500:]}")
        
        if result.returncode != 0:
            raise Exception(f"FFmpeg failed (code {result.returncode}): {result.stderr[-800:]}")
        
        # Output dosyasını kontrol et
        if not os.path.exists(output_path):
            raise Exception(f"FFmpeg completed but output not found: {output_path}")
        out_size = os.path.getsize(output_path)
        if out_size == 0:
            raise Exception(f"FFmpeg output is 0 bytes: {output_path}")
        print(f"[DEBUG] Slide created: {output_path} — {out_size} bytes")
        
    except Exception as e:
        print(f"[ERROR] FFmpeg slide exception:\n{traceback.format_exc()}")
        raise
    
    return output_path

def concat_videos(video_paths: list, output_path: str):
    """Tüm slayt videolarını birleştirir"""
    list_file = output_path.replace(".mp4", "_list.txt")
    with open(list_file, "w") as f:
        for vp in video_paths:
            f.write(f"file '{os.path.abspath(vp)}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        "-loglevel", "warning",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(list_file):
        os.remove(list_file)
    if result.returncode != 0:
        raise Exception(f"FFmpeg concat error: {result.stderr[-500:]}")
    return output_path

async def assemble_video(slides: list, output_dir: str, job_id: str) -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    slide_videos = []

    for i, slide in enumerate(slides):
        try:
            print(f"[DEBUG] Processing slide {i}: image={slide['image_url']}, audio={slide['audio_path']}")
            img_path = f"{output_dir}/img_{i}.jpg"
            slide_video = f"{output_dir}/slide_{i}.mp4"

            await download_file(slide["image_url"], img_path)
            duration = get_audio_duration(slide["audio_path"])
            add_ken_burns(img_path, slide["audio_path"], slide_video, duration)
            slide_videos.append(slide_video)
            print(f"[DEBUG] Slide {i} done")
        except Exception as e:
            print(f"[ERROR] Slide {i} failed:\n{traceback.format_exc()}")
            raise

    final_path = f"{output_dir}/final_{job_id}.mp4"
    concat_videos(slide_videos, final_path)
    print(f"[DEBUG] Final video: {final_path} — {os.path.getsize(final_path)} bytes")
    return final_path
