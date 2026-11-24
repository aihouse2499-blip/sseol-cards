"""썰배달 '진짜 카톡 화면' 릴스 생성기 (1:1 대화, 등장인물 2명).

사용법: python3 tools/make_kakao_reel.py chat.json out.mp4
chat.json:
{
  "hook": ["프러포즈 해놓고", "비용 N빵 청구한 남친"],   # 첫 2초 큰 자막 (마지막 줄 노란 강조)
  "teaser": 13,      # (권장) 첫 화면에 미리 보여줄 결정적인 말풍선 번호(messages 의 0부터 센 위치). 결말 한 줄을 먼저 보여주고 처음부터 재생
  "cover_title": ["프러포즈 비용", "N빵 청구한", "남친"],    # 표지용 (없으면 hook)
  "cover_photo": "cards/<폴더>/cover_photo.jpg",
  "partner": "남자친구",            # 대화방 이름 = 상대 이름 (등장인물은 나 + 상대 2명만)
  "mood": "funny",                  # 배경음악 분위기 (make_chat_reel.py 와 같은 자동 선택)
  "messages": [
    {"t": "notice", "text": "결혼 자금도 반반 하기로 한 커플"},   # 가운데 회색 안내(날짜 구분선 모양)
    {"t": "them", "text": "이번 주말에 호캉스 갈래?"},
    {"t": "me", "text": "좋아"},
    {"t": "settle", "title": "정산 요청", "items": ["호텔 1박", "생화 장식"], "note": "1/2 정산"},  # 카카오 정산 카드
    {"t": "transfer", "text": "송금 완료"},      # 내가 보낸 송금 카드 ("from": "them" 이면 상대가 보낸 송금)
  ],
  "ending": ["너라면", "결혼한다 vs 파혼한다"],
  "cta": "반반 커플 친구한테 보내기"
}
- 실제 대화 캡처가 아니라 사연을 재구성한 화면이므로 위쪽에 항상 "사연 내용 재구성" 표시가 붙는다.
- 시간·날짜처럼 기사에 없는 정보는 화면에 넣지 않는다.
- v3(2026-11-24): 훅 1.4초, 말풍선 글자 62px, 빠른 진행. 목표 12~16초 = 말풍선 7~9개 + notice 1~2개, 말풍선 하나 20자 안팎.
"""
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_chat_reel import make_cover, pick_bgm, title_font  # noqa: E402

W, H, FPS = 1080, 1920, 30
NOTO = "/usr/share/fonts/opentype/noto/NotoSansCJK-{}.ttc"

KBG = (186, 206, 224)        # 카톡 기본 배경
YEL = (254, 229, 0)
WHITE = (255, 255, 255)
TXT = (25, 25, 25)
GRAY = (90, 100, 110)

STATUS_H = 90
HEAD_H = 140
TOP = STATUS_H + HEAD_H
INPUT_H = 150
SIDE = 34
AV = 118
FS = 62
LH = 82
MAXW = 730


def font(size, w="Regular"):
    return ImageFont.truetype(NOTO.format(w), size, index=1)


def wrap(text, f, maxw):
    out = []
    for para in text.split("\n"):
        cur = ""
        for ch_word in para.split(" "):
            cand = (cur + " " + ch_word).strip()
            if f.getlength(cand) <= maxw or not cur:
                cur = cand
            else:
                out.append(cur)
                cur = ch_word
        if cur:
            out.append(cur)
    return out


def bubble_shape(d, x0, y0, x1, y1, color, tail):
    d.rounded_rectangle((x0, y0, x1, y1), radius=30, fill=color)
    if tail == "left":
        d.polygon([(x0 + 6, y0 + 14), (x0 - 16, y0 + 8), (x0 + 6, y0 + 44)], fill=color)
    elif tail == "right":
        d.polygon([(x1 - 6, y0 + 14), (x1 + 16, y0 + 8), (x1 - 6, y0 + 44)], fill=color)


