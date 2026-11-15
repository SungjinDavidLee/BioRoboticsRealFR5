#!/usr/bin/env python3
"""실행 영상 · 단계 사진 · 배치 사진 · 시간축 자료를 실험 기록에서 만든다.

    python3 scripts/make_media.py <bench_pack 폴더> <영상 폴더>

입력은 로봇 실행 PC에서 읽기만 해서 모은 묶음(공개하지 않음)과 녹화 영상(3인칭 | 손목, 10 fps)이다.
  media/200_<배치>_<결과>.mp4 · _x3.gif   영상 4개 (실제 속도 · 3배속 미리보기)
  figs/task_S0_start.jpg … task_S9_place.jpg  200판 L9-1 성공 판의 단계 사진 4장
  figs/1200_L7-1_photos.jpg                   1200판 L7-1 성공 판 시작 · 끝 사진 (이날은 영상 녹화 전)
  figs/layout_photos.jpg                      배치 10개를 두 날 시작 사진으로 나란히
  data/timeline_200_L9-1.csv, data/timeline_200_L9-1_events.json
"""
import csv
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-{}.ttc"
BG, INK, INK2 = (250, 250, 248), (34, 34, 34), (85, 85, 85)
PHASE = {"approach": ((86, 180, 233), "접근"), "carry": ((0, 114, 178), "쥐고 옮기기"), "place": ((0, 158, 115), "놓기 · 홈으로"),
         "miss": ((213, 94, 0), "헛잡음 뒤")}
CLIPS = {  # 이름 → (머리말, 단계 구분)
    "success_L9-1": ("200판 · 배치 L9-1 · 성공", "carry"),
    "success_L4-1": ("200판 · 배치 L4-1 · 성공", "carry"),
    "wrong_tube_L3-1": ("200판 · 배치 L3-1 · 실패 — 노란 튜브를 집어 링 칸으로 옮김", "carry"),
    "grasp_miss_L6-1": ("200판 · 배치 L6-1 · 실패 — 빨간 튜브 중심에서 25 mm 떨어진 곳에서 닫아 헛잡음", "miss"),
}
B200, B1200 = "r200_bs64_B", "mix1200_r1111_bs64_v66c"


def font(size, w="Regular"):
    return ImageFont.truetype(FONT.format(w), size, index=1)


def L(s):
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return None


def trial_dirs(pack, bench):
    """유효 판을 시각 순으로 → {(배치, 유효 순번): 폴더}. score_stages_fr5.py와 같은 번호."""
    T = sorted((t for t in csv.DictReader(open(pack / "trials.csv", encoding="utf-8-sig")) if t["bench"] == bench),
               key=lambda t: t["stamp"])
    out, seen = {}, {}
    for t in T:
        if t["human"] == "invalid":
            continue
        seen[t["layout"]] = seen.get(t["layout"], 0) + 1
        out[(int(t["layout"]), seen[t["layout"]])] = (pack / "trials" / bench / t["dir"], t)
    return out


def tcp(d):
    return [[float(v) for v in r.values()] for r in csv.DictReader(open(d / "tcp.csv"))]


def label(dr, xy, text, f):
    x, y = xy
    l, t, r, b = dr.textbbox((x + 8, y + 4), text, font=f)
    dr.rectangle((x, y, r + 8, b + 6), fill=(20, 20, 20))
    dr.text((x + 8, y + 4), text, font=f, fill=(255, 255, 255))


# ── 영상 ───────────────────────────────────────────────────────────
def encode(frames, size, dst):
    tmp = dst.with_name(dst.stem + ".part.mp4")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}",
                          "-r", "10", "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p",
                          "-movflags", "+faststart", str(tmp)], stdin=subprocess.PIPE)
    for fr in frames:
        p.stdin.write(fr.tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise SystemExit(f"ffmpeg 실패: {dst}")
    os.replace(tmp, dst)
    gif = dst.with_name(dst.stem + "_x3.gif")
    tmpg = gif.with_name(gif.stem + ".part.gif")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(dst), "-vf",
                    "setpts=PTS/3,fps=10,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];"
                    "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle", str(tmpg)], check=True)
    os.replace(tmpg, gif)


