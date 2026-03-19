# Faceless YouTube API

AI ile otomatik faceless YouTube videosu üreten backend API.

## Pipeline
```
Konu → Gemini Script → ElevenLabs Ses + Wiro Görsel (paralel) → FFmpeg Video → MP4
```

## Kurulum (Local)

```bash
git clone <repo>
cd faceless-yt-api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # API key'lerini gir
uvicorn main:app --reload
```

API: http://localhost:8000
Docs: http://localhost:8000/docs

## Railway Deploy (5 dakika)

1. [railway.app](https://railway.app) → New Project → Deploy from GitHub
2. Variables sekmesine gir, .env.example'daki key'leri ekle
3. Deploy → URL al

## API Kullanımı

### Video Üret
```
POST /generate
{
  "topic": "Top 5 AI Tools in 2026",
  "sections": 5,
  "voice_id": "pNInz6obpgDQGcFmaJgB",
  "language": "tr"
}
→ { "job_id": "uuid", "status": "queued" }
```

### Durum Kontrol
```
GET /status/{job_id}
→ { "status": "done", "progress": 100, "video_url": "..." }
```

## Environment Variables

| Key | Açıklama |
|-----|----------|
| WIRO_API_KEY | Wiro AI panelinden alınır |
| WIRO_API_SECRET | Wiro AI panelinden alınır |
| ELEVENLABS_API_KEY | elevenlabs.io/api |
| OUTPUT_DIR | Video çıktı klasörü (default: /tmp/videos) |

## Ses Seçenekleri (ElevenLabs)

| ID | Ses |
|----|-----|
| pNInz6obpgDQGcFmaJgB | Adam (erkek, İngilizce) |
| 21m00Tcm4TlvDq8ikWAM | Rachel (kadın, İngilizce) |
| TxGEqnHWrfWFTfGW9XjX | Josh (erkek, İngilizce) |

## Maliyet (per video, 5 bölüm)
- Wiro görsel (7 görsel): ~$0.35
- ElevenLabs ses: ~$0.15
- Gemini script: ~$0.05
- **Toplam: ~$0.55/video**
