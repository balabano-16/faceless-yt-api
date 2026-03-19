import asyncio
import os
from pathlib import Path
from src.store import job_store
from src.script_generator import generate_script
from src.wiro_client import generate_image
from src.elevenlabs_client import text_to_speech
from src.video_assembler import assemble_video

OUTPUT_BASE = os.environ.get("OUTPUT_DIR", "/tmp/videos")
BASE_URL = os.environ.get("BASE_URL", "https://faceless-yt-api-production.up.railway.app")

class VideoPipeline:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.output_dir = f"{OUTPUT_BASE}/{job_id}"

    def _make_cover_prompt(self, topic: str, title: str, style: str) -> str:
        """
        Nano Banana için YouTube kapak görseli prompt'u.
        Sinematik, dramatik, yüz göstermeyen ama konuya uygun.
        """
        topic_lower = topic.lower()

        # Konuya göre sahne seç
        if any(w in topic_lower for w in ["habit", "productiv", "routine", "morning", "success"]):
            scene = "a person silhouette standing at the top of a mountain at golden hour, arms wide open, sun rays breaking through clouds"
        elif any(w in topic_lower for w in ["smart", "brain", "psycholog", "mind", "think", "genius"]):
            scene = "a glowing human brain surrounded by floating light particles and neural connections in a dark cosmic space"
        elif any(w in topic_lower for w in ["money", "rich", "wealth", "finance", "invest"]):
            scene = "a rain of golden coins falling in a dark dramatic background with light rays, cinematic atmosphere"
        elif any(w in topic_lower for w in ["ai", "tech", "future", "robot", "digital"]):
            scene = "a futuristic glowing neural network with blue and purple light streams in a dark background, hyper realistic"
        elif any(w in topic_lower for w in ["health", "fit", "body", "workout", "exercise"]):
            scene = "a dramatic silhouette of an athletic person training at sunset, strong backlighting, cinematic"
        elif any(w in topic_lower for w in ["relation", "love", "social", "people", "friend"]):
            scene = "two silhouettes facing each other with warm golden light between them, bokeh background, cinematic"
        else:
            scene = f"a dramatic cinematic scene representing {topic}, powerful composition, epic atmosphere"

        return (
            f"{scene}, "
            f"ultra high quality, 8K, cinematic photography, dramatic lighting, "
            f"professional color grading, sharp focus, epic composition, "
            f"no text, no watermark, photorealistic"
        )

    def _update(self, status: str, progress: int, message: str, video_url=None, error=None):
        job_store[self.job_id].update({
            "status": status,
            "progress": progress,
            "message": message,
            "video_url": video_url,
            "error": error
        })

    async def run(self, req):
        try:
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)

            # 1. Script üret
            self._update("generating_script", 5, "Writing script...")
            script = await generate_script(req.topic, req.sections, req.language)
            title = script.get("title", req.topic)

            # Kapak için özel prompt — Nano Banana'nın güçlü olduğu sinematik stil
            cover_prompt = self._make_cover_prompt(req.topic, title, req.style)

            # 2. Slide listesi oluştur — cover + sections + outro
            raw_sections = [
                {"type": "cover", "text": script["intro"]["text"], "image_prompt": cover_prompt, "heading": title, "number": 0},
            ]
            for s in script["sections"]:
                raw_sections.append({
                    "type": "section",
                    "text": s["text"],
                    "image_prompt": s.get("image_prompt", req.topic),
                    "heading": s.get("heading", f"Point {s['number']}"),
                    "number": s["number"]
                })
            raw_sections.append({
                "type": "outro",
                "text": script["outro"]["text"],
                "image_prompt": script["outro"]["image_prompt"],
                "heading": "",
                "number": 0
            })

            total = len(raw_sections)
            slides = []

            # 3. Her slide için ses + görsel paralel üret
            self._update("generating_assets", 15, f"0/{total} sections ready...")

            for i, section in enumerate(raw_sections):
                full_prompt = f"{section['image_prompt']}, {req.style}, high quality, 4K"
                audio_path = f"{self.output_dir}/audio_{i}.mp3"

                audio_result, image_url = await asyncio.gather(
                    text_to_speech(section["text"], req.voice_id, audio_path),
                    generate_image(full_prompt)
                )

                progress = 15 + int((i + 1) / total * 60)
                self._update("generating_assets", progress, f"{i+1}/{total} sections ready")
                slides.append({
                    "image_url": image_url,
                    "audio_path": audio_result,
                    "type": section["type"],
                    "heading": section["heading"],
                    "number": section["number"]
                })

            # 4. Video birleştir
            self._update("assembling", 80, "Assembling video...")
            final_path = await assemble_video(slides, self.output_dir, self.job_id, title)

            # 5. URL döndür
            video_url = f"{BASE_URL}/videos/{self.job_id}/final_{self.job_id}.mp4"
            self._update("done", 100, "Video ready!", video_url=video_url)

        except Exception as e:
            self._update("error", 0, "An error occurred", error=str(e))
