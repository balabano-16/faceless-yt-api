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
    size = os.path.getsize(dest)
    print(f"[DEBUG] Downloaded {dest} — {size} bytes")
    if size == 0:
        raise Exception(f"Downloaded file is 0 bytes: {dest}")
    return dest

def get_audio_duration(audio_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        duration = float(result.stdout.strip())
        print(f"[DEBUG] Audio duration: {duration:.2f}s — {os.path.basename(audio_path)}")
        return duration
    except:
        print(f"[WARN] Could not get duration for {audio_path}, defaulting to 6s")
        return 6.0

def validate_inputs(*paths):
    for path in paths:
        if not os.path.exists(path):
            raise Exception(f"File not found: {path}")
        if os.path.getsize(path) == 0:
            raise Exception(f"File is 0 bytes: {path}")

def make_slide(image_path: str, audio_path: str, output_path: str, duration: float, is_portrait: bool = False):
    """Evrensel slide: yatay (1280x720) veya dikey (1080x1920)"""
    validate_inputs(image_path, audio_path)
    w, h = (1080, 1920) if is_portrait else (1280, 720)
    # Ses süresine 1.0s buffer ekle — geçiş için nefes boşluğu
    video_duration = duration + 1.0
    print(f"[DEBUG] make_slide: {w}x{h}, audio={duration:.2f}s, video={video_duration:.2f}s")
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-framerate", "24",
        "-t", str(video_duration),  # önce görsel süresini belirle
        "-i", image_path,
        "-i", audio_path,
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=yuv420p",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "44100", "-b:a", "128k",
        "-t", str(video_duration),
        "-loglevel", "warning", output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Slide error: {result.stderr[-500:]}")
    return output_path

def merge_audio_to_video(video_path: str, audio_path: str, output_path: str):
    """P-Video klibine ses ekler"""
    validate_inputs(video_path, audio_path)
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        "-loglevel", "warning",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Audio merge error: {result.stderr[-300:]}")
    return output_path

def concat_with_transitions(video_paths: list, output_path: str):
    if len(video_paths) == 1:
        import shutil
        shutil.copy(video_paths[0], output_path)
        return output_path

    list_file = output_path.replace(".mp4", "_list.txt")
    with open(list_file, "w") as f:
        for vp in video_paths:
            f.write(f"file '{os.path.abspath(vp)}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        "-loglevel", "warning",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(list_file):
        os.remove(list_file)
    if result.returncode != 0:
        raise Exception(f"Concat error: {result.stderr[-500:]}")
    return output_path

async def assemble_video(slides: list, output_dir: str, job_id: str, title: str = "", is_portrait: bool = False) -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    slide_videos = []
    print(f"[DEBUG] assemble_video: is_portrait={is_portrait}, slides={len(slides)}")

    for i, slide in enumerate(slides):
        try:
            slide_video = f"{output_dir}/slide_{i}.mp4"

            if slide.get("is_video_clip"):
                # P-Video modu: mp4 klip indir, ses ekle
                print(f"[DEBUG] Slide {i}: P-Video clip mode")
                clip_path = f"{output_dir}/clip_{i}.mp4"
                await download_file(slide["image_url"], clip_path)
                merge_audio_to_video(clip_path, slide["audio_path"], slide_video)
            else:
                # Görsel modu: jpg indir, FFmpeg ile video yap
                img_path = f"{output_dir}/img_{i}.jpg"
                await download_file(slide["image_url"], img_path)
                duration = get_audio_duration(slide["audio_path"])
                make_slide(img_path, slide["audio_path"], slide_video, duration, is_portrait)

            slide_videos.append(slide_video)
            print(f"[DEBUG] Slide {i} done")
        except Exception as e:
            print(f"[ERROR] Slide {i} failed: {traceback.format_exc()}")
            raise

    final_path = f"{output_dir}/final_{job_id}.mp4"
    concat_with_transitions(slide_videos, final_path)
    print(f"[DEBUG] Final video: {final_path} — {os.path.getsize(final_path)} bytes")
    return final_path
