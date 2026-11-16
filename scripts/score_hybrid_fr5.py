#!/usr/bin/env python3
"""200판 모델 + 수식(자동 보정) 벤치 → data/hybrid_trials.csv · hybrid_invalid.csv · hybrid_summary.json

    python3 scripts/score_hybrid_fr5.py <bench_pack 폴더(r200_bs64_B_hy 포함)>

단계 판정은 scripts/score_stages_fr5.py 의 score_trial 그대로다(1200판 · 200판과 같은 기준).
링 칸 자리: 그 판 시작 장면 → 끝 장면(빨간 튜브 시작 자리 20 mm 안 값은 버림) → 수식 메모리의 링 칸 → 같은 배치 다른 판 가운데값.
수식 열: 수식 준비(시작 장면 인식) · 잡기 넘김 · 꽂기 넘김과 그 결과(meta.json → hybrid).
VLA만 결과(200판)는 data/trials.csv 의 model=200B 를 쓴다.
"""
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score_stages_fr5 import STAGES, L, f, hd, score_trial  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BENCH, MODEL = "r200_bs64_B_hy", "200B_hy"


def fisher(a, b, c, d):
    """2×2 표 [[a, b], [c, d]] 양측 Fisher 정확 검정 p."""
    n, r1, c1 = a + b + c + d, a + b, a + c
    comb = math.comb
    p0 = comb(r1, a) * comb(n - r1, c1 - a) / comb(n, c1)
    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    return min(1.0, sum(comb(r1, k) * comb(n - r1, c1 - k) / comb(n, c1) for k in range(lo, hi + 1)
                        if comb(r1, k) * comb(n - r1, c1 - k) / comb(n, c1) <= p0 * (1 + 1e-9)))


def wilson(k, n, z=1.959964):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(100 * max(0.0, c - h)), round(100 * min(1.0, c + h))


