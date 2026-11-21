"""표지용 무료 사진 찾기 (Openverse 공식 API, CC0·퍼블릭도메인만).

1) 후보 보기:   python3 tools/find_photo.py search "exam classroom" [개수]
   -> 후보 id 목록과 /tmp/photo_sheet.jpg (번호 붙은 미리보기) 생성. 이 이미지를 열어 직접 고른다.
2) 내려받기:    python3 tools/find_photo.py get <id> cards/<폴더>/cover_photo.jpg
   -> 원본 크기 이미지 저장 + 같은 폴더에 cover_photo.txt (출처·라이선스 기록)

고르는 기준: 얼굴이 알아볼 수 있게 나온 실제 인물 사진은 피하고(손, 뒷모습, 사물, 장소 위주),
사연 속 인물로 오해될 수 있는 사진은 쓰지 않는다. 로고·브랜드가 크게 나온 사진도 피한다.
검색어는 영어가 결과가 많다.
"""
import io
import json
import sys
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw

API = "https://api.openverse.org/v1/images/"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "sseol-delivery-bot"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def search(q, n=20):
    url = API + "?" + urllib.parse.urlencode({"q": q, "license": "cc0,pdm", "page_size": n})
    res = json.loads(fetch(url))["results"]
    tiles = []
    for i, r in enumerate(res, 1):
        print(i, r["id"], r["width"], r["height"], (r.get("title") or "")[:40])
        try:
            im = Image.open(io.BytesIO(fetch(API + r["id"] + "/thumb/"))).convert("RGB")
            im.thumbnail((240, 240))
            t = Image.new("RGB", (250, 270), "white")
            t.paste(im, (5, 25))
            ImageDraw.Draw(t).text((5, 5), str(i), fill="black")
            tiles.append(t)
        except Exception as e:
            print("  thumb fail", e)
    cols = 5
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 250, max(rows, 1) * 270), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * 250, (i // cols) * 270))
    sheet.save("/tmp/photo_sheet.jpg")
    print("preview: /tmp/photo_sheet.jpg")


def get(pid, out):
    meta = json.loads(fetch(API + pid + "/"))
    data = fetch(API + pid + "/thumb/?full_size=true&compressed=false")
    Image.open(io.BytesIO(data)).convert("RGB").save(out, "JPEG", quality=95)
    with open(out.rsplit(".", 1)[0] + ".txt", "w", encoding="utf-8") as f:
        f.write(f"openverse_id: {pid}\ntitle: {meta.get('title')}\ncreator: {meta.get('creator')}\n"
                f"license: {meta.get('license')} {meta.get('license_version')}\nsource: {meta.get('foreign_landing_url')}\n")
    print("saved", out, meta.get("license"))


if __name__ == "__main__":
    if sys.argv[1] == "search":
        search(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 20)
    else:
        get(sys.argv[2], sys.argv[3])
