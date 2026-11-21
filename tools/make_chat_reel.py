"""썰배달 메신저 대화형 릴스 생성기.

사용법: python3 tools/make_chat_reel.py chat.json out.mp4
chat.json:
{
  "title": ["내 택배 뜯어서", "이틀 쓴 아랫집"],   # 위쪽 고정 제목 (마지막 줄 노란 강조)
  "partner": "102호 아저씨",                       # 대화방 이름
  "messages": [
    {"t": "sys", "text": "배송완료인데 집 앞에 없음 📦"},   # 상황 설명(가운데 회색 알약)
    {"t": "me",  "text": "저기요 이거 제 택배인데요"},
    {"t": "them","text": "우리 집 앞에 있길래 우리 건 줄"}
  ],
  "ending": ["너네라면", "그냥 넘어가?"],
  "cta": "이런 이웃 겪어본 친구한테 보내기"
}
- 실제 대화 캡처가 아니라 사연을 재구성한 화면이므로 화면에 항상 "사연 내용 재구성" 표시가 붙는다.
- 1080x1920, 30fps, 무음.
"""
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
NOTO = "/usr/share/fonts/opentype/noto/NotoSansCJK-{}.ttc"
TITLE_TTF = os.path.expanduser("~/.fonts/BlackHanSans-Regular.ttf")

BG = (178, 199, 217)
ME = (254, 229, 0)
THEM = (255, 255, 255)
DARK = (30, 30, 30)

HEADER_H = 430          # 제목 + 대화방 바
CHAT_TOP = HEADER_H + 30
CHAT_BOTTOM = H - 140
PAD = 48


def noto(size, weight="Medium"):
    return ImageFont.truetype(NOTO.format(weight), size, index=1)


def title_font(size):
    return ImageFont.truetype(TITLE_TTF, size)


def wrap(text, font, maxw):
    """\\n 은 강제 줄바꿈, 나머지는 단어(띄어쓰기) 단위로 줄바꿈. 이모지는 폰트에 없어 쓰지 않는다."""
    out = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            cand = (cur + " " + word).strip()
            if font.getlength(cand) <= maxw or not cur:
                cur = cand
            else:
                out.append(cur)
                cur = word
        if cur:
            out.append(cur)
    return out


def render_bubble(msg):
    """메시지 하나를 RGBA 이미지로. (이미지, 정렬)"""
    kind = msg["t"]
    if kind == "sys":
        f = noto(40, "Bold")
        lines = wrap(msg["text"], f, 820)
        lh = 56
        w = int(max(f.getlength(l) for l in lines)) + 64
        h = lh * len(lines) + 36
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2 if len(lines) == 1 else 32, fill=(0, 0, 0, 120))
        for i, l in enumerate(lines):
            d.text((w // 2, 18 + lh * i + lh // 2), l, font=f, fill="white", anchor="mm")
        return im, "center"
    f = noto(48, "Medium")
    lines = wrap(msg["text"], f, 700)
    lh = 66
    tw = int(max(f.getlength(l) for l in lines))
    bw, bh = tw + 64, lh * len(lines) + 40
    color = ME if kind == "me" else THEM
    if kind == "them":
        av = 110
        w, h = av + 22 + bw, max(bh + 56, av)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, av, av), radius=40, fill=(160, 175, 190))
        d.ellipse((30, 18, 80, 68), fill=(235, 240, 245))
        d.rounded_rectangle((18, 72, 92, 110), radius=18, fill=(235, 240, 245))
        d.text((av + 26, 0), msg.get("name", ""), font=noto(34, "Regular"), fill=(60, 60, 60))
        x0, y0 = av + 22, 52
        d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=34, fill=color)
        for i, l in enumerate(lines):
            d.text((x0 + 32, y0 + 20 + lh * i), l, font=f, fill=DARK)
        return im, "left"
    w, h = bw, bh
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, bw, bh), radius=34, fill=color)
    for i, l in enumerate(lines):
        d.text((32, 20 + lh * i), l, font=f, fill=DARK)
    return im, "right"


def typing_bubble(phase):
    av = 110
    im = Image.new("RGBA", (av + 22 + 170, 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, av, av), radius=40, fill=(160, 175, 190))
    d.ellipse((30, 18, 80, 68), fill=(235, 240, 245))
    d.rounded_rectangle((18, 72, 92, 110), radius=18, fill=(235, 240, 245))
    x0, y0 = av + 22, 52
    d.rounded_rectangle((x0, y0, x0 + 170, y0 + 100), radius=34, fill=THEM)
    for i in range(3):
        on = (int(phase * 3) % 3) == i
        c = (90, 90, 90) if on else (190, 190, 190)
        cx = x0 + 45 + i * 40
        d.ellipse((cx - 11, y0 + 39, cx + 11, y0 + 61), fill=c)
    return im


