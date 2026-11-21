"""썰배달 카드뉴스 생성기.

사용법: python3 tools/make_cards.py spec.json cards/YYYY-MM-DD-slug
spec.json 형식:
{
  "tag": "오늘의 썰",
  "slides": [
    {"kind": "cover", "lines": [["제목 1줄", 84, "dark"], ["강조 줄", 84, "red"], ["", 40, "dark"], ["부제", 46, "dark"]]},
    {"kind": "body",  "lines": [["본문 줄", 50, "dark"], ["", 0, "dark"], ["강조 줄", 50, "red"]]},
    {"kind": "end",   "lines": [["마무리", 54, "dark"], ["질문", 54, "red"]]}
  ]
}
- 슬라이드 2~10장. 한 줄은 한글 기준 약 18자 이내(50px), 표지는 약 11자 이내(84px).
- 빈 문자열 줄은 문단 간격.
- 출력: 01.jpg, 02.jpg ... (1080x1350, 4:5, JPEG)
- 사진 표지: cover 슬라이드에 "photo": "cover_photo.jpg" (spec.json 기준 상대경로)를 넣으면
  사진 배경 + 흰 큰 제목으로 렌더링. 제목은 3줄 이내, 줄당 9자 안팎(90px). "red" 줄은 노란색으로 강조.
- 사진 구하기: tools/find_photo.py 참고 (Openverse, CC0/퍼블릭도메인만)
"""
import html
import json
import os
import subprocess
import sys

from PIL import Image

W, H = 1080, 1350
FONT = "Noto Sans CJK KR"
TITLE_FONT = "Black Han Sans"  # fonts/BlackHanSans-Regular.ttf 를 ~/.fonts 에 복사 후 fc-cache -f
COLORS = {"dark": "#2B2B2B", "red": "#E5484D"}


def photo_cover(slide, page, total, tag, base_dir):
    """사진 배경 표지: 사진 + 아래쪽 어두운 그라데이션 + 큰 흰 제목(Black Han Sans)."""
    import base64
    path = slide["photo"]
    if not os.path.isabs(path):
        path = os.path.join(base_dir, path)
    im = Image.open(path).convert("RGB")
    # 4:5로 가운데 크롭 후 1080x1350
    tw, th = W, H
    r = max(tw / im.width, th / im.height)
    im = im.resize((int(im.width * r + 1), int(im.height * r + 1)), Image.LANCZOS)
    left, top = (im.width - tw) // 2, (im.height - th) // 2
    im = im.crop((left, top, left + tw, top + th))
    import io
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode()
    lines = slide["lines"]
    sizes = [s for t, s, c in lines if t]
    block = sum(int(s * 1.25) for t, s, c in lines if t) + sum(40 for t, s, c in lines if not t)
    y = H - 200 - block
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
           '<stop offset="0" stop-color="#000" stop-opacity="0.15"/>'
           '<stop offset="0.45" stop-color="#000" stop-opacity="0.25"/>'
           '<stop offset="1" stop-color="#000" stop-opacity="0.88"/></linearGradient></defs>',
           f'<image width="{W}" height="{H}" xlink:href="data:image/jpeg;base64,{b64}"/>',
           f'<rect width="{W}" height="{H}" fill="url(#g)"/>',
           '<rect x="80" y="90" width="260" height="76" rx="38" fill="#FFD84D"/>',
           f'<text x="210" y="142" text-anchor="middle" font-family="{FONT}" font-weight="900" font-size="36" fill="#2B2B2B">{html.escape(tag)}</text>',
           f'<text x="{W-80}" y="142" text-anchor="end" font-family="{FONT}" font-weight="700" font-size="34" fill="#FFFFFF" opacity="0.8">{page}/{total}</text>']
    for text, size, color in lines:
        if text == "":
            y += 40
            continue
        fill = {"dark": "#FFFFFF", "red": "#FFD84D"}.get(color, color)
        y += int(size * 1.0)
        out.append(f'<text x="80" y="{y}" font-family="{TITLE_FONT}" font-size="{size}" fill="{fill}">{html.escape(text)}</text>')
        y += int(size * 0.25)
    out.append(f'<text x="80" y="{H-90}" font-family="{FONT}" font-weight="900" font-size="38" fill="#FFD84D">썰배달</text>')
    out.append(f'<text x="{W-80}" y="{H-90}" text-anchor="end" font-family="{FONT}" font-weight="500" font-size="30" fill="#FFFFFF" opacity="0.75">@sseol.delivery</text>')
    out.append('</svg>')
    return "\n".join(out)


def render(slide, page, total, tag, base_dir="."):
    kind = slide["kind"]
    if kind == "cover" and slide.get("photo"):
        return photo_cover(slide, page, total, tag, base_dir)
    bg = "#FFD84D" if kind in ("cover", "end") else "#FFF8E1"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           f'<rect width="{W}" height="{H}" fill="{bg}"/>',
           '<rect x="80" y="90" width="260" height="76" rx="38" fill="#2B2B2B"/>',
           f'<text x="210" y="142" text-anchor="middle" font-family="{FONT}" font-weight="900" font-size="36" fill="#FFD84D">{html.escape(tag)}</text>',
           f'<text x="{W-80}" y="142" text-anchor="end" font-family="{FONT}" font-weight="700" font-size="34" fill="#2B2B2B" opacity="0.55">{page}/{total}</text>']
    if kind == "cover":
        y, weight, gap = 470, 900, 1.35
    else:
        y, weight, gap = 340, 700, 1.55
    for text, size, color in slide["lines"]:
        if text == "":
            y += 40
            continue
        fill = COLORS.get(color, color)
        out.append(f'<text x="80" y="{y}" font-family="{FONT}" font-weight="{weight}" font-size="{size}" fill="{fill}">{html.escape(text)}</text>')
        y += int(size * gap)
    out.append(f'<text x="80" y="{H-90}" font-family="{FONT}" font-weight="900" font-size="38" fill="#2B2B2B">썰배달</text>')
    out.append(f'<text x="{W-80}" y="{H-90}" text-anchor="end" font-family="{FONT}" font-weight="500" font-size="30" fill="#2B2B2B" opacity="0.6">@sseol.delivery</text>')
    out.append('</svg>')
    return "\n".join(out)


def main(spec_path, outdir):
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    slides = spec["slides"]
    tag = spec.get("tag", "오늘의 썰")
    os.makedirs(outdir, exist_ok=True)
    for i, slide in enumerate(slides, 1):
        svg = os.path.join(outdir, f"{i:02d}.svg")
        png = os.path.join(outdir, f"{i:02d}.png")
        with open(svg, "w", encoding="utf-8") as f:
            f.write(render(slide, i, len(slides), tag, os.path.dirname(os.path.abspath(spec_path))))
        subprocess.run(["rsvg-convert", "-w", str(W), "-h", str(H), svg, "-o", png], check=True)
        Image.open(png).convert("RGB").save(os.path.join(outdir, f"{i:02d}.jpg"), "JPEG", quality=92)
        os.remove(svg)
        os.remove(png)
    print(f"{len(slides)} cards -> {outdir}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
