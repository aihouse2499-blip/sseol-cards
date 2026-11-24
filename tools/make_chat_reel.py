"""썰배달 메신저 대화형 릴스 생성기.

사용법: python3 tools/make_chat_reel.py chat.json out.mp4
chat.json:
{
  "hook": ["같은 빌라 살면서", "무슨 돈 얘기를 해"],  # (필수) 첫 1.3초 전체 화면 훅. 가장 황당한 대사·장면, 결론은 말하지 않기
  "hook_sub": "내 택배 이틀 쓴 아랫집이 한 말",      # (선택) 훅 아래 작은 설명
  "title": ["내 택배 뜯어서", "이틀 쓴 아랫집"],   # 위쪽 고정 제목 (마지막 줄 노란 강조)
  "partner": "102호 아저씨",                       # 대화방 이름
  "messages": [
    {"t": "sys", "text": "배송완료인데 집 앞에 없음 📦"},   # 상황 설명(가운데 회색 알약)
    {"t": "me",  "text": "저기요 이거 제 택배인데요"},
    {"t": "them","text": "우리 집 앞에 있길래 우리 건 줄"}
  ],
  "ending": ["너네라면", "그냥 넘어가?"],
  "cta": "이런 이웃 겪어본 친구한테 보내기",
  "setup": "택배가 사라진 날, 아랫집에서 발견",          # (권장) 첫 화면 한 줄 상황 설명
  "me_name": "나",                                       # 노란 말풍선 위 이름표
  "me_desc": "택배 주인",                                # (권장) 첫 화면에서 '나'가 누구인지
  # me 메시지에 "to": "조카" 를 주면 이름표가 "나 → 조카"로 바뀐다(단톡방에서 누구한테 하는 말인지)
  "cast": [{"name": "102호 아저씨", "desc": "아랫집 이웃"}],  # (권장) 첫 화면 등장인물 소개
  "mood": "funny"   # 배경음악 분위기: funny / daily / warm / serious. "bgm"을 직접 지정하지 않으면
                    # 분위기에 맞는 곡 중 최근에 덜 쓴 곡을 자동으로 고른다(assets/bgm/history.txt)
}
- them 메시지에 "name"을 주면 그 사람 이름표와 전용 색 아바타(이름 첫 글자)가 붙는다. 단톡방처럼 여러 명 가능.
- 실제 대화 캡처가 아니라 사연을 재구성한 화면이므로 화면에 항상 "사연 내용 재구성" 표시가 붙는다.
- 1080x1920, 30fps. 목표 길이 12~15초: 말풍선 7~9개, 상황 설명(sys) 1~2개, 한 말풍선 20자 안팎.
- 등장인물 카드는 기본으로 꺼져 있다("intro": true 일 때만). 첫 화면은 항상 hook.
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

AVATAR_COLORS = [(244, 143, 177), (129, 199, 132), (100, 181, 246), (255, 183, 77), (186, 104, 200), (77, 182, 172)]
SPEAKER_COLOR = {}

MOOD_BGM = {
    "funny": ["good_vibe.mp3", "happy_taps.mp3", "happy_strings.mp3", "acoustic_upbeat.mp3", "sims_beat.mp3"],
    "daily": ["lofi_loafy.mp3", "lofi_melody.mp3", "lofi_organ.mp3", "jazz_piano.mp3", "sims_beat.mp3"],
    "warm": ["cute_loop.mp3", "acoustic_orchestra.mp3", "happy_strings.mp3"],
    "serious": ["piano_suspense.mp3", "jazz_piano.mp3", "lofi_organ.mp3"],
}

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


def draw_avatar(d, name, av=110):
    col = SPEAKER_COLOR.setdefault(name, AVATAR_COLORS[len(SPEAKER_COLOR) % len(AVATAR_COLORS)])
    d.rounded_rectangle((0, 0, av, av), radius=40, fill=col)
    ch = (name or "?").strip()[:1]
    d.text((av // 2, av // 2 + 2), ch, font=noto(58, "Bold"), fill="white", anchor="mm")


def render_bubble(msg):
    """메시지 하나를 RGBA 이미지로. (이미지, 정렬)"""
    kind = msg["t"]
    if kind == "sys":
        f = noto(50, "Bold")
        lines = wrap(msg["text"], f, 900)
        lh = 68
        w = int(max(f.getlength(l) for l in lines)) + 64
        h = lh * len(lines) + 36
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2 if len(lines) == 1 else 32, fill=(0, 0, 0, 120))
        for i, l in enumerate(lines):
            d.text((w // 2, 18 + lh * i + lh // 2), l, font=f, fill="white", anchor="mm")
        return im, "center"
    f = noto(68, "Bold")
    lines = wrap(msg["text"], f, 740)
    lh = 90
    tw = int(max(f.getlength(l) for l in lines))
    bw, bh = tw + 64, lh * len(lines) + 40
    color = ME if kind == "me" else THEM
    if kind == "them":
        av = 110
        w, h = av + 22 + bw, max(bh + 56, av)
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        draw_avatar(d, msg.get("name", ""))
        d.text((av + 26, 0), msg.get("name", ""), font=noto(36, "Bold"), fill=(40, 40, 40))
        x0, y0 = av + 22, 52
        d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=40, fill=color)
        for i, l in enumerate(lines):
            d.text((x0 + 32, y0 + 18 + lh * i), l, font=f, fill=DARK)
        return im, "left"
    label = msg.get("label")
    top = 52 if label else 0
    nf = noto(36, "Bold")
    w = max(bw, int(nf.getlength(label)) + 4) if label else bw
    h = bh + top
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if label:
        d.text((w, 0), label, font=nf, fill=(40, 40, 40), anchor="ra")
    d.rounded_rectangle((w - bw, top, w, top + bh), radius=34, fill=color)
    for i, l in enumerate(lines):
        d.text((w - bw + 32, top + 20 + lh * i), l, font=f, fill=DARK)
    return im, "right"


def typing_bubble(phase, name=""):
    av = 110
    im = Image.new("RGBA", (av + 22 + 170, 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    draw_avatar(d, name)
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


def intro_card(spec):
    """첫 화면: 상황 한 줄 + 등장인물(누가 누구인지)."""
    cast = [{"name": "나", "desc": spec.get("me_desc", ""), "me": True}] + spec.get("cast", [])
    im = Image.new("RGBA", (W - 2 * PAD, 10), (0, 0, 0, 0))
    rows = []
    if spec.get("setup"):
        rows.append(("setup", spec["setup"]))
    rows.append(("head", "등장인물"))
    for c in cast:
        rows.append(("cast", c))
    f_setup, f_head, f_name, f_desc = noto(46, "Bold"), noto(36, "Bold"), noto(44, "Bold"), noto(40, "Regular")
    setup_lines = wrap(spec.get("setup", ""), f_setup, W - 2 * PAD - 80) if spec.get("setup") else []
    h = 40 + len(setup_lines) * 64 + (30 if setup_lines else 0) + 60 + len(cast) * 110 + 30
    im = Image.new("RGBA", (W - 2 * PAD, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, im.width - 1, h - 1), radius=40, fill=(255, 255, 255, 235))
    y = 40
    for l in setup_lines:
        d.text((40, y), l, font=f_setup, fill=DARK)
        y += 64
    if setup_lines:
        y += 30
    d.text((40, y), "등장인물", font=f_head, fill=(120, 120, 120))
    y += 60
    for c in cast:
        if c.get("me"):
            d.rounded_rectangle((40, y, 130, y + 90), radius=30, fill=ME)
            d.text((85, y + 45), "나", font=noto(44, "Bold"), fill=DARK, anchor="mm")
            text = "나"
        else:
            sub = Image.new("RGBA", (110, 110), (0, 0, 0, 0))
            draw_avatar(ImageDraw.Draw(sub), c["name"])
            im.alpha_composite(sub.resize((90, 90)), (40, y))
            text = c["name"]
        d.text((160, y + 45), text, font=f_name, fill=DARK, anchor="lm")
        if c.get("desc"):
            x2 = 160 + int(f_name.getlength(text)) + 24
            d.text((x2, y + 47), c["desc"], font=f_desc, fill=(110, 110, 110), anchor="lm")
        y += 110
    return im


def hook_screen(spec, now):
    """첫 1.3초: 가장 황당한 한마디를 화면 가득. 스크롤을 멈추게 하는 용도."""
    im = Image.new("RGBA", (W, H), (18, 18, 18, 255))
    d = ImageDraw.Draw(im)
    p = min(1.0, now / 0.15)
    lines = spec["hook"]
    size = 150
    tf = title_font(size)
    while size > 90 and any(tf.getlength(l) > W - 120 for l in lines):
        size -= 8
        tf = title_font(size)
    lh = int(size * 1.2)
    y = H // 2 - lh * len(lines) // 2 + lh // 2 - 60
    for i, line in enumerate(lines):
        col = (255, 216, 77) if i == len(lines) - 1 else (255, 255, 255)
        d.text((W // 2, y), line, font=tf, fill=col, anchor="mm", stroke_width=6, stroke_fill=(0, 0, 0))
        y += lh
    if spec.get("hook_sub"):
        d.text((W // 2, y + 40), spec["hook_sub"], font=noto(52, "Bold"), fill=(220, 220, 220), anchor="mm")
    d.text((W // 2, H - 220), "실제 사연 재구성 · 썰배달", font=noto(36, "Regular"), fill=(150, 150, 150), anchor="mm")
    if p < 1:
        s2 = 0.85 + 0.15 * p
        sm = im.resize((int(W * s2), int(H * s2)))
        base = Image.new("RGBA", (W, H), (18, 18, 18, 255))
        base.alpha_composite(sm, ((W - sm.width) // 2, (H - sm.height) // 2))
        return base
    return im


def pick_bgm(spec, assets):
    if spec.get("bgm"):
        return spec["bgm"]
    cands = MOOD_BGM.get(spec.get("mood", "daily"), MOOD_BGM["daily"])
    cands = [c for c in cands if os.path.exists(os.path.join(assets, "bgm", c))]
    hist_path = os.path.join(assets, "bgm", "history.txt")
    hist = open(hist_path).read().split() if os.path.exists(hist_path) else []
    # 가장 오래전에 쓴(또는 안 쓴) 곡
    def last_used(c):
        return max([i for i, h in enumerate(hist) if h == c], default=-1)
    choice = min(cands, key=last_used)
    with open(hist_path, "a") as fp:
        fp.write(choice + "\n")
    return choice


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
    SPEAKER_COLOR.clear()
    prev = None
    for m in spec["messages"]:
        if m["t"] == "them":
            m.setdefault("name", spec["partner"])
        if m["t"] == "me" and m.get("to"):
            m.setdefault("label", f'{spec.get("me_name", "나")} → {m["to"]}')
        elif m["t"] == "me" and prev != "me":
            m.setdefault("label", spec.get("me_name", "나"))
        prev = m["t"]
    for c in spec.get("cast", []):
        draw_avatar(ImageDraw.Draw(Image.new("RGBA", (110, 110))), c["name"])

    intro = intro_card(spec) if spec.get("intro") else None   # 등장인물 카드는 기본 끔(첫 3초 이탈 원인)
    hook_end = 1.3 if spec.get("hook") else 0.0
    intro_end = hook_end + (1.6 if intro else 0.0)

    # 타임라인: 훅 화면 → 바로 대화. them 앞에는 짧은 입력중 표시
    events, t = [], intro_end + 0.15
    for m in spec["messages"]:
        img, align = render_bubble(m)
        if m["t"] == "them":
            events.append({"start": t, "typing": True, "dur": 0.35, "name": m["name"]})
            t += 0.35
        events.append({"start": t, "img": img, "align": align})
        read = 0.5 + len(m["text"]) * 0.04
        t += min(max(read, 0.8), 1.7)
    end_start = t + 0.2
    total = end_start + 2.2
    nframes = int(total * FPS)

    tmp = tempfile.mkdtemp(prefix="chat_")
    gap = 26
    for fi in range(nframes):
        now = fi / FPS
        if now < hook_end:
            hs = hook_screen(spec, now)
            hs.convert("RGB").save(os.path.join(tmp, f"{fi:05d}.jpg"), quality=90)
            continue
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
            frame.alpha_composite(typing_bubble(now * 2, typing[0]["name"]), (PAD, int(y)))
        if intro and now < intro_end + 0.3:
            a = 1.0 if now < intro_end else 1 - (now - intro_end) / 0.3
            ii = intro.copy()
            if a < 1:
                ii.putalpha(ii.getchannel("A").point(lambda v: int(v * a)))
            frame.alpha_composite(ii, (PAD, CHAT_TOP + 60))
        footer(frame)
        frame.alpha_composite(header(spec, min(1.0, now / total)), (0, 0))
        # 엔딩 오버레이
        if now >= end_start:
            p = min(1.0, (now - end_start) / 0.3)
            ov = Image.new("RGBA", (W, H), (0, 0, 0, int(238 * p)))
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
    if hook_end:
        cues.append(("sfx/pop.mp3", 0.02, None, 1.0))
    bgm_name = pick_bgm(spec, assets)
    print("bgm:", bgm_name)
    bgm = os.path.join(assets, "bgm", bgm_name)
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", silent, "-stream_loop", "-1", "-i", bgm]
    for f, _, _, _ in cues:
        cmd += ["-i", os.path.join(assets, f)]
    parts = [f"[1:a]atrim=0:{total:.2f},loudnorm=I=-16,volume={spec.get('bgm_volume', 0.35)},afade=t=in:d=0.6,afade=t=out:st={total - 1.5:.2f}:d=1.5[bg]"]
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
