import asyncio
import os
from pathlib import Path
from src.store import job_store
from src.script_generator import generate_script
from src.wiro_client import generate_image
from src.elevenlabs_client import text_to_speech
from src.video_assembler import assemble_video

OUTPUT_BASE = os.environ.get("OUTPUT_DIR", "/tmp/videos")

class VideoPipeline:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.output_dir = f"{OUTPUT_BASE}/{job_id}"

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
            self._update("generating_script", 5, "Script yazılıyor...")
            script = await generate_script(req.topic, req.sections, req.language)

            # 2. Tüm bölümleri topla
            all_sections = [script["intro"]] + script["sections"] + [script["outro"]]
            total = len(all_sections)
            slides = []

            # 3. Ses + görsel paralel üret (her bölüm için)
            self._update("generating_assets", 15, f"0/{total} bölüm hazırlanıyor...")

            async def process_section(i, section):
                text = section["text"]
                image_prompt = section.get("image_prompt", req.topic)

                # style ekle
                full_prompt = f"{image_prompt}, {req.style}, high quality, 4K"

                audio_path = f"{self.output_dir}/audio_{i}.mp3"

                # Ses ve görsel paralel
                audio_task = text_to_speech(text, req.voice_id, audio_path)
                image_task = generate_image(full_prompt)

                audio_result, image_url = await asyncio.gather(audio_task, image_task)

                progress = 15 + int((i + 1) / total * 60)
                self._update("generating_assets", progress, f"{i+1}/{total} bölüm hazır")

                return {"image_url": image_url, "audio_path": audio_result}

            tasks = [process_section(i, s) for i, s in enumerate(all_sections)]
            slides = await asyncio.gather(*tasks)

            # 4. Video birleştir
            self._update("assembling", 80, "Video birleştiriliyor...")
            final_path = await assemble_video(list(slides), self.output_dir, self.job_id)

            # 5. Video URL döndür
            # Railway/Vercel'de static file serve veya cloud storage kullanılır
            # Şimdilik local path döndürüyoruz — production'da S3/R2'ye upload edilmeli
            video_url = f"/videos/{self.job_id}/final_{self.job_id}.mp4"
            self._update("done", 100, "Video hazır!", video_url=video_url)

        except Exception as e:
            self._update("error", 0, "Hata oluştu", error=str(e))
