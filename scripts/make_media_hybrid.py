#!/usr/bin/env python3
"""200판 + 수식 실행 영상 2개와 장면 띠 그림을 만든다.

    python3 scripts/make_media_hybrid.py <bench_pack 폴더(r200_bs64_B_hy 포함)> <영상 폴더>

  media/200hy_L4-1_success.mp4 · _x3.gif, media/200hy_L9-3_success.mp4 · _x3.gif
  figs/hy_keyframes.jpg   L9-3 의 VLA 접근 · 수식 잡기 · VLA 옮기기 · 수식 꽂기 · 끝 (3인칭)
아래 막대는 누가 움직이는지(VLA · 수식)를 meta.json → hybrid 의 넘김 시각으로 칠한다.
"""
import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_media import BG, INK, INK2, ROOT, encode, find_video, font, label  # noqa: E402

BENCH = "r200_bs64_B_hy"
COL = {"vla_a": (86, 180, 233), "vla_c": (0, 114, 178), "fm": (0, 158, 115), "home": (150, 150, 145)}
PICKS = {"4-1": "200판 + 수식 · 배치 L4-1 · 성공", "9-3": "200판 + 수식 · 배치 L9-3 · 성공"}


def phases(meta, t_end):
    h = meta["hybrid"]
    g, p = h["grasp"], h["place"]
    g0, g1 = g["t_start"], g["t_start"] + g["move_s"]
    p0, p1 = p["t_start"], p["t_start"] + p["move_s"]
    return [(0.0, g0, "vla_a", "VLA 접근"), (g0, g1, "fm", "수식 잡기"), (g1, p0, "vla_c", "VLA 옮기기"),
            (p0, p1, "fm", "수식 꽂기"), (p1, t_end, "home", "홈으로")]


