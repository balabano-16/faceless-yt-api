import subprocess
import os
import asyncio
import httpx
from pathlib import Path

async def download_file(url: str, dest: str) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            f.write(resp.content)
    return dest

def add_ken_burns(image_path: str, audio_path: str, output_path: str, duration: float):
    """Tek slayt: görsel + ses + Ken Burns efekti"""
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-filter_complex",
        f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
        f"crop=1920:1080,zoompan=z='min(zoom+0.0015,1.3)':d={int(duration*25)}:s=1920x1080[v]",
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        "-t", str(duration + 0.5),
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg hatası: {result.stderr[-500:]}")
    return output_path

def get_audio_duration(audio_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 5.0

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
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(list_file):
        os.remove(list_file)
    if result.returncode != 0:
        raise Exception(f"Concat hatası: {result.stderr[-500:]}")
    return output_path

async def assemble_video(slides: list, output_dir: str, job_id: str) -> str:
    """
    slides = [
      {"image_url": "...", "audio_path": "..."},
      ...
    ]
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    slide_videos = []

    for i, slide in enumerate(slides):
        img_path = f"{output_dir}/img_{i}.jpg"
        slide_video = f"{output_dir}/slide_{i}.mp4"

        await download_file(slide["image_url"], img_path)
        duration = get_audio_duration(slide["audio_path"])
        add_ken_burns(img_path, slide["audio_path"], slide_video, duration)
        slide_videos.append(slide_video)

    final_path = f"{output_dir}/final_{job_id}.mp4"
    concat_videos(slide_videos, final_path)
    return final_path
