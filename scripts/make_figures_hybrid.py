#!/usr/bin/env python3
"""figs/fig_hy_*.png 를 data/trials.csv(200판 VLA만) · data/hybrid_trials.csv(200판 + 수식)에서 다시 만든다.

    python3 scripts/make_figures_hybrid.py

모양 · 색은 make_figures.py 와 같다. 200판 VLA만 = 주황, 200판 + 수식 = 청록.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_figures import (BG, FIG, INK, INK2, MUTE, OI, STAGES, fl, heading, plt, rd,  # noqa: E402
                          wilson)
from matplotlib.lines import Line2D  # noqa: E402

CONDS = [("200B", "200판 VLA만 (11-15 오후)", OI["orange"], "^"), ("200B_hy", "200판 + 수식 (11-15 저녁 · 11-16 오전)", OI["green"], "o")]
VERD = {"success": "성공", "partial": "부분", "fail": "실패"}


def base_rows():
    return [r for r in rd("trials.csv") if r["model"] == "200B" and r["counted"] == "1"]


def hy_rows(all_=False):
    return [r for r in rd("hybrid_trials.csv") if all_ or r["counted"] == "1"]


# ── 1. 단계별 누적 통과 ─────────────────────────────────────────────
def fig_stage(B, H):
    fig, ax = plt.subplots(figsize=(9.6, 5.0))
    xs = np.arange(len(STAGES))
    for j, ((m, name, col, mk), R) in enumerate(zip(CONDS, (B, H))):
        n = len(R)
        k = [sum(int(r[s]) for r in R) for s, _ in STAGES]
        p = [v / n * 100 for v in k]
        lo, hi = zip(*[wilson(v, n) for v in k])
        dx = (j - 0.5) * 0.08
        ax.errorbar(xs + dx, p, yerr=[np.array(p) - np.array(lo) * 100, np.array(hi) * 100 - np.array(p)], fmt="none",
                    ecolor=col, elinewidth=1.0, capsize=3, alpha=0.55, zorder=2)
        ax.plot(xs + dx, p, color=col, lw=2.2, marker=mk, ms=8, mec=BG, mew=1.5, zorder=3, label=f"{name} (n={n})")
        ax.annotate(f"{k[-1]}/{n} = {p[-1]:.0f}%", (xs[-1] + dx, p[-1]), xytext=(14, 6 if j else -6),
                    textcoords="offset points", va="center", fontsize=10, color=INK)
    ax.set_xticks(xs, [f"{s}\n{lab}" for s, lab in STAGES])
    ax.set_xlim(-0.3, len(STAGES) - 1 + 1.0)
    ax.set_ylim(0, 105)
    ax.set_yticks(range(0, 101, 20), [f"{v}%" for v in range(0, 101, 20)])
    ax.set_ylabel("그 단계까지 모두 통과한 판 비율")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="lower left", fontsize=9.5)
    heading(fig, "200판 모델: VLA만 vs VLA + 수식 — 단계별 누적 통과율",
            "같은 체크포인트 · 배치 10개 × 앞의 유효 3판 · 세로 막대는 Wilson 95% 구간 · S8은 링 칸 자리를 모르면 통과로 세지 않음(수식 쪽 L5 2판)")
    fig.savefig(FIG / "fig_hy_stage_cumulative.png")
    plt.close(fig)


# ── 2. 배치별 성공 ────────────────────────────────────────────────
def fig_layout(B, H, HA):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9.6, 5.8), sharex=True, gridspec_kw={"height_ratios": [1.5, 1], "hspace": 0.12})
    xs = np.arange(1, 11)
    w = 0.38
    for j, ((m, name, col, _), R) in enumerate(zip(CONDS, (B, H))):
        v = [sum(1 for r in R if int(r["layout"]) == n and r["verdict"] == "success") for n in xs]
        a1.bar(xs + (j - 0.5) * w, v, width=w * 0.92, color=col, label=name.split(" (")[0], zorder=2)
        for x, vv in zip(xs + (j - 0.5) * w, v):
            if vv == 0:
                a1.text(x, 0.04, "0", ha="center", va="bottom", fontsize=8.5, color=col)
    for n in xs:
        R = [r for r in H if int(r["layout"]) == n]
        if R and not any(int(r["hy_ready"]) for r in R):
            a1.text(n + 0.5 * w, 1.2, "수식\n준비\n못 함", ha="center", va="bottom", fontsize=7.5, color=INK2, linespacing=1.0)
    X = [r for r in HA if r["counted"] == "0"]
    if X:
        n = int(X[0]["layout"])
        k = sum(1 for r in X if r["verdict"] == "success")
        a1.bar(n + 0.5 * w, k, width=w * 0.92, fill=False, edgecolor=OI["green"], lw=1.4, ls="--", zorder=3)
        a1.annotate(f"자리 맞춤 추가 {k}/{len(X)}", (n + 0.5 * w, k), xytext=(8, 2), textcoords="offset points", fontsize=8, color=INK2)
    a1.set_ylim(0, 3.6)
    a1.set_yticks([0, 1, 2, 3], ["0/3", "1/3", "2/3", "3/3"])
    a1.set_ylabel("성공")
    a1.grid(axis="x", visible=False)
    a1.legend(loc="upper left", ncol=2, fontsize=9.5)
    for key, lab, mk, col in (("scene_vs_ref_red_mm", "빨간 튜브", "o", INK), ("scene_vs_ref_ring_mm", "링 칸", "s", MUTE)):
        for n in xs:
            v = sorted(fl(r[key]) for r in H if int(r["layout"]) == n and fl(r[key]) is not None)
            if v:
                med = v[len(v) // 2]
                a2.scatter([n + (0.12 if mk == "s" else -0.12)], [med], marker=mk, s=42, color=col, edgecolor=BG, lw=1, zorder=3)
                if v[-1] - v[0] > 20:
                    a2.vlines(n + (0.12 if mk == "s" else -0.12), v[0], v[-1], color=col, lw=1.0, zorder=2)
    a2.legend(handles=[Line2D([], [], ls="", marker="o", color=INK, label="빨간 튜브"),
                       Line2D([], [], ls="", marker="s", color=MUTE, label="링 칸")], loc="upper left", ncol=2, fontsize=9)
    a2.set_ylim(0, 100)
    a2.set_ylabel("오후 자리와 차이 (mm)")
    a2.set_xticks(xs, [f"L{n}" for n in xs])
    a2.grid(axis="x", visible=False)
    heading(fig, "배치별 성공 — 200판 VLA만 vs VLA + 수식",
            "아래: 수식 판 시작 장면이 오후(VLA만) 시작 장면과 다른 정도 · 가운데값, 세로선은 판 사이 범위 · L2 · L5 링 칸은 인식 못 함")
    fig.savefig(FIG / "fig_hy_layout_success.png")
    plt.close(fig)


# ── 3. 판마다 넘김 기록 ────────────────────────────────────────────
def fig_handoff(H):
    R = sorted(H, key=lambda r: (int(r["layout"]), int(r["trial"])))
    n = len(R)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.4, 0.27 * n + 1.6), sharey=True, gridspec_kw={"wspace": 0.06})
    ys = np.arange(n)[::-1]
    capc = {"red": OI["vermillion"], "yellow": OI["yellow"]}
    for y, r in zip(ys, R):
        a2.text(41, y, VERD[r["verdict"]], va="center", ha="left", fontsize=8.5,
                color={"success": INK, "partial": INK2, "fail": OI["vermillion"]}[r["verdict"]])
        if not int(r["hy_ready"]):
            a1.text(1, y, "수식 준비 못 함(링 칸 인식 실패) · VLA만으로 실행", va="center", fontsize=8, color=MUTE)
            continue
        if int(r["grasp_handoff"]):
            d, cap, filled = fl(r["grasp_vla_to_cap_mm"]), r["grasp_target"], True
        else:
            d, cap, filled = fl(r["grasp_reject_mm"]), r["grasp_reject_cap"], False
        if d is not None:
            c = capc.get(cap, MUTE)
            a1.scatter([d], [y], s=46, marker="o", color=c if filled else BG, edgecolor=INK if cap == "yellow" or not filled else c,
                       lw=1.2, zorder=3)
        if int(r["place_handoff"]):
            d2 = fl(r["place_vla_to_slot_mm"])
            ok = r["place_ok"] == "1"
            a2.scatter([d2], [y], s=46, marker="s", color=OI["green"] if ok else BG, edgecolor=OI["green"], lw=1.2, zorder=3)
    for ax, t in ((a1, "잡기: VLA가 닫으려던 자리 → 가장 가까운 뚜껑 (mm)"), (a2, "꽂기: VLA가 내려가려던 자리 → 링 칸 (mm)")):
        ax.axvline(25, color=INK2, ls="--", lw=1.0, zorder=1)
        ax.text(25, n - 0.3, " 넘김 한도 25 mm", fontsize=8, color=INK2, va="bottom")
        ax.set_xlim(0, 40 if ax is a1 else 46)
        ax.set_xlabel(t, fontsize=9.5)
        ax.grid(axis="y", visible=False)
        ax.set_ylim(-0.8, n - 0.2)
    a2.set_xticks(range(0, 41, 10))
    a1.set_yticks(ys, [f"L{r['layout']}-{r['trial']}" for r in R], fontsize=8.5)
    h = [Line2D([], [], ls="", marker="o", ms=7, color=OI["vermillion"], label="빨간 뚜껑 · 수식이 잡음"),
         Line2D([], [], ls="", marker="o", ms=7, color=OI["yellow"], mec=INK, label="노란 뚜껑 · 수식이 잡음"),
         Line2D([], [], ls="", marker="o", ms=7, color=BG, mec=MUTE, label="한도 밖 — VLA가 그대로 닫음"),
         Line2D([], [], ls="", marker="s", ms=7, color=OI["green"], label="수식 꽂기 끝까지"),
         Line2D([], [], ls="", marker="s", ms=7, color=BG, mec=OI["green"], label="수식 꽂기 중 멈춤")]
    fig.legend(handles=h, loc="lower center", ncol=5, fontsize=8.2, bbox_to_anchor=(0.5, -0.01))
    heading(fig, "판마다 수식이 넘겨받은 자리 — 200판 + 수식 (센 30판)",
            "VLA가 그 자리에서 닫거나 내려가려 할 때 기준 안이면 수식이 넘겨받는다 · 오른쪽 끝 글자는 사람 판정")
    H_ = 0.27 * n + 1.6
    fig.subplots_adjust(bottom=0.95 / H_, top=1 - 0.75 / H_)
    fig.savefig(FIG / "fig_hy_handoff.png")
    plt.close(fig)


def main():
    B, H, HA = base_rows(), hy_rows(), hy_rows(True)
    fig_stage(B, H)
    fig_layout(B, H, HA)
    fig_handoff(H)
    print("figs:", ", ".join(sorted(p.name for p in FIG.glob("fig_hy_*.png"))))


if __name__ == "__main__":
    main()
