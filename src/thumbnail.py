from PIL import Image, ImageDraw, ImageFont
import os

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

def split_title_smart(title: str):
    """
    Başlığı 2-3 satıra böl.
    Sayılar veya ilk kelime ayrı, geri kalan 2 satırda.
    Örnek: '7 Signs You Are Smarter Than You Think'
    → '7', 'SIGNS YOU ARE', 'SMARTER THAN YOU THINK'
    """
    words = title.split()
    if not words:
        return [title]

    lines = []
    # Eğer ilk kelime sayı veya kısaysa ayrı sat
    if words[0].isdigit() or len(words[0]) <= 2:
        lines.append(words[0])
        rest = words[1:]
    else:
        rest = words

    # Geri kalan kelimeleri 2 satıra böl
    mid = len(rest) // 2
    lines.append(" ".join(rest[:mid]))
    lines.append(" ".join(rest[mid:]))

    return [l for l in lines if l]

def create_youtube_cover(image_path: str, title: str, output_path: str):
    """
    YouTube tarzı kapak:
    - Koyu arka plan (görsel soluklaştırılmış)
    - Çok büyük beyaz başlık
    - Anahtar kelimeler mor highlight ile
    - Sağ üst küçük badge
    """
    img = Image.open(image_path).convert("RGBA")
    img = img.resize((1280, 720), Image.LANCZOS)
    W, H = 1280, 720

    # Tüm görseli %70 koyulaştır
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 180))
    img = Image.alpha_composite(img, dark)

    # Sol yarıya ekstra karartma — metin alanı
    left_dark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(left_dark)
    for x in range(W):
        alpha = int(100 * max(0, 1 - x / (W * 0.6)))
        ld.line([(x, 0), (x, H)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img, left_dark).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Başlığı satırlara böl
    lines = split_title_smart(title)

    # Font boyutlarını belirle
    # İlk satır sayıysa çok büyük, diğerleri büyük
    is_number_first = lines[0].isdigit()

    x_pad = 55
    y_start = 80

    if is_number_first:
        # Büyük numara
        num_font = get_font(200)
        text_font = get_font(90)
        small_font = get_font(72)

        # Numarayı çiz
        num = lines[0]
        draw.text((x_pad + 3, y_start + 3), num, font=num_font, fill=(0, 0, 0))
        draw.text((x_pad, y_start), num, font=num_font, fill=(255, 255, 255))

        # Mor accent çizgi numera altında
        num_bbox = draw.textbbox((0, 0), num, font=num_font)
        num_h = num_bbox[3]
        line_y = y_start + num_h + 10

        # Diğer satırlar
        curr_y = y_start + num_h - 20
        for i, line in enumerate(lines[1:]):
            f = text_font if i == 0 else small_font
            # Gölge
            draw.text((x_pad + 3, curr_y + 3), line.upper(), font=f, fill=(0, 0, 0))
            # Birinci metin satırı normal beyaz, ikincisi mor highlight ile
            if i == 0:
                draw.text((x_pad, curr_y), line.upper(), font=f, fill=(255, 255, 255))
            else:
                # Mor highlight bar
                bbox = draw.textbbox((x_pad, curr_y), line.upper(), font=f)
                pad = 8
                draw.rectangle([bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad], fill=(168, 85, 247))
                draw.text((x_pad, curr_y), line.upper(), font=f, fill=(255, 255, 255))
            curr_y += f.size + 16

    else:
        # Normal büyük başlık
        font_sizes = [100, 84, 68]
        curr_y = y_start
        for i, line in enumerate(lines):
            fs = font_sizes[min(i, len(font_sizes)-1)]
            f = get_font(fs)
            draw.text((x_pad + 3, curr_y + 3), line.upper(), font=f, fill=(0, 0, 0))
            if i == 1:
                bbox = draw.textbbox((x_pad, curr_y), line.upper(), font=f)
                pad = 8
                draw.rectangle([bbox[0]-pad, bbox[1]-pad, bbox[2]+pad, bbox[3]+pad], fill=(168, 85, 247))
            draw.text((x_pad, curr_y), line.upper(), font=f, fill=(255, 255, 255))
            curr_y += fs + 20

    # Sağ üst badge
    badge_font = get_font(28)
    badge = "▶  WATCH NOW"
    bbox = draw.textbbox((0, 0), badge, font=badge_font)
    bw = bbox[2] - bbox[0] + 32
    bh = bbox[3] - bbox[1] + 18
    bx, by = W - bw - 24, 24
    draw.rounded_rectangle([bx, by, bx+bw, by+bh], radius=10, fill=(168, 85, 247))
    draw.text((bx+16, by+9), badge, font=badge_font, fill=(255, 255, 255))

    img.save(output_path, "JPEG", quality=95)
    return output_path

def create_section_overlay(image_path: str, heading: str, number: int, output_path: str):
    """Section slaydı: üstte ince bar, sadece fontlar büyük"""
    img = Image.open(image_path).convert("RGBA")
    img = img.resize((1280, 720), Image.LANCZOS)

    BAR_H = 90
    overlay = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    ov = ImageDraw.Draw(overlay)
    ov.rectangle([0, 0, 1280, BAR_H], fill=(0, 0, 0, 200))
    ov.rectangle([0, 0, 8, BAR_H], fill=(168, 85, 247, 255))
    img = Image.alpha_composite(img, overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    num_font = get_font(62)
    head_font_size = 48 if len(heading) < 30 else 38 if len(heading) < 45 else 30
    head_font = get_font(head_font_size)

    num_y = (BAR_H - 62) // 2
    head_y = (BAR_H - head_font_size) // 2

    draw.text((16, num_y), str(number), font=num_font, fill=(168, 85, 247))
    draw.text((100, head_y), heading, font=head_font, fill=(255, 255, 255))

    img.save(output_path, "JPEG", quality=95)
    return output_path
