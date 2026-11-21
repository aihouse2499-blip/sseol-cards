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
"""
import html
import json
import os
import subprocess
import sys

from PIL import Image

W, H = 1080, 1350
FONT = "Noto Sans CJK KR"
COLORS = {"dark": "#2B2B2B", "red": "#E5484D"}


def render(slide, page, total, tag):
    kind = slide["kind"]
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
            f.write(render(slide, i, len(slides), tag))
        subprocess.run(["rsvg-convert", "-w", str(W), "-h", str(H), svg, "-o", png], check=True)
        Image.open(png).convert("RGB").save(os.path.join(outdir, f"{i:02d}.jpg"), "JPEG", quality=92)
        os.remove(svg)
        os.remove(png)
    print(f"{len(slides)} cards -> {outdir}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