def main(pack):
    pack = Path(pack)
    T = sorted((t for t in csv.DictReader(open(pack / "trials.csv", encoding="utf-8-sig")) if t["bench"] == BENCH),
               key=lambda t: t["stamp"])
    metas = {t["stamp"]: json.loads((pack / "trials" / BENCH / t["dir"] / "meta.json").read_text()) for t in T}

    def ring_of(t):
        red = L(t["target_xy"])
        for k in ("ring_xy", "end_ring_xy"):
            v = L(t[k])
            if v and not (red and hd(v, red) < 20.0):
                return v, "scene"
        h = metas[t["stamp"]].get("hybrid") or {}
        if h.get("slot_xy"):
            return h["slot_xy"], "hybrid_memory"
        return None, ""

    same = {}
    for t in T:
        v, _ = ring_of(t)
        if v:
            same.setdefault(t["layout"], []).append(v)
    rows, inv, seen = [], [], {}
    for t in T:
        if t["human"] == "invalid":
            inv.append({"model": MODEL, "date": t["stamp"][:8], "layout": t["layout"], "auto": t["auto"], "type": t["type"]})
            continue
        seen[t["layout"]] = seen.get(t["layout"], 0) + 1
        ring, src = ring_of(t)
        if ring is None and same.get(t["layout"]):
            R = same[t["layout"]]
            ring, src = [sorted(v[0] for v in R)[len(R) // 2], sorted(v[1] for v in R)[len(R) // 2]], "same_layout"
        r = score_trial(pack, t, MODEL, seen[t["layout"]], ring, src)
        h = metas[t["stamp"]].get("hybrid") or {}
        g, p = h.get("grasp") or {}, h.get("place") or {}
        gev = [e for e in (h.get("events") or []) if e.get("kind") == "grasp"]
        pev = [e for e in (h.get("events") or []) if e.get("kind") == "place"]
        rej = next((e for e in gev if e.get("key") != "go"), {}) if not g else {}
        prej = [e for e in pev if e.get("key") != "go"]
        rnd = lambda v, n=1: None if v is None else round(v, n)        # noqa: E731
        r.update({
            "hy_ready": int(bool(h.get("ok"))), "hy_why": h.get("why") or "",
            "grasp_handoff": int(bool(g)), "grasp_target": g.get("state", ""), "grasp_vla_to_cap_mm": rnd(g.get("snap_mm")),
            "grasp_next_cap_mm": rnd(g.get("second_mm")), "grasp_ok": int(bool(g.get("ok"))) if g else "",
            "grasp_width_mm": rnd(g.get("grip_mm")), "grasp_arrive_xy_mm": rnd((g.get("arrive") or {}).get("xy_mm")),
            "t_grasp_handoff_s": rnd(g.get("t_start")), "grasp_formula_s": rnd(g.get("move_s")),
            "grasp_reject": rej.get("key", ""), "grasp_reject_mm": rnd(rej.get("snap_mm")), "grasp_reject_cap": rej.get("state", ""),
            "place_handoff": int(bool(p)), "place_vla_to_slot_mm": rnd(p.get("snap_mm")), "place_ok": int(bool(p.get("ok"))) if p else "",
            "place_arrive_xy_mm": rnd((p.get("arrive") or {}).get("xy_mm")), "place_above_mm": rnd(p.get("above_mm")),
            "t_place_handoff_s": rnd(p.get("t_start")), "place_formula_s": rnd(p.get("move_s")),
            "place_rejects": len(prej), "place_stop": "" if not p or p.get("ok") else (p.get("why") or "")[:60],
            "scene_vs_ref_red_mm": f(t["photo_diff_red"]), "scene_vs_ref_ring_mm": f(t["photo_diff_ring"]),
        })
        rows.append(r)
    out = ROOT / "data"
    for name, R in (("hybrid_trials.csv", rows), ("hybrid_invalid.csv", inv)):
        with open(out / name, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(R[0]))
            w.writeheader()
            w.writerows(R)

    C = [r for r in rows if r["counted"]]
    base = [r for r in csv.DictReader(open(out / "trials.csv", encoding="utf-8")) if r["model"] == "200B" and r["counted"] == "1"]
    k_h, k_b = sum(r["S9"] for r in C), sum(int(r["S9"]) for r in base)
    cause = {}
    for r in C:
        if r["S9"]:
            c = "success"
        elif not r["hy_ready"]:
            c = "not_ready"
        elif not r["S1"]:
            c = "other_tube"
        elif not r["grasp_handoff"] and not r["S4"]:
            c = "vla_closed_outside_25mm"
        elif r["place_handoff"] and r["place_ok"]:
            c = "inserted_not_seated"
        else:
            c = "other"
        cause[c] = cause.get(c, 0) + 1
    red_place = [r for r in C if r["place_handoff"] and r["S1"]]
    summ = {
        "n": len(C), "invalid": len(inv), "extra": sum(1 for r in rows if not r["counted"]),
        "verdict": {v: sum(1 for r in C if r["verdict"] == v) for v in ("success", "partial", "fail")},
        "stages": {k: sum(r[k] for r in C) for k in STAGES},
        "first_fail": {k: sum(1 for r in C if r["first_fail"] == k) for k in STAGES},
        "success_wilson95": wilson(k_h, len(C)),
        "vla_only_200B": {"success": k_b, "n": len(base), "wilson95": wilson(k_b, len(base)),
                          "stages": {k: sum(int(r[k]) for r in base) for k in STAGES}},
        "fisher_p_success": round(fisher(k_h, len(C) - k_h, k_b, len(base) - k_b), 3),
        "formula": {
            "ready": sum(r["hy_ready"] for r in C),
            "grasp_handoff": sum(r["grasp_handoff"] for r in C),
            "grasp_handoff_red": sum(1 for r in C if r["grasp_handoff"] and r["grasp_target"] == "red"),
            "grasp_handoff_yellow": sum(1 for r in C if r["grasp_handoff"] and r["grasp_target"] == "yellow"),
            "grasp_ok": sum(1 for r in C if r["grasp_ok"] == 1),
            "grasp_rejected": {k: sum(1 for r in C if r["grasp_reject"] == k) for k in sorted({r["grasp_reject"] for r in C} - {""})},
            "place_handoff": sum(r["place_handoff"] for r in C),
            "place_handoff_red": len(red_place),
            "place_red_success": sum(r["S9"] for r in red_place),
            "place_stopped": sum(1 for r in C if r["place_stop"]),
        },
        "cause": cause,
        "per_layout": {n: {"vla_only": sum(int(r["S9"]) for r in base if int(r["layout"]) == n),
                           "hybrid": sum(r["S9"] for r in C if r["layout"] == n),
                           "hybrid_ready": sum(r["hy_ready"] for r in C if r["layout"] == n)} for n in range(1, 11)},
        "extra_trials": [{"layout": r["layout"], "trial": r["trial"], "verdict": r["verdict"]} for r in rows if not r["counted"]],
    }
    (out / "hybrid_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1))
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
