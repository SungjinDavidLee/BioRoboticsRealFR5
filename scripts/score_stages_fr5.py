#!/usr/bin/env python3
"""FR5 벤치 기록(bench_pack 묶음) → data/trials.csv · invalid_trials.csv · stage_summary.json · layouts.csv
                                     · train_positions.csv · train_loss.csv

    python3 scripts/score_stages_fr5.py <bench_pack 폴더>

입력은 로봇 실행 PC에서 읽기만 해서 모은 묶음이다(공개하지 않음). 판마다 처음 막힌 단계를 정한다.
  S1 목표 선택   처음 닫은 자리가 노란 튜브보다 빨간 튜브에 가깝다 (닫지 않았으면 높이 170 mm 아래에서 가장 가까이 간 튜브)
  S2 접근        닫기 전 손끝이 빨간 튜브 중심 수평 25 mm 안 · 높이 170 mm 아래로 들어간다
  S4 잡기        처음 닫고 3 s 뒤 그리퍼 폭이 20–50 mm다 (실행 도구 자동 판정 grasp)
  S6 들기        쥔 채(폭 12 mm 이상) 닫은 높이보다 60 mm 이상 올라간다
  S8 이송        쥔 채(폭 12 mm 이상, 처음 폭이 12 mm 아래로 떨어지기 전까지) 손끝이 링 칸 중심 수평 20 mm 안에 들어간다
  S9 꽂힘        사람 판정 성공
뒤 단계를 통과했으면 앞 단계도 통과로 본다. 배치마다 앞의 유효 3판만 센다(넘친 판은 counted=0).
"""
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = {"mix1200_r1111_bs64_v66c": "1200", "r200_bs64_B": "200B"}
STAGES = ["S1", "S2", "S4", "S6", "S8", "S9"]


def L(s):
    try:
        v = json.loads(s)
    except (TypeError, ValueError):
        return None
    return v


def f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def hd(a, b):
    return None if a is None or b is None else math.dist(a[:2], b[:2])