def default_avatar(size=AV):
    """카톡 기본 프로필(회청색 스퀴클 + 흰 사람 실루엣)."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=int(size * 0.38), fill=(155, 188, 220))
    s = size / 118
    d.ellipse((38 * s, 22 * s, 80 * s, 64 * s), fill=(225, 236, 247))
    d.pieslice((20 * s, 70 * s, 98 * s, 150 * s), 180, 360, fill=(225, 236, 247))
    return im


def content_size(m):
    """말풍선 안 내용 (w, h, draw_fn)."""
    t = m["t"]
    if t in ("me", "them"):
        f = font(FS)
        lines = wrap(m["text"], f, MAXW)
        w = int(max(f.getlength(l) for l in lines)) + 56
        h = LH * len(lines) + 34

        def draw(d, x, y):
            for i, l in enumerate(lines):
                d.text((x + 28, y + 15 + LH * i), l, font=f, fill=TXT)
        return w, h, draw
    if t == "settle":
        fb, fr = font(40, "Bold"), font(38)
        items = m.get("items", [])
        w = 600
        h = 120 + 58 * len(items) + (80 if m.get("note") else 0) + 100

        def draw(d, x, y):
            d.rounded_rectangle((x, y, x + w, y + 110), radius=30, fill=YEL)
            d.rectangle((x, y + 60, x + w, y + 110), fill=YEL)
            d.text((x + 34, y + 55), m.get("title", "정산 요청"), font=fb, fill=TXT, anchor="lm")
            d.ellipse((x + w - 90, y + 28, x + w - 34, y + 84), outline=TXT, width=5)
            d.text((x + w - 62, y + 56), "₩", font=font(32, "Bold"), fill=TXT, anchor="mm")
            yy = y + 140
            for it in items:
                d.text((x + 34, yy), "· " + it, font=fr, fill=(60, 60, 60))
                yy += 58
            if m.get("note"):
                d.text((x + 34, yy + 10), m["note"], font=font(40, "Bold"), fill=TXT)
                yy += 80
            d.line((x, yy + 6, x + w, yy + 6), fill=(230, 230, 230), width=2)
            d.text((x + w // 2, yy + 52), m.get("button", "정산하기"), font=font(38, "Medium"), fill=TXT, anchor="mm")
        return w, h, draw
    if t == "transfer":
        w, h = 520, 210

        def draw(d, x, y):
            d.text((x + 34, y + 40), "송금", font=font(36), fill=(80, 70, 0))
            d.text((x + 34, y + 92), m.get("text", "송금 완료"), font=font(48, "Bold"), fill=TXT)
            d.ellipse((x + w - 110, y + 52, x + w - 34, y + 128), fill=(255, 255, 255))
            d.text((x + w - 72, y + 90), "₩", font=font(40, "Bold"), fill=TXT, anchor="mm")
        return w, h, draw
    raise ValueError(t)


def render_item(m, first_in_group, partner):
    """메시지 하나 → (RGBA 이미지, x 위치)"""
    t = m["t"]
    if t == "notice":
        f = font(36)
        lines = wrap(m["text"], f, 820)
        lh = 50
        w = int(max(f.getlength(l) for l in lines)) + 70
        h = lh * len(lines) + 30
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=min(h // 2, 34), fill=(0, 0, 0, 38))
        for i, l in enumerate(lines):
            d.text((w // 2, 15 + lh * i + lh // 2), l, font=f, fill=(255, 255, 255), anchor="mm")
        return im, (W - w) // 2
    mine = t == "me" or (t == "transfer" and m.get("from") != "them")
    cw, ch, draw = content_size(m)
    color = YEL if (mine and t == "me") or t == "transfer" else WHITE
    if t == "settle":
        color = WHITE
    if mine:
        im = Image.new("RGBA", (cw + 20, ch), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        bubble_shape(d, 0, 0, cw, ch, color, "right" if first_in_group else None)
        draw(d, 0, 0)
        return im, W - SIDE - cw - 4
    # 상대
    name_h = 56 if first_in_group else 0
    im = Image.new("RGBA", (AV + 30 + cw, max(ch + name_h, AV if first_in_group else 0)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if first_in_group:
        im.alpha_composite(default_avatar(), (0, 0))
        d.text((AV + 26, 0), partner, font=font(36), fill=(70, 75, 80))
    bx = AV + 26
    bubble_shape(d, bx, name_h, bx + cw, name_h + ch, color, "left" if first_in_group else None)
    draw(d, bx, name_h)
    return im, SIDE


def battery_icons(d):
    # 상태바 아이콘 (시계는 넣지 않음)
    x = W - 60
    d.rounded_rectangle((x - 70, 30, x, 62), radius=8, outline=TXT, width=4)
    d.rectangle((x - 64, 36, x - 20, 56), fill=TXT)
    d.rectangle((x + 4, 40, x + 9, 52), fill=TXT)
    for i in range(4):
        hh = 10 + i * 7
        d.rectangle((x - 210 + i * 16, 62 - hh, x - 200 + i * 16, 62), fill=TXT)
    cx, cy = x - 115, 62
    for r in (34, 23, 12):
        d.arc((cx - r, cy - r, cx + r, cy + r), 225, 315, fill=TXT, width=6)


def chrome(spec):
    """고정 UI (상태바+헤더, 입력창) 레이어"""
    top = Image.new("RGBA", (W, TOP), KBG + (255,))
    d = ImageDraw.Draw(top)
    battery_icons(d)
    d.text((SIDE + 10, STATUS_H + HEAD_H // 2 - 4), "‹", font=font(90, "Light"), fill=TXT, anchor="lm")
    d.text((SIDE + 80, STATUS_H + HEAD_H // 2), spec["partner"], font=font(48, "Bold"), fill=TXT, anchor="lm")
    # 돋보기, 메뉴
    sx, sy = W - 190, STATUS_H + HEAD_H // 2
    d.ellipse((sx - 24, sy - 28, sx + 20, sy + 16), outline=TXT, width=6)
    d.line((sx + 14, sy + 10, sx + 34, sy + 30), fill=TXT, width=7)
    mx = W - 90
    for i in (-18, 0, 18):
        d.line((mx - 26, sy + i, mx + 26, sy + i), fill=TXT, width=6)
    # 재구성 표시 (상태바 왼쪽)
    d.rounded_rectangle((SIDE, 24, SIDE + 300, 70), radius=23, fill=(0, 0, 0, 60))
    d.text((SIDE + 150, 47), "사연 내용 재구성", font=font(28, "Medium"), fill=WHITE, anchor="mm")

    bot = Image.new("RGBA", (W, INPUT_H), WHITE + (255,))
    d = ImageDraw.Draw(bot)
    d.rounded_rectangle((SIDE, 30, SIDE + 66, 96), radius=12, outline=(120, 120, 120), width=5)
    d.line((SIDE + 33, 46, SIDE + 33, 80), fill=(120, 120, 120), width=5)
    d.line((SIDE + 16, 63, SIDE + 50, 63), fill=(120, 120, 120), width=5)
    d.rounded_rectangle((SIDE + 100, 22, W - 220, 104), radius=41, fill=(243, 243, 243))
    ex = W - 170
    d.ellipse((ex - 30, 33, ex + 30, 93), outline=(120, 120, 120), width=5)
    d.ellipse((ex - 14, 52, ex - 6, 60), fill=(120, 120, 120))
    d.ellipse((ex + 6, 52, ex + 14, 60), fill=(120, 120, 120))
    d.arc((ex - 16, 52, ex + 16, 80), 20, 160, fill=(120, 120, 120), width=5)
    d.text((W - 80, 63), "#", font=font(56, "Medium"), fill=(120, 120, 120), anchor="mm")
    return top, bot


def main(spec_path, out):
    with open(spec_path, encoding="utf-8") as fp:
        spec = json.load(fp)
    msgs = spec["messages"]
    side = lambda m: ("them" if m.get("from") == "them" else "me") if m["t"] == "transfer" else (
        "me" if m["t"] == "me" else ("them" if m["t"] in ("them", "settle") else "n"))

    items, prev = [], None
    for m in msgs:
        s = side(m)
        img, x = render_item(m, s != prev, spec["partner"])
        gap_before = 14 if s == prev and s != "n" else 34
        items.append({"img": img, "x": x, "gap": gap_before, "side": s, "m": m})
        prev = s

    hook_end = float(spec.get("hook_sec", 1.4))   # v3: 첫 화면은 짧고 강하게
    # 티저: 결정적인 말풍선(예: 상대의 막말)을 첫 화면에 먼저 보여주고 처음부터 대화를 재생 (open loop)
    teaser = None
    if spec.get("teaser") is not None:
        tm = dict(msgs[spec["teaser"]])
        timg, _ = render_item(tm, False, spec["partner"])
        if timg.width > 0:
            # 아바타 자리 여백 잘라내고 1.3배 확대
            bbox = timg.getbbox()
            timg = timg.crop(bbox)
            teaser = timg.resize((int(timg.width * 1.3), int(timg.height * 1.3)), Image.LANCZOS)
    t = hook_end + 0.2
    for it in items:
        it["start"] = t
        m = it["m"]
        n = len(m.get("text", "")) + 12 * len(m.get("items", []))
        t += min(max(0.6 + n * 0.035, 0.9), 1.7)   # v3: 빠른 진행 (목표 12~16초)
    end_start = t + 0.3
    total = end_start + 2.2

    top, bot = chrome(spec)
    area_top, area_bot = TOP + 20, H - INPUT_H - 24
    tmp = tempfile.mkdtemp(prefix="kakao_")
    nframes = int(total * FPS)
    # 스크롤: 내용 끝이 area_bot 넘으면 부드럽게 올림
    scroll = 0.0
    for fi in range(nframes):
        now = fi / FPS
        frame = Image.new("RGBA", (W, H), KBG + (255,))
        shown = [it for it in items if it["start"] <= now]
        y = area_top
        pos = []
        for it in shown:
            y += it["gap"]
            pos.append(y)
            y += it["img"].height
        target = max(0.0, y - area_bot)
        scroll += (target - scroll) * 0.35 if abs(target - scroll) > 1 else (target - scroll)
        for it, py in zip(shown, pos):
            age = now - it["start"]
            p = min(1.0, age / 0.15)
            img = it["img"]
            yy = py - scroll + (1 - p) * 30
            if yy + img.height < TOP - 10 or yy > H:
                continue
            if p < 1:
                img = img.copy()
                img.putalpha(img.getchannel("A").point(lambda v: int(v * p)))
            frame.alpha_composite(img, (int(it["x"]), int(yy)))
        frame.alpha_composite(top, (0, 0))
        frame.alpha_composite(bot, (0, H - INPUT_H))
        d = ImageDraw.Draw(frame)
        # 첫 화면 훅 자막
        if now < hook_end + 0.3:
            a = 1.0 if now < hook_end else 1 - (now - hook_end) / 0.3
            ov = Image.new("RGBA", (W, H), (0, 0, 0, int(215 * a)))
            if teaser is not None:
                ti = teaser.copy()
                ti.putalpha(ti.getchannel("A").point(lambda v: int(v * a)))
                pop = min(1.0, now / 0.25)
                tw = max(1, int(ti.width * (0.85 + 0.15 * pop)))
                ti = ti.resize((tw, max(1, int(ti.height * tw / ti.width))))
                ov.alpha_composite(ti, ((W - ti.width) // 2, int(H * 0.56)))
            od = ImageDraw.Draw(ov)
            lines = spec["hook"]
            sz = 140
            while max(title_font(sz).getlength(l) for l in lines) > W - 80:
                sz -= 6
            tf = title_font(sz)
            yy = (int(H * 0.50) - 140 * len(lines)) if teaser is not None else H // 2 - 70 * len(lines)
            for i, line in enumerate(lines):
                col = (255, 216, 77) if i == len(lines) - 1 else (255, 255, 255)
                od.text((W // 2, yy + 70), line, font=tf, fill=col + (int(255 * a),), anchor="mm",
                        stroke_width=6, stroke_fill=(0, 0, 0, int(255 * a)))
                yy += 140
            frame.alpha_composite(ov)
        if now >= end_start:
            p = min(1.0, (now - end_start) / 0.3)
            ov = Image.new("RGBA", (W, H), (0, 0, 0, int(238 * p)))
            od = ImageDraw.Draw(ov)
            yy = H // 2 - 170
            for line in spec["ending"]:
                sz = 120
                while title_font(sz).getlength(line) > W - 100:
                    sz -= 6
                tf = title_font(sz)
                od.text((W // 2, yy), line, font=tf, fill=(255, 216, 77, int(255 * p)), anchor="mm")
                yy += 155
            if spec.get("cta"):
                od.text((W // 2, yy + 50), spec["cta"], font=font(46, "Bold"), fill=(255, 255, 255, int(255 * p)), anchor="mm")
            frame.alpha_composite(ov)
        frame.convert("RGB").save(os.path.join(tmp, f"{fi:05d}.jpg"), quality=90)

    silent = os.path.join(tmp, "silent.mp4")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(tmp, "%05d.jpg"),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", silent], check=True)

    assets = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
    cues = []
    for it in items:
        f = {"me": "sfx/pop.mp3", "them": "sfx/pop2.mp3"}.get(it["side"], "sfx/plop.mp3")
        cues.append((f, it["start"], 0.7))
    cues.append(("sfx/ding.mp3", end_start, 0.8))
    cues.append(("sfx/pop.mp3", 0.02, 1.0))   # v3: 첫 프레임 효과음
    bgm_name = pick_bgm(spec, assets)
    print("bgm:", bgm_name)
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", silent, "-stream_loop", "-1", "-i", os.path.join(assets, "bgm", bgm_name)]
    for f, _, _ in cues:
        cmd += ["-i", os.path.join(assets, f)]
    parts = [f"[1:a]atrim=0:{total:.2f},loudnorm=I=-16,volume={spec.get('bgm_volume', 0.35)},afade=t=in:d=0.6,afade=t=out:st={total - 1.5:.2f}:d=1.5[bg]"]
    labels = ["[bg]"]
    for i, (f, start, vol) in enumerate(cues):
        ms = int(start * 1000)
        parts.append(f"[{i + 2}:a]volume={vol},adelay={ms}|{ms}[c{i}]")
        labels.append(f"[c{i}]")
    parts.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first,atrim=0:{total:.2f},loudnorm=I=-15:TP=-1.5:LRA=11[aout]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[aout]", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    print(f"{out} ({total:.1f}s)")
    if spec.get("cover_photo"):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cp = spec["cover_photo"] if os.path.isabs(spec["cover_photo"]) else os.path.join(root, spec["cover_photo"])
        spec.setdefault("title", spec["hook"])
        cover = os.path.splitext(out)[0] + "_cover.jpg"
        make_cover(spec, cp, cover)
        print("cover:", cover)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