def clip(src, row, head, mid, dst):
    keys = dict((k, v) for k, v in L(row["keys"]))
    ws, we = float(row["win_s"]), float(row["win_e"])
    t0, tc, to, te = keys["start"], keys.get("close"), keys.get("open"), keys["end"]
    segs = [(t0, tc, "approach")]
    if mid == "carry":
        segs += [(tc, to, "carry"), (to, te, "place")]
    else:
        segs += [(tc, te, "miss")]
    cap = cv2.VideoCapture(str(src))
    W, H = 1272, 360                                             # 1696×480 → 0.75
    BAR = 58
    fh, fs = font(19, "Bold"), font(15, "Medium")
    frames = []
    cap.set(cv2.CAP_PROP_POS_MSEC, ws * 1000)
    while True:
        tv = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        ok, f = cap.read()
        if not ok or tv > we:
            break
        im = Image.fromarray(cv2.cvtColor(cv2.resize(f, (W, H), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB))
        dr = ImageDraw.Draw(im)
        dr.rectangle((0, 0, 260, 22), fill=(20, 20, 20))           # 녹화기 글자(시각 · 폴더 이름) 가림
        label(dr, (0, 0), "3인칭", fs)
        label(dr, (W // 2, 0), "손목", fs)
        canvas = Image.new("RGB", (W, H + BAR), BG)
        canvas.paste(im, (0, 0))
        d2 = ImageDraw.Draw(canvas)
        d2.text((12, H + 4), head, font=fh, fill=INK)
        tt = max(0.0, tv - t0)
        d2.text((W - 12, H + 4), f"{tt:5.1f} s", font=fh, fill=INK2, anchor="ra")
        x0, x1, y0 = 12, W - 12, H + 36
        span = we - ws
        X = lambda t: x0 + (x1 - x0) * (t - ws) / span      # noqa: E731
        d2.rectangle((x0, y0, x1, y0 + 12), fill=(228, 228, 224))
        for a, b, k in segs:
            if a is None or b is None:
                continue
            c, name = PHASE[k]
            d2.rectangle((X(a), y0, X(b), y0 + 12), fill=c)
            if X(b) - X(a) > 90:
                d2.text(((X(a) + X(b)) / 2, y0 + 6), name, font=font(11, "Medium"), fill=(255, 255, 255), anchor="mm")
        d2.rectangle((X(tv) - 1.5, y0 - 4, X(tv) + 1.5, y0 + 16), fill=INK)
        frames.append(np.asarray(canvas))
    cap.release()
    encode(frames, (W, H + BAR), dst)
    return len(frames) / 10.0


# ── 단계 사진 ─────────────────────────────────────────────────────
def frame_at(src, t):
    cap = cv2.VideoCapture(str(src))
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, f = cap.read()
    cap.release()
    f = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
    return Image.fromarray(f[:, :848]), Image.fromarray(f[:, 848:])


def panel(views, badge, title, sub, dst, names=("3인칭 · third-person", "손목 · wrist")):
    W, pad, gap = 848, 20, 16
    head = 96
    out = Image.new("RGB", (pad * 2 + W * 2 + gap, head + 480 + pad), BG)
    d = ImageDraw.Draw(out)
    fb, fs = font(26, "Bold"), font(19)
    l, t, r, b = d.textbbox((pad + 10, 14), badge, font=fb)
    d.rounded_rectangle((pad, 10, r + 10, b + 6), radius=8, fill=(20, 20, 20))
    d.text((pad + 10, 14), badge, font=fb, fill=(255, 255, 255))
    d.text((r + 22, 14), title, font=fb, fill=INK)
    d.text((pad, 58), sub, font=fs, fill=INK2)
    for i, (v, nm) in enumerate(zip(views, names)):
        x = pad + i * (W + gap)
        im = v.copy()
        dr = ImageDraw.Draw(im)
        if i == 0 and names[0].startswith("3인칭"):
            dr.rectangle((0, 0, 340, 30), fill=(20, 20, 20))       # 녹화기 글자(시각 · 폴더 이름) 가림
        label(dr, (0, 0), nm, font(19, "Medium"))
        out.paste(im, (x, head))
    out.save(dst, quality=88)


def task_photos(pack, vids, picks):
    T = trial_dirs(pack, B200)
    d, t = T[(9, 1)]
    row = next(r for r in picks if r["layout_k"] == "9-1" and r["bench"] == B200)
    src = find_video(vids, row["clip"])
    keys = dict((k, v) for k, v in L(row["keys"]))
    meta = json.loads((d / "meta.json").read_text())
    tr = tcp(d)
    t0 = tr[0][0]
    ev = meta["events"]
    ce = next(e for e in ev if e["ev"] == "close")
    oe = next(e for e in ev if e["ev"] == "open")
    S = {r["model"] + r["layout"] + "-" + r["trial"]: r for r in csv.DictReader(open(ROOT / "data" / "trials.csv"))}
    s = S["200B9-1"]
    ring = [float(s["ring_x"]), float(s["ring_y"])]
    red = [float(s["red_x"]), float(s["red_y"])]
    hold = [r for r in tr if ce["tm"] <= r[0] <= oe["tm"] and r[5] >= 12.0]
    hm = min(hold, key=lambda r: math.dist(r[1:3], ring))
    vt = lambda tm: keys["start"] + (tm - t0)                    # noqa: E731
    w3 = float(s["width_3s_mm"])
    shots = [
        ("S0", "초기 위치", vt(t0) + 0.2, f"시작 장면에서 찾은 빨간 튜브 ({red[0]:.0f}, {red[1]:.0f}) mm · 링 칸 ({ring[0]:.0f}, {ring[1]:.0f}) mm · 3인칭 밝기 {s['bright_third']}"),
        ("S4", "쥐기", vt(ce["tm"]) + 1.5, f"빨간 튜브 중심에서 {float(s['close_to_red_mm']):.0f} mm 떨어진 곳에서 닫음 · 닫고 3 s 뒤 손가락 폭 {w3:.1f} mm (기준 20–50 mm)"),
        ("S8", "이송", vt(hm[0]), f"쥔 채(폭 {hm[5]:.0f} mm) 링 칸 중심 수평 {math.dist(hm[1:3], ring):.1f} mm까지 옴 (기준 20 mm) · 손끝 높이 {hm[3]:.0f} mm"),
        ("S9", "꽂힘", vt(oe["tm"]) + 2.0, f"링 칸 중심에서 {float(s['open_to_ring_mm']):.0f} mm 떨어진 곳에서 열어 놓음 · 사람 판정 성공"),
    ]
    names = {"S0": "start", "S4": "grasp", "S8": "transport", "S9": "place"}
    for st, nm, tv, sub in shots:
        a, b = frame_at(src, tv)
        panel((a, b), st, f"{nm}  ·  200판 L9-1 성공 판 ({tv - keys['start']:.1f} s)", sub, ROOT / "figs" / f"task_{st}_{names[st]}.jpg")
    # 시간축 자료
    with open(ROOT / "data" / "timeline_200_L9-1.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "x_mm", "y_mm", "z_mm", "width_mm"])
        for r in tr:
            w.writerow([round(r[0] - t0, 2), round(r[1], 1), round(r[2], 1), round(r[3], 1), round(r[5], 1)])
    evj = {"close": round(ce["tm"] - t0, 2), "open": round(oe["tm"] - t0, 2), "over_ring": round(hm[0] - t0, 2),
           "over_ring_mm": round(math.dist(hm[1:3], ring), 1), "width_3s": w3, "lift_mm": float(s["lift_mm"])}
    (ROOT / "data" / "timeline_200_L9-1_events.json").write_text(json.dumps(evj, indent=1))


def photos_1200(pack):
    d, t = trial_dirs(pack, B1200)[(7, 1)]
    a = [Image.open(d / f"{k}.jpg").convert("RGB") for k in ("start_third", "end_third")]
    panel(a, "1200판", "배치 L7-1 성공 판 — 시작 · 끝 (3인칭)",
          "이날(11-12)은 영상 녹화를 하지 않아 시작 · 끝 장면 사진만 있다 · 왼쪽 받침의 빨간 튜브를 오른쪽 받침의 빨간 링 칸에 꽂음",
          ROOT / "figs" / "1200_L7-1_photos.jpg", names=("시작", "끝"))


def layout_photos(pack):
    A, B = trial_dirs(pack, B1200), trial_dirs(pack, B200)
    cw, ch = 560, 190                                            # 848×480 에서 책상 부분 (x 60–800, y 230–480) 을 줄임
    pad, lw, head = 14, 56, 64
    out = Image.new("RGB", (lw + 2 * cw + 3 * pad, head + 10 * (ch + pad) + pad), BG)
    dr = ImageDraw.Draw(out)
    fb, fm = font(22, "Bold"), font(18, "Medium")
    dr.text((pad, 12), "같은 배치 번호, 두 날의 시작 장면 (3인칭, 책상 부분)", font=fb, fill=INK)
    for j, (nm, c) in enumerate((("1200판 날 · 11-12", (0, 114, 178)), ("200판 날 · 11-15", (230, 159, 0)))):
        dr.text((lw + pad + j * (cw + pad) + 4, 42), nm, font=fm, fill=c)
    for i in range(1, 11):
        y = head + (i - 1) * (ch + pad) + 10
        dr.text((pad, y + ch // 2), f"L{i}", font=fb, fill=INK, anchor="lm")
        for j, T in enumerate((A, B)):
            k = (i, 1)
            if k not in T or not (T[k][0] / "start_third.jpg").is_file():
                continue
            im = Image.open(T[k][0] / "start_third.jpg").convert("RGB").crop((60, 230, 800, 480)).resize((cw, ch), Image.LANCZOS)
            out.paste(im, (lw + pad + j * (cw + pad), y))
    out.save(ROOT / "figs" / "layout_photos.jpg", quality=86)


def find_video(vids, name):
    m = sorted(Path(vids).glob(f"*{name}"))
    if not m:
        raise SystemExit(f"영상 없음: {name}")
    return m[0]


def main(pack, vids):
    pack = Path(pack)
    (ROOT / "media").mkdir(exist_ok=True)
    (ROOT / "figs").mkdir(exist_ok=True)
    picks = list(csv.DictReader(open(pack / "picks.csv", encoding="utf-8-sig")))
    for r in picks:
        if r["bench"] != B200:
            continue
        key = f"{r['label']}_L{r['layout_k']}"
        head, mid = CLIPS[key]
        dst = ROOT / "media" / f"200_L{r['layout_k']}_{r['label']}.mp4"
        sec = clip(find_video(vids, r["clip"]), r, head, mid, dst)
        print(f"{dst.name}  {sec:.1f} s  {dst.stat().st_size / 1e6:.1f} MB · gif {dst.with_name(dst.stem + '_x3.gif').stat().st_size / 1e6:.1f} MB")
    task_photos(pack, vids, picks)
    photos_1200(pack)
    layout_photos(pack)
    print("사진:", ", ".join(sorted(p.name for p in (ROOT / "figs").glob("*.jpg"))))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