def clip(src, row, meta, head, dst):
    keys = dict((k, v) for k, v in json.loads(row["keys"]))
    ws, we, t0 = float(row["win_s"]), float(row["win_e"]), keys["start"]
    segs = phases(meta, we - t0)
    W, H, BAR = 1272, 360, 58
    fh = font(19, "Bold")
    fs = font(15, "Medium")
    cap = cv2.VideoCapture(str(src))
    cap.set(cv2.CAP_PROP_POS_MSEC, ws * 1000)
    frames = []
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
        tt = tv - t0
        now = next((s for s in segs if s[0] <= tt < s[1]), None)
        if now:
            l, t, r, b = dr.textbbox((0, 0), now[3], font=fh)
            dr.rectangle((W // 2 - (r - l) // 2 - 10, H - 34, W // 2 + (r - l) // 2 + 10, H - 6), fill=COL[now[2]])
            dr.text((W // 2, H - 20), now[3], font=fh, fill=(255, 255, 255), anchor="mm")
        canvas = Image.new("RGB", (W, H + BAR), BG)
        canvas.paste(im, (0, 0))
        d2 = ImageDraw.Draw(canvas)
        d2.text((12, H + 4), head, font=fh, fill=INK)
        d2.text((W - 12, H + 4), f"{max(0.0, tt):5.1f} s", font=fh, fill=INK2, anchor="ra")
        x0, x1, y0 = 12, W - 12, H + 36
        X = lambda t: x0 + (x1 - x0) * (t + t0 - ws) / (we - ws)    # noqa: E731
        d2.rectangle((x0, y0, x1, y0 + 12), fill=(228, 228, 224))
        for a, b, k, name in segs:
            d2.rectangle((X(a), y0, X(b), y0 + 12), fill=COL[k])
            if X(b) - X(a) > 70:
                d2.text(((X(a) + X(b)) / 2, y0 + 6), name, font=font(11, "Medium"), fill=(255, 255, 255), anchor="mm")
        d2.rectangle((X(tt) - 1.5, y0 - 4, X(tt) + 1.5, y0 + 16), fill=INK)
        frames.append(np.asarray(canvas))
    cap.release()
    encode(frames, (W, H + BAR), dst)
    return len(frames) / 10.0


def keyframes(src, row, meta, dst):
    keys = dict((k, v) for k, v in json.loads(row["keys"]))
    t0 = keys["start"]
    g, p = meta["hybrid"]["grasp"], meta["hybrid"]["place"]
    shots = [(g["t_start"] - 1.0, "vla_a", "VLA 접근", "VLA가 빨간 튜브 근처로 내려온다"),
             (g["events"][0]["t"], "fm", "수식 잡기", f"VLA가 닫으려던 자리 {g['snap_mm']:.0f} mm → 계획한 자리에서 쥠"),
             ((g["t_start"] + g["move_s"] + p["t_start"]) / 2, "vla_c", "VLA 옮기기", "쥔 튜브를 링 칸 쪽으로"),
             (p["events"][0]["t"] - 2.0, "fm", "수식 꽂기", f"링 칸 {p['snap_mm']:.0f} mm에서 넘겨받아 곧게 넣음"),
             (p["t_start"] + p["move_s"] + 1.5, "home", "끝", "놓고 올라온 뒤")]
    cw, ch, pad, top = 424, 240, 10, 74
    out = Image.new("RGB", (pad + len(shots) * (cw + pad), top + ch + pad), BG)
    dr = ImageDraw.Draw(out)
    dr.text((pad, 10), "200판 + 수식 · L9-3 — 누가 언제 움직이나 (3인칭)", font=font(22, "Bold"), fill=INK)
    cap = cv2.VideoCapture(str(src))
    for i, (t, k, name, sub) in enumerate(shots):
        cap.set(cv2.CAP_PROP_POS_MSEC, (t0 + t) * 1000)
        ok, f = cap.read()
        im = Image.fromarray(cv2.cvtColor(cv2.resize(f[:, :848], (cw, ch), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB))
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 175, 13), fill=(20, 20, 20))              # 녹화기 글자 가림
        x = pad + i * (cw + pad)
        out.paste(im, (x, top))
        l, tt, r, b = dr.textbbox((0, 0), name, font=font(17, "Bold"))
        dr.rectangle((x, 44, x + (r - l) + 16, 68), fill=COL[k])
        dr.text((x + 8, 56), name, font=font(17, "Bold"), fill=(255, 255, 255), anchor="lm")
        dr.text((x + (r - l) + 24, 56), f"{t:.1f} s", font=font(14, "Medium"), fill=INK2, anchor="lm")
        dr.text((x + 4, top + ch - 6), sub, font=font(13, "Medium"), fill=(255, 255, 255), anchor="ld",
                stroke_width=2, stroke_fill=(20, 20, 20))
    cap.release()
    out.save(dst, quality=88)


def main(pack, vids):
    pack = Path(pack)
    picks = [r for r in csv.DictReader(open(pack / "picks.csv", encoding="utf-8-sig")) if r["bench"] == BENCH]
    T = {t["stamp"]: t for t in csv.DictReader(open(pack / "trials.csv", encoding="utf-8-sig")) if t["bench"] == BENCH}
    for r in picks:
        meta = json.loads((pack / "trials" / BENCH / T[r["stamp"]]["dir"] / "meta.json").read_text())
        src = find_video(vids, r["clip"])
        dst = ROOT / "media" / f"200hy_L{r['layout_k']}_{r['label']}.mp4"
        sec = clip(src, r, meta, PICKS[r["layout_k"]], dst)
        print(f"{dst.name}  {sec:.1f} s  {dst.stat().st_size / 1e6:.1f} MB · gif {dst.with_name(dst.stem + '_x3.gif').stat().st_size / 1e6:.1f} MB")
        if r["layout_k"] == "9-3":
            keyframes(src, r, meta, ROOT / "figs" / "hy_keyframes.jpg")
            print("figs/hy_keyframes.jpg")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
