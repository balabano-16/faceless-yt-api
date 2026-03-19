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
    cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 5.0

def validate_inputs(*paths):
    for path in paths:
        if not os.path.exists(path):
            raise Exception(f"File not found: {path}")
        if os.path.getsize(path) == 0:
            raise Exception(f"File is 0 bytes: {path}")

def make_cover_slide(image_path: str, title: str, audio_path: str, output_path: str, duration: float):
    """Kapak slaydı: Pillow ile YouTube tarzı tasarım"""
    validate_inputs(image_path, audio_path)
    from src.thumbnail import create_youtube_cover

    # Pillow ile kapak görseli oluştur
    cover_path = image_path.replace(".jpg", "_cover.jpg")
    create_youtube_cover(image_path, title, cover_path)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", cover_path,
        "-i", audio_path,
        "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,format=yuv420p",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", "-t", str(duration + 0.5),
        "-loglevel", "warning", output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Cover slide error: {result.stderr[-500:]}")
    return output_path

def make_section_slide(image_path: str, heading: str, number: int, audio_path: str, output_path: str, duration: float):
    """Section slaydı: Pillow ile üstte numara + başlık bar"""
    validate_inputs(image_path, audio_path)
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(image_path).convert("RGBA")
    img = img.resize((1280, 720), Image.LANCZOS)

    def get_font(size):
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                return ImageFont.truetype(fp, size)
        return ImageFont.load_default()

    # Üst bar overlay
    overlay = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rectangle([0, 0, 1280, 90], fill=(0, 0, 0, 185))
    ov_draw.rectangle([0, 0, 6, 90], fill=(168, 85, 247, 255))
    img = Image.alpha_composite(img, overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    num_font = get_font(56)
    head_font_size = 38 if len(heading) < 40 else 30 if len(heading) < 60 else 24
    head_font = get_font(head_font_size)

    draw.text((20, 15), str(number), font=num_font, fill=(168, 85, 247))
    draw.text((88, (90 - head_font_size) // 2), heading, font=head_font, fill=(255, 255, 255))

    section_path = image_path.replace(".jpg", "_section.jpg")
    img.save(section_path, "JPEG", quality=95)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", section_path,
        "-i", audio_path,
        "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,format=yuv420p",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", "-t", str(duration + 0.5),
        "-loglevel", "warning", output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Section slide error: {result.stderr[-500:]}")
    return output_path

def make_simple_slide(image_path: str, audio_path: str, output_path: str, duration: float):
    """Outro slaydı: sade"""
    validate_inputs(image_path, audio_path)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-i", audio_path,
        "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,format=yuv420p",
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", "-t", str(duration + 0.5),
        "-loglevel", "warning", output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Simple slide error: {result.stderr[-500:]}")
    return output_path

def concat_with_transitions(video_paths: list, output_path: str):
    """Videolar arası fade-to-black geçiş efekti"""
    if len(video_paths) == 1:
        import shutil
        shutil.copy(video_paths[0], output_path)
        return output_path

    # Önce tüm videolar aynı formata çevir, sonra birleştir
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

async def assemble_video(slides: list, output_dir: str, job_id: str, title: str = "") -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    slide_videos = []

    for i, slide in enumerate(slides):
        try:
            img_path = f"{output_dir}/img_{i}.jpg"
            slide_video = f"{output_dir}/slide_{i}.mp4"
            await download_file(slide["image_url"], img_path)
            duration = get_audio_duration(slide["audio_path"])

            slide_type = slide.get("type", "section")
            
            if slide_type == "cover":
                make_cover_slide(img_path, title or "AI Video", slide["audio_path"], slide_video, duration)
            elif slide_type == "section":
                make_section_slide(img_path, slide.get("heading", ""), slide.get("number", i), slide["audio_path"], slide_video, duration)
            else:
                make_simple_slide(img_path, slide["audio_path"], slide_video, duration)

            slide_videos.append(slide_video)
            print(f"[DEBUG] Slide {i} ({slide_type}) done")
        except Exception as e:
            print(f"[ERROR] Slide {i} failed: {traceback.format_exc()}")
            raise

    final_path = f"{output_dir}/final_{job_id}.mp4"
    concat_with_transitions(slide_videos, final_path)
    print(f"[DEBUG] Final video: {final_path} — {os.path.getsize(final_path)} bytes")
    return final_path