def header(spec, progress):
    im = Image.new("RGBA", (W, HEADER_H), (34, 34, 34, 255))
    d = ImageDraw.Draw(im)
    tf = title_font(96)
    y = 70
    for i, line in enumerate(spec["title"]):
        col = (255, 216, 77) if i == len(spec["title"]) - 1 else (255, 255, 255)
        d.text((W // 2, y + 50), line, font=tf, fill=col, anchor="mm")
        y += 110
    # 대화방 바
    bar_y = HEADER_H - 100
    d.rectangle((0, bar_y, W, HEADER_H), fill=BG)
    d.text((PAD, bar_y + 50), "‹", font=noto(64, "Regular"), fill=DARK, anchor="lm")
    d.text((PAD + 60, bar_y + 50), spec["partner"], font=noto(42, "Bold"), fill=DARK, anchor="lm")
    d.text((W - PAD, bar_y + 50), "사연 내용 재구성", font=noto(30, "Regular"), fill=(70, 80, 90), anchor="rm")
    # 진행 막대
    d.rectangle((0, HEADER_H - 8, int(W * progress), HEADER_H), fill=(255, 216, 77))
    return im


def footer(frame):
    d = ImageDraw.Draw(frame)
    d.rectangle((0, H - 120, W, H), fill=(255, 255, 255))
    d.rounded_rectangle((PAD, H - 98, W - 200, H - 22), radius=38, fill=(240, 240, 240))
    d.rounded_rectangle((W - 170, H - 98, W - PAD, H - 22), radius=38, fill=ME)
    d.text((W - 109, H - 60), "썰배달", font=noto(30, "Bold"), fill=DARK, anchor="mm")


def make_cover(spec, photo_path, out_jpg):
    """릴스 표지(1080x1920 JPEG). 프로필 격자에서는 가운데 3:4 정도만 보이므로 제목을 가운데에 둔다."""
    im = Image.open(photo_path).convert("RGB")
    r = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * r + 1), int(im.height * r + 1)), Image.LANCZOS)
    left, top = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((left, top, left + W, top + H)).convert("RGBA")
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for y in range(H):  # 가운데로 갈수록 어둡게
        a = int(70 + 130 * (1 - abs(y - H * 0.52) / (H * 0.52)))
        sd.line((0, y, W, y), fill=(0, 0, 0, max(70, min(200, a))))
    im.alpha_composite(shade)
    d = ImageDraw.Draw(im)
    tf = title_font(150)
    lines = spec.get("cover_title", spec["title"])
    lh = 175
    y = H // 2 - lh * len(lines) // 2 + lh // 2
    for i, line in enumerate(lines):
        col = (255, 216, 77) if i == len(lines) - 1 else (255, 255, 255)
        d.text((W // 2, y), line, font=tf, fill=col, anchor="mm", stroke_width=6, stroke_fill=(0, 0, 0))
        y += lh
    # 말풍선 배지 (대화형 릴스라는 표시)
    by = H // 2 - lh * len(lines) // 2 - 150
    d.rounded_rectangle((W // 2 - 190, by, W // 2 + 190, by + 96), radius=48, fill=ME)
    d.text((W // 2, by + 48), "카톡으로 보는 썰", font=noto(42, "Bold"), fill=DARK, anchor="mm")
    d.rounded_rectangle((W // 2 - 130, y + 20, W // 2 + 130, y + 100), radius=40, fill=(34, 34, 34))
    d.text((W // 2, y + 60), "썰배달", font=title_font(50), fill=(255, 216, 77), anchor="mm")
    im.convert("RGB").save(out_jpg, "JPEG", quality=92)


def main(spec_path, out):
    with open(spec_path, encoding="utf-8") as fp:
        spec = json.load(fp)
    for m in spec["messages"]:
        if m["t"] == "them":
            m.setdefault("name", spec["partner"])

    # 타임라인: 각 메시지 (등장시각, 이미지, 정렬, 높이), them 앞에는 입력중 표시
    events, t = [], 1.2
    for m in spec["messages"]:
        img, align = render_bubble(m)
        if m["t"] == "them":
            events.append({"start": t, "typing": True, "dur": 0.7})
            t += 0.7
        events.append({"start": t, "img": img, "align": align})
        read = 0.9 + len(m["text"]) * 0.055
        t += min(max(read, 1.3), 2.6)
    end_start = t + 0.3
    total = end_start + 3.2
    nframes = int(total * FPS)

    tmp = tempfile.mkdtemp(prefix="chat_")
    gap = 26
    for fi in range(nframes):
        now = fi / FPS
        frame = Image.new("RGBA", (W, H), BG + (255,))
        # 보이는 메시지
        shown = [e for e in events if "img" in e and e["start"] <= now]
        typing = [e for e in events if e.get("typing") and e["start"] <= now < e["start"] + e["dur"]]
        heights = [e["img"].height for e in shown] + ([160] if typing else [])
        total_h = sum(heights) + gap * len(heights)
        avail = CHAT_BOTTOM - CHAT_TOP
        y = CHAT_TOP + min(0, avail - total_h)
        for e in shown:
            img = e["img"]
            age = now - e["start"]
            p = min(1.0, age / 0.18)
            s = 0.8 + 0.2 * p
            im2 = img if p >= 1 else img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))))
            if e["align"] == "left":
                x = PAD
            elif e["align"] == "right":
                x = W - PAD - im2.width
            else:
                x = (W - im2.width) // 2
            if y + img.height > CHAT_TOP - 200:
                frame.alpha_composite(im2, (int(x), int(y + (img.height - im2.height) / 2)))
            y += img.height + gap
        if typing:
            frame.alpha_composite(typing_bubble(now * 2), (PAD, int(y)))
        footer(frame)
        frame.alpha_composite(header(spec, min(1.0, now / total)), (0, 0))
        # 엔딩 오버레이
        if now >= end_start:
            p = min(1.0, (now - end_start) / 0.3)
            ov = Image.new("RGBA", (W, H), (0, 0, 0, int(200 * p)))
            d = ImageDraw.Draw(ov)
            tf = title_font(130)
            yy = H // 2 - 160
            for i, line in enumerate(spec["ending"]):
                col = (255, 216, 77, int(255 * p))
                d.text((W // 2, yy), line, font=tf, fill=col, anchor="mm")
                yy += 160
            if spec.get("cta"):
                d.text((W // 2, yy + 60), spec["cta"], font=noto(46, "Bold"), fill=(255, 255, 255, int(255 * p)), anchor="mm")
            frame.alpha_composite(ov)
        frame.convert("RGB").save(os.path.join(tmp, f"{fi:05d}.jpg"), quality=90)
    silent = os.path.join(tmp, "silent.mp4")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(tmp, "%05d.jpg"),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", silent], check=True)

    # 소리: 배경음악 + 말풍선 효과음 + 입력중 타자음 + 엔딩 효과음
    assets = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
    cues = []  # (파일, 시작초, 길이 또는 None, 볼륨)
    for e in events:
        if e.get("typing"):
            cues.append(("sfx/typing.mp3", e["start"], e["dur"], 0.35))
        elif e["align"] == "right":
            cues.append(("sfx/pop.mp3", e["start"], None, 0.7))
        elif e["align"] == "left":
            cues.append(("sfx/pop2.mp3", e["start"], None, 0.7))
        else:
            cues.append(("sfx/plop.mp3", e["start"], None, 0.6))
    cues.append(("sfx/ding.mp3", end_start, None, 0.8))
    bgm = os.path.join(assets, "bgm", spec.get("bgm", "good_vibe.mp3"))
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", silent, "-stream_loop", "-1", "-i", bgm]
    for f, _, _, _ in cues:
        cmd += ["-i", os.path.join(assets, f)]
    parts = [f"[1:a]atrim=0:{total:.2f},volume={spec.get('bgm_volume', 0.35)},afade=t=in:d=0.6,afade=t=out:st={total - 1.5:.2f}:d=1.5[bg]"]
    labels = ["[bg]"]
    for i, (f, start, dur, vol) in enumerate(cues):
        trim = f"atrim=0:{dur:.2f}," if dur else ""
        ms = int(start * 1000)
        parts.append(f"[{i + 2}:a]{trim}volume={vol},adelay={ms}|{ms}[c{i}]")
        labels.append(f"[c{i}]")
    parts.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first,atrim=0:{total:.2f},loudnorm=I=-15:TP=-1.5:LRA=11[aout]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[aout]", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    print(f"{out} ({total:.1f}s, {len(cues)} sfx)")
    if spec.get("cover_photo"):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cp = spec["cover_photo"] if os.path.isabs(spec["cover_photo"]) else os.path.join(root, spec["cover_photo"])
        cover = os.path.splitext(out)[0] + "_cover.jpg"
        make_cover(spec, cp, cover)
        print(f"cover: {cover}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
