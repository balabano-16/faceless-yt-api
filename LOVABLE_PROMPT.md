# Lovable Prompt — Faceless YouTube Video Generator

Build a clean, modern web app called "VideoForge AI" that generates faceless YouTube videos using an API.

## Tech Stack
- React + TypeScript
- Tailwind CSS
- shadcn/ui components

## Pages

### 1. Home / Generate Page (main page)

A dark-themed dashboard with:

**Header:**
- Logo: "VideoForge AI" with a play icon
- Nav: Home, My Videos, Pricing

**Main Card — Video Generator Form:**
```
Title: "Create Your Video"
Subtitle: "AI-powered faceless YouTube videos in minutes"

Fields:
1. Topic input (text, placeholder: "Top 5 AI Tools in 2026")
2. Language select: Turkish / English
3. Sections slider: 3-8 (default 5), shows "5 sections"
4. Voice select dropdown:
   - Adam (Male, English)
   - Rachel (Female, English)
   - Josh (Male, English)
5. Style select:
   - Cinematic (default)
   - Documentary
   - Minimalist
   - Epic

Generate button: "Generate Video →" (full width, purple gradient)
```

**Under the form — Cost Estimator:**
```
Small card showing:
"Estimated cost: ~$0.55" (updates based on sections slider)
"Estimated time: ~8 min"
```

### 2. Progress Page (shown after clicking Generate)

Replaces the form with a progress tracker:

```
[Stepper with 4 steps]
1. Writing Script    ✓ or spinner
2. Generating Visuals ✓ or spinner  
3. Generating Audio  ✓ or spinner
4. Assembling Video  ✓ or spinner

[Progress bar: 0-100%]
[Status message: "Generating visuals for section 3/5..."]

[Cancel button]
```

Polls GET /status/{job_id} every 3 seconds.

### 3. Done State (inside Progress Page)

When status === "done":
```
✓ Big green checkmark
"Your video is ready!"

[Video player — plays the video_url]
[Download button]
[Generate Another button]
```

## API Integration

Base URL comes from env variable: `VITE_API_URL`

```typescript
// Generate video
POST {VITE_API_URL}/generate
Body: { topic, sections, voice_id, style, language }
Response: { job_id, status }

// Poll status  
GET {VITE_API_URL}/status/{job_id}
Response: { status, progress, message, video_url, error }
```

## Style Guidelines
- Dark background: #0f0f0f
- Card background: #1a1a1a  
- Purple accent: #7c3aed
- Clean, modern, minimal
- Smooth loading animations

## Voice ID Mapping
```typescript
const VOICES = {
  "Adam (Male)": "pNInz6obpgDQGcFmaJgB",
  "Rachel (Female)": "21m00Tcm4TlvDq8ikWAM", 
  "Josh (Male)": "TxGEqnHWrfWFTfGW9XjX",
}
```