def main(pack):
    pack = Path(pack)
    T = list(csv.DictReader(open(pack / "trials.csv", encoding="utf-8-sig")))
    T.sort(key=lambda t: (t["bench"], t["stamp"]))
    seen, rows, inv = {}, [], []
    def ring_of(t):                                             # 시작 장면 → 끝 장면. 빨간 튜브 시작 자리 20 mm 안에서 찾은 값은 잘못 찾은 것으로 버림
        red = L(t["target_xy"])
        for k in ("ring_xy", "end_ring_xy"):
            v = L(t[k])
            if v and not (red and hd(v, red) < 20.0):
                return v
        return None

    rings = {}                                                  # 시작·끝 장면에서 링 칸을 못 찾은 판은 그날 배치 사진(1200판 벤치) → 같은 벤치·같은 배치의 다른 판 가운데값
    for t in T:
        v = ring_of(t)
        if v:
            rings.setdefault((t["bench"], t["layout"]), []).append(v)
    photo = {}
    for jf in (pack / "bench" / "mix1200_r1111_bs64_v66c").glob("layout_L*.json"):
        photo[jf.stem.split("_L")[-1]] = (json.loads(jf.read_text()) or {}).get("slot_xy")
    for t in T:
        m = MODEL.get(t["bench"])
        if m is None:
            continue
        if t["human"] == "invalid":
            inv.append({"model": m, "date": t["stamp"][:8], "layout": t["layout"], "auto": t["auto"], "type": t["type"]})
            continue
        key = (m, t["layout"])
        seen[key] = seen.get(key, 0) + 1
        d = pack / "trials" / t["bench"] / t["dir"]
        meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").is_file() else {}
        tr = [[float(r["t_mono"]), f(r["x_mm"]), f(r["y_mm"]), f(r["z_mm"]), f(r["grip_pos"]), f(r["width_mm"])]
              for r in csv.DictReader(open(d / "tcp.csv"))] if (d / "tcp.csv").is_file() else []
        ev = meta.get("events") or []
        ce = next((e for e in ev if e.get("ev") == "close" and e.get("xyz")), None)
        oe = next((e for e in ev if e.get("ev") == "open" and e.get("xyz")), None)
        red, yel = L(t["target_xy"]), L(t["other_xy"])
        ring, ring_src = ring_of(t), "scene"
        if ring is None and t["bench"] == "mix1200_r1111_bs64_v66c" and photo.get(t["layout"]):   # 1200판 날은 판 장면이 배치 사진과 0–2 mm(L9 약 9 mm)로 맞았다
            ring, ring_src = photo[t["layout"]], "layout_photo"
        if ring is None and rings.get((t["bench"], t["layout"])):
            R = rings[(t["bench"], t["layout"])]
            ring, ring_src = [sorted(v[0] for v in R)[len(R) // 2], sorted(v[1] for v in R)[len(R) // 2]], "same_layout"
        t_close = ce.get("tm") if ce else None
        pre = [r for r in tr if t_close is None or r[0] <= t_close]
        low = [r for r in pre if r[3] is not None and r[3] <= 170]
        s = {}
        if ce:
            dr, dy = hd(ce["xyz"], red), hd(ce["xyz"], yel)
        else:
            dr = min((hd(r[1:3], red) for r in low), default=None) if red else None
            dy = min((hd(r[1:3], yel) for r in low), default=None) if yel else None
        s["S1"] = dr is not None and (dy is None or dr < dy)
        s["S2"] = any(hd(r[1:3], red) is not None and hd(r[1:3], red) <= 25 for r in low)
        s["S4"] = t["grasp"] == "1"
        t_open = oe.get("tm") if oe else None
        hold = []                                                # 닫은 뒤 폭 12 mm 이상인 동안(튜브를 쥐고 있는 구간). 처음 12 mm 아래로 떨어지면 끝
        for r in tr:
            if t_close is None or r[0] < t_close or (t_open is not None and r[0] > t_open):
                continue
            if r[0] > t_close + 1.0 and (r[5] is None or r[5] < 12.0):   # 닫는 1 s 동안은 폭 값이 늦게 바뀐다
                break
            hold.append(r)
        z0 = ce["xyz"][2] if ce else None
        lift = max((r[3] - z0 for r in hold if r[3] is not None), default=None) if z0 is not None else None
        s["S6"] = bool(s["S4"] and lift is not None and lift >= 60.0)
        ring_min = min((hd(r[1:3], ring) for r in hold), default=None) if ring else None
        s["S8"] = bool(s["S6"] and ring_min is not None and ring_min <= 20)
        s["S9"] = t["human"] == "success"
        if not s["S1"]:                                          # 다른 튜브를 잡았으면 그 뒤 단계는 빨간 튜브로는 통과가 아님
            for k in STAGES[1:]:
                s[k] = False
        for i in range(len(STAGES) - 1, 0, -1):                 # 뒤 단계를 통과했으면 앞 단계도 통과
            if s[STAGES[i]]:
                for j in range(i):
                    s[STAGES[j]] = True
        first = next((k for k in STAGES if not s[k]), "")
        b = L(t["bright_start"]) or {}
        c = ce["xyz"] if ce else [None] * 3
        o = oe["xyz"] if oe else [None] * 3
        rnd = lambda v, n=1: None if v is None else round(v, n)        # noqa: E731
        rows.append({"model": m, "date": t["stamp"][:8], "layout": int(t["layout"]), "trial": seen[key], "counted": int(seen[key] <= 3),
                     "verdict": t["human"], "auto": t["auto"], "auto_type": t["type"],
                     "red_x": rnd(red and red[0]), "red_y": rnd(red and red[1]), "yellow_x": rnd(yel and yel[0]), "yellow_y": rnd(yel and yel[1]),
                     "ring_x": rnd(ring and ring[0]), "ring_y": rnd(ring and ring[1]),
                     "close_x": rnd(c[0]), "close_y": rnd(c[1]), "close_z": rnd(c[2]), "close_to_red_mm": rnd(dr), "close_to_yellow_mm": rnd(dy),
                     "open_x": rnd(o[0]), "open_y": rnd(o[1]), "open_z": rnd(o[2]), "open_to_ring_mm": rnd(hd(o, ring) if oe else None),
                     "lift_mm": rnd(lift), "width_3s_mm": f(t.get("width_3s")), "t_close_s": rnd(ce.get("t") if ce else None),
                     "t_open_s": rnd(oe.get("t") if oe else None), "hold_min_to_ring_mm": rnd(ring_min), "ring_src": ring_src if ring else "", **{k: int(v) for k, v in s.items()}, "first_fail": first,
                     "t_exec_s": f(t["t_exec"]), "rtt_ms": f(t["rtt_med"]), "bright_third": rnd((b.get("third") or [None])[0]),
                     "photo_diff_red_mm": f(t["photo_diff_red"]), "photo_diff_ring_mm": f(t["photo_diff_ring"])})
    out = ROOT / "data"
    for name, R in (("trials.csv", rows), ("invalid_trials.csv", inv)):
        with open(out / name, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(R[0]))
            w.writeheader()
            w.writerows(R)
    summ = {}
    for m in ("1200", "200B"):
        C = [r for r in rows if r["model"] == m and r["counted"]]
        summ[m] = {"n": len(C), "invalid": sum(1 for r in inv if r["model"] == m), "extra": sum(1 for r in rows if r["model"] == m and not r["counted"]),
                   "verdict": {v: sum(1 for r in C if r["verdict"] == v) for v in ("success", "partial", "fail")},
                   "stages": {k: sum(r[k] for r in C) for k in STAGES},
                   "first_fail": {k: sum(1 for r in C if r["first_fail"] == k) for k in STAGES}}
    (out / "stage_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1))
    export_train(pack, out)
    export_layouts(rows, out)
    print(json.dumps(summ, ensure_ascii=False, indent=1))


def med(v):
    v = sorted(x for x in v if x is not None)
    return None if not v else round(v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2, 1)


def export_layouts(rows, out):
    """배치마다 두 모델 날의 빨강 · 노랑 · 링 칸 자리(센 판의 가운데값), 그 차이, 가장 가까운 학습 판까지 거리."""
    TP = list(csv.DictReader(open(out / "train_positions.csv", encoding="utf-8")))
    near = lambda p, k: None if p[0] is None else round(min(math.dist(p, (float(t[f"{k}_x"]), float(t[f"{k}_y"]))) for t in TP if t[f"{k}_x"]), 1)  # noqa: E731
    L_ = []
    for n in range(1, 11):
        r = {"layout": n}
        for m in ("1200", "200B"):
            C = [x for x in rows if x["model"] == m and x["layout"] == n and x["counted"]]
            for k in ("red", "yellow", "ring"):
                for a in ("x", "y"):
                    r[f"{m}_{k}_{a}"] = med([x[f"{k}_{a}"] for x in C])
        for k in ("red", "yellow", "ring"):
            a, b = (r[f"1200_{k}_x"], r[f"1200_{k}_y"]), (r[f"200B_{k}_x"], r[f"200B_{k}_y"])
            r[f"diff_{k}_mm"] = None if None in a + b else round(math.dist(a, b), 1)
        for m in ("1200", "200B"):
            r[f"{m}_red_train_nearest_mm"] = near((r[f"{m}_red_x"], r[f"{m}_red_y"]), "red")
            r[f"{m}_ring_train_nearest_mm"] = near((r[f"{m}_ring_x"], r[f"{m}_ring_y"]), "slot")
        L_.append(r)
    with open(out / "layouts.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(L_[0]))
        w.writeheader()
        w.writerows(L_)


def export_train(pack, out):
    """학습 실물 200판의 빨간 튜브 자리 · 꽂은 칸 자리, 두 모델의 학습 손실(10 스텝마다)."""
    tags = list(csv.DictReader(open(pack / "train" / "train_tags.csv", encoding="utf-8-sig")))
    with open(out / "train_positions.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["episode", "red_x", "red_y", "slot_x", "slot_y"])
        for i, t in enumerate(tags):
            a, b = L(t["red_xy"]) or [None, None], L(t["slot_xy"]) or [None, None]
            w.writerow([i, a[0], a[1], b[0], b[1]])
    H = {}
    for m, fn in (("1200", "1200_trainer_state.json"), ("200B", "B_trainer_state.json")):
        for h in json.loads((pack / "train_info" / fn).read_text())["log_history"]:
            if "loss" in h:
                H.setdefault(h["step"], {})[m] = h["loss"]
    with open(out / "train_loss.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["step", "loss_1200", "loss_200"])
        for st in sorted(H):
            w.writerow([st, H[st].get("1200"), H[st].get("200B")])


if __name__ == "__main__":
    main(sys.argv[1])
