from PIL import Image, ImageDraw, ImageFont, ImageFilter
import textwrap
import os

def create_youtube_cover(image_path: str, title: str, output_path: str):
    """
    YouTube tarzı kapak görseli üretir:
    - Sol tarafta koyu gradient
    - Büyük bold başlık, word wrap
    - Alt kısımda mor accent çizgi
    - Sağ üstte izleme sayısı / badge
    """
    img = Image.open(image_path).convert("RGB")
    img = img.resize((1280, 720), Image.LANCZOS)
    draw = ImageDraw.Draw(img)
    W, H = 1280, 720

    # Sol + alt koyu gradient overlay
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)

    # Sol gradient (soldan sağa kararıyor)
    for x in range(W):
        alpha = int(200 * max(0, 1 - x / (W * 0.75)))
        ov_draw.line([(x, 0), (x, H)], fill=(0, 0, 0, alpha))

    # Alt gradient
    for y in range(H):
        alpha = int(180 * max(0, (y - H * 0.5) / (H * 0.5)))
        ov_draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))

    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Font — sistem fontunu kullan
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

    title_font = get_font(72)
    small_font = get_font(28)

    # Başlığı satırlara böl
    words = title.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=title_font)
        if bbox[2] > 700:
            if current:
                lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    # Başlık konumu — dikey ortalı, sol hizalı
    line_height = 85
    total_h = len(lines) * line_height
    start_y = (H - total_h) // 2 - 30
    x_pad = 60

    # Gölge efekti
    for i, line in enumerate(lines):
        y = start_y + i * line_height
        draw.text((x_pad + 3, y + 3), line, font=title_font, fill=(0, 0, 0, 180))

    # Ana başlık metni
    for i, line in enumerate(lines):
        y = start_y + i * line_height
        draw.text((x_pad, y), line, font=title_font, fill=(255, 255, 255))

    # Mor accent çizgi (başlığın altında)
    accent_y = start_y + len(lines) * line_height + 10
    draw.rectangle([x_pad, accent_y, x_pad + 120, accent_y + 6], fill=(168, 85, 247))

    # Sağ üst badge — "Watch Now"
    badge_text = "▶  WATCH NOW"
    bbox = draw.textbbox((0, 0), badge_text, font=small_font)
    bw = bbox[2] - bbox[0] + 30
    bh = bbox[3] - bbox[1] + 16
    bx = W - bw - 30
    by = 30
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=8, fill=(168, 85, 247))
    draw.text((bx + 15, by + 8), badge_text, font=small_font, fill=(255, 255, 255))

    img.save(output_path, "JPEG", quality=95)
    return output_path
