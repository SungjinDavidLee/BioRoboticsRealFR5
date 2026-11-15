#!/usr/bin/env python3
"""figs/*.png 를 data/*.csv 에서 다시 만든다.

    python3 scripts/make_figures.py

색은 Okabe & Ito (2008) 팔레트. 좌표는 로봇 베이스 기준 mm다.
위치 그림은 3인칭 카메라에서 본 방향으로 그렸다(로봇 x+ = 화면 왼쪽, y+ = 화면 아래).
"""
import csv
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA, FIG = ROOT / "data", ROOT / "figs"

OI = {"orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73", "yellow": "#F0E442",
      "blue": "#0072B2", "vermillion": "#D55E00", "purple": "#CC79A7", "black": "#000000"}
BG, INK, INK2, MUTE, GRID = "#FAFAF8", "#222222", "#555555", "#8A8A8A", "#E4E4E0"
MODELS = [("1200", "1200판", OI["blue"], "o"), ("200B", "200판", OI["orange"], "^")]
LONG = {"1200": "1200판 · 실물 200×3 + 시뮬 600", "200B": "200판 · 실물 200"}
STAGES = [("S1", "목표 선택"), ("S2", "접근"), ("S4", "쥐기"), ("S6", "들기"), ("S8", "이송"), ("S9", "꽂힘")]

plt.rcParams.update({
    "font.family": ["Noto Sans CJK KR", "Noto Sans CJK JP", "DejaVu Sans"],
    "font.size": 10, "axes.edgecolor": MUTE, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.7,
    "axes.axisbelow": True, "figure.dpi": 150, "savefig.dpi": 150, "savefig.bbox": "tight", "savefig.facecolor": BG,
    "figure.facecolor": BG, "axes.facecolor": BG, "legend.frameon": False, "axes.titlesize": 11, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.titlecolor": INK,
})


def rd(name):
    p = DATA / name
    if not p.is_file():
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fl(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def wilson(k, n, z=1.959964):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def heading(fig, title, sub):
    fig.text(0.01, 1.0, title, fontsize=14, fontweight="bold", color=INK, ha="left", va="bottom")
    fig.text(0.01, 0.985, sub, fontsize=9.5, color=INK2, ha="left", va="top")


def camera_view(ax):
    """로봇 x+ = 화면 왼쪽, y+ = 화면 아래(카메라 쪽)."""
    if not ax.xaxis_inverted():                                  # 축을 같이 쓰는 그림에서 두 번 뒤집히지 않게
        ax.invert_xaxis()
    if not ax.yaxis_inverted():
        ax.invert_yaxis()
    ax.set_aspect("equal")


def counted(T):
    return [t for t in T if t["counted"] == "1"]


# ── 1. 단계별 누적 통과 ─────────────────────────────────────────────
def fig_stage_cumulative(T):
    fig, ax = plt.subplots(figsize=(9.6, 5.0))
    xs = np.arange(len(STAGES))
    for j, (m, name, col, mk) in enumerate(MODELS):
        C = [t for t in counted(T) if t["model"] == m]
        n = len(C)
        k = [sum(int(t[s]) for t in C) for s, _ in STAGES]
        p = [v / n * 100 for v in k]
        lo, hi = zip(*[wilson(v, n) for v in k])
        dx = (j - 0.5) * 0.08
        ax.errorbar(xs + dx, p, yerr=[np.array(p) - np.array(lo) * 100, np.array(hi) * 100 - np.array(p)], fmt="none",
                    ecolor=col, elinewidth=1.0, capsize=3, alpha=0.55, zorder=2)
        ax.plot(xs + dx, p, color=col, lw=2.2, marker=mk, ms=8, mec=BG, mew=1.5, zorder=3, label=f"{LONG[m]} (n={n})")
        ax.annotate(f"{name}  {k[-1]}/{n} = {p[-1]:.0f}%", (xs[-1] + dx, p[-1]), xytext=(14, 0 if j == 0 else -2),
                    textcoords="offset points", va="center", fontsize=10, color=INK)
    ax.set_xticks(xs, [f"{s}\n{lab}" for s, lab in STAGES])
    ax.set_xlim(-0.3, len(STAGES) - 1 + 1.25)
    ax.set_ylim(0, 105)
    ax.set_yticks(range(0, 101, 20), [f"{v}%" for v in range(0, 101, 20)])
    ax.set_ylabel("그 단계까지 모두 통과한 판 비율")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="lower left", fontsize=9.5)
    heading(fig, "단계별 누적 통과율", "배치 10개 × 앞의 유효 3판 · 처음 막힌 단계에서 멈춘 것으로 셈 · 세로 막대는 Wilson 95% 구간 · S9 = 사람 판정 성공")
    fig.savefig(FIG / "fig_stage_cumulative.png")
    plt.close(fig)


# ── 2. 처음 막힌 단계 ──────────────────────────────────────────────
def fig_first_fail(T):
    cats = [("S1", "S1 노란 튜브 쪽에서 닫음"), ("S2", "S2 빨간 튜브 25 mm 안으로 못 감"), ("S4", "S4 헛잡음"), ("S6", "S6 들다 놓침"),
            ("S8", "S8 칸 위로 못 감"), ("S9", "S9 꽂지 못함"), ("", "성공 (S9까지 통과)")]
    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    ys = np.arange(len(cats))[::-1]
    h = 0.36
    for j, (m, name, col, _) in enumerate(MODELS):
        C = [t for t in counted(T) if t["model"] == m]
        v = [sum(1 for t in C if t["first_fail"] == c) for c, _ in cats]
        y = ys + (0.5 - j) * h
        ax.barh(y, v, height=h * 0.92, color=col, label=f"{name} (n={len(C)})", zorder=2)
        for yy, vv in zip(y, v):
            ax.text(vv + 0.2, yy, str(vv), va="center", fontsize=9, color=INK2)
    ax.set_yticks(ys, [lab for _, lab in cats])
    ax.set_xlabel("판 수")
    ax.set_xlim(0, 18.5)
    ax.set_xticks(range(0, 19, 2))
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper right", fontsize=9.5)
    heading(fig, "판마다 처음 막힌 단계", "S6 · S8에서 처음 막힌 판은 두 모델 모두 없었다")
    fig.savefig(FIG / "fig_first_fail.png")
    plt.close(fig)


# ── 3. 배치별 성공과 두 날의 배치 차이 ────────────────────────────────
def fig_layout_success(T, LAY):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9.6, 5.8), sharex=True, gridspec_kw={"height_ratios": [1.5, 1], "hspace": 0.12})
    xs = np.arange(1, 11)
    w = 0.38
    for j, (m, name, col, _) in enumerate(MODELS):
        C = [t for t in counted(T) if t["model"] == m]
        v = [sum(1 for t in C if int(t["layout"]) == n and t["verdict"] == "success") for n in xs]
        a1.bar(xs + (j - 0.5) * w, v, width=w * 0.92, color=col, label=name, zorder=2)
        for x, vv in zip(xs + (j - 0.5) * w, v):
            if vv == 0:                                          # 0판도 빈자리와 구분되게
                a1.text(x, 0.04, "0", ha="center", va="bottom", fontsize=8.5, color=col)
    a1.set_ylim(0, 3.4)
    a1.set_yticks([0, 1, 2, 3], ["0/3", "1/3", "2/3", "3/3"])
    a1.set_ylabel("성공")
    a1.grid(axis="x", visible=False)
    a1.legend(loc="upper right", ncol=2, fontsize=9.5)
    L_ = {int(r["layout"]): r for r in LAY}
    for key, lab, mk, col in (("diff_red_mm", "빨간 튜브", "o", INK), ("diff_ring_mm", "링 칸", "s", MUTE)):
        v = [fl(L_[n][key]) if n in L_ else None for n in xs]
        x2 = [x for x, y in zip(xs, v) if y is not None]
        y2 = [y for y in v if y is not None]
        a2.scatter(x2, y2, marker=mk, s=42, color=col, edgecolor=BG, linewidth=1, zorder=3, label=lab)
        for x, y in zip(xs, v):
            if y is None:
                a2.text(x + (0.18 if key == "diff_ring_mm" else -0.18), 3, "–", ha="center", va="bottom", fontsize=9, color=MUTE)
    a2.set_ylim(0, 100)
    a2.set_ylabel("두 날 자리 차이 (mm)")
    a2.set_xticks(xs, [f"L{n}" for n in xs])
    a2.grid(axis="x", visible=False)
    a2.legend(loc="upper left", ncol=2, fontsize=9)
    heading(fig, "배치별 성공 (배치마다 3판)",
            "아래: 같은 배치 번호인데 1200판 날(11-12)과 200판 날(11-15)에 실제로 놓인 자리 차이 · 시작 장면 인식값 · L6 링 칸은 200판 날 인식 못 함")
    fig.savefig(FIG / "fig_layout_success.png")
    plt.close(fig)


# ── 4. 닫은 자리 − 빨간 튜브 중심 ──────────────────────────────────────
def fig_close_offsets(T):
    fig, axs = plt.subplots(1, 2, figsize=(10.2, 5.4), sharex=True, sharey=True)
    kinds = [("grip", "쥠 (S4 통과)", "o", OI["green"]), ("miss", "빨간 튜브 쪽에서 헛잡음", "X", OI["vermillion"]),
             ("other", "노란 튜브 쪽에서 닫음 (S1 실패)", "D", OI["purple"])]
    for ax, (m, name, col, _) in zip(axs, MODELS):
        C = [t for t in counted(T) if t["model"] == m and fl(t["close_x"]) is not None]
        ax.add_patch(Circle((0, 0), 25, fc="none", ec=MUTE, ls="--", lw=1.0, zorder=1))
        ax.text(0, -27, "25 mm", ha="center", va="bottom", fontsize=8, color=MUTE)
        ax.axhline(0, color=GRID, lw=1.0, zorder=0)
        ax.axvline(0, color=GRID, lw=1.0, zorder=0)
        for kind, lab, mk, c in kinds:
            P = []
            for t in C:
                k_ = "other" if t["S1"] == "0" else ("grip" if t["S4"] == "1" else "miss")
                if k_ == kind:
                    P.append((fl(t["close_x"]) - fl(t["red_x"]), fl(t["close_y"]) - fl(t["red_y"]), t))
            if P:
                ax.scatter([p[0] for p in P], [p[1] for p in P], marker=mk, s=46, color=c, edgecolor=BG, linewidth=0.8,
                           zorder=3, label=f"{lab} {len(P)}")
            for dx, dy, t in P:
                if kind != "grip":
                    ax.annotate(f"L{t['layout']}", (dx, dy), xytext=(4, 3), textcoords="offset points", fontsize=7.5, color=INK2)
        ax.set_xlim(-75, 75)
        ax.set_ylim(-75, 75)
        camera_view(ax)
        ax.set_title(f"{name} (n={len(C)})", color=col)
        ax.set_xlabel("Δx (mm, 로봇 x+ = 화면 왼쪽)")
        ax.legend(loc="lower left", fontsize=8.5, handletextpad=0.3)
    axs[0].set_ylabel("Δy (mm, 로봇 y+ = 화면 아래)")
    heading(fig, "처음 그리퍼를 닫은 자리 − 빨간 튜브 중심",
            "판마다 점 하나 · 3인칭 카메라에서 본 방향 · 빨간 튜브 자리는 그 판 시작 장면 인식값 · 받침 구멍 간격 37.2 mm")
    fig.savefig(FIG / "fig_close_offsets.png")
    plt.close(fig)


# ── 5. 학습 데이터 자리와 평가 배치 ──────────────────────────────────
def fig_layouts_train(LAY, TP):
    fig, axs = plt.subplots(2, 1, figsize=(9.6, 9.0), sharex=True, sharey=True, gridspec_kw={"hspace": 0.18})
    for ax, (key, tk, title) in zip(axs, (("red", "red", "빨간 튜브 자리"), ("ring", "slot", "링 칸 자리"))):
        tx = [fl(r[f"{tk}_x"]) for r in TP if fl(r[f"{tk}_x"]) is not None]
        ty = [fl(r[f"{tk}_y"]) for r in TP if fl(r[f"{tk}_x"]) is not None]
        ax.scatter(tx, ty, s=10, color="#B9B9B4", lw=0, zorder=1, label=f"학습 실물 200판 ({len(tx)})")
        for r in LAY:
            pts = []
            for m, name, col, mk in MODELS:
                x, y = fl(r[f"{m}_{key}_x"]), fl(r[f"{m}_{key}_y"])
                if x is not None:
                    pts.append((x, y))
                    ax.scatter([x], [y], marker=mk, s=60, color=col, edgecolor=BG, linewidth=1, zorder=3)
            if len(pts) == 2:
                ax.plot([pts[0][0], pts[1][0]], [pts[0][1], pts[1][1]], color=INK2, lw=0.8, zorder=2)
            if pts:
                ax.annotate(f"L{r['layout']}", pts[0], xytext=(-6, -9), textcoords="offset points", fontsize=8.5, color=INK,
                            ha="left")
        camera_view(ax)
        ax.set_title(title)
        ax.set_ylabel("로봇 y (mm) · 화면 아래가 +")
    axs[1].set_xlabel("로봇 x (mm) · 화면 왼쪽이 +")
    h = [Line2D([], [], ls="", marker="o", ms=4, color="#B9B9B4", label="학습 실물 200판"),
         Line2D([], [], ls="", marker="o", ms=7, color=OI["blue"], label="평가 배치 · 1200판 날 (11-12)"),
         Line2D([], [], ls="", marker="^", ms=7, color=OI["orange"], label="평가 배치 · 200판 날 (11-15)")]
    axs[1].legend(handles=h, loc="lower right", fontsize=8.5)
    heading(fig, "학습 데이터 자리와 평가 배치",
            "회색 점: 자동 수집 200판에서 집은 빨간 튜브 · 꽂은 칸 자리 · 평가 배치는 두 날 각각 센 판의 가운데값, 선으로 이음")
    fig.savefig(FIG / "fig_layouts_train.png")
    plt.close(fig)


# ── 6. 학습 손실 ──────────────────────────────────────────────────
def fig_train_loss(LOSS):
    fig, ax = plt.subplots(figsize=(8.6, 4.2))
    st = np.array([fl(r["step"]) for r in LOSS])
    for m, name, col, _ in MODELS:
        k = "loss_1200" if m == "1200" else "loss_200"
        y = np.array([fl(r[k]) if fl(r[k]) is not None else np.nan for r in LOSS])
        ax.plot(st, y, color=col, lw=0.5, alpha=0.25, zorder=1)
        h, ly = 25, np.log(y)                                    # 가운데 맞춘 500 스텝 창(양 끝은 창을 줄임), 로그 평균
        sm = np.exp([np.nanmean(ly[max(0, i - h):i + h + 1]) for i in range(len(ly))])
        ax.plot(st, sm, color=col, lw=2.0, zorder=2, label=f"{LONG[m]} · 마지막 {y[-1]:.4f}")
    ax.set_yscale("log")
    ax.set_xlabel("학습 스텝 (배치 64)")
    ax.set_ylabel("학습 손실 (flow matching)")
    ax.set_xlim(0, 20000)
    ax.legend(loc="upper right", fontsize=9.5)
    heading(fig, "학습 손실", "10 스텝마다 기록 · 굵은 선은 500 스텝 이동 평균 · 검증 세트는 두지 않았다")
    fig.savefig(FIG / "fig_train_loss.png")
    plt.close(fig)


# ── 7. 한 판의 시간축 ─────────────────────────────────────────────
def fig_timeline(TL, tag="200판 L9-1 (성공)"):
    if not TL:
        return
    t = np.array([fl(r["t_s"]) for r in TL])
    z = np.array([fl(r["z_mm"]) for r in TL])
    w = np.array([fl(r["width_mm"]) for r in TL])
    ev = json.loads((DATA / "timeline_200_L9-1_events.json").read_text())
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9.6, 4.8), sharex=True, gridspec_kw={"hspace": 0.12})
    a1.plot(t, z, color=INK, lw=1.8)
    a1.set_ylabel("손끝 높이 z (mm)")
    a2.plot(t, w, color=OI["blue"], lw=1.8)
    a2.set_ylabel("손가락 폭 (mm)")
    a2.set_xlabel("실행 시작부터 (s)")
    a2.set_ylim(-3, 100)
    for ax in (a1, a2):
        ax.grid(axis="x", visible=False)
        for k, lab in (("close", "닫기"), ("open", "열기")):
            if ev.get(k) is not None:
                ax.axvline(ev[k], color=MUTE, ls="--", lw=1)
    for k, lab in (("close", "닫기"), ("open", "열기")):
        if ev.get(k) is not None:
            a1.text(ev[k] + 0.3, a1.get_ylim()[1], lab, va="top", fontsize=9, color=INK2)
    if ev.get("over_ring") is not None:
        a1.annotate(f"쥔 채 링 칸 {ev['over_ring_mm']:.0f} mm 안", (ev["over_ring"], np.interp(ev["over_ring"], t, z)),
                    xytext=(10, 18), textcoords="offset points", fontsize=9, color=INK2,
                    arrowprops={"arrowstyle": "-", "color": MUTE, "lw": 0.8})
    heading(fig, f"한 판의 손끝 높이와 손가락 폭 — {tag}",
            f"10 Hz 실측 · 닫고 3 s 뒤 폭 {ev.get('width_3s', 0):.1f} mm · 들어 올린 높이 {ev.get('lift_mm', 0):.0f} mm")
    fig.savefig(FIG / "fig_timeline_200_L9-1.png")
    plt.close(fig)


def main():
    FIG.mkdir(exist_ok=True)
    T, LAY, TP, LOSS = rd("trials.csv"), rd("layouts.csv"), rd("train_positions.csv"), rd("train_loss.csv")
    fig_stage_cumulative(T)
    fig_first_fail(T)
    fig_layout_success(T, LAY)
    fig_close_offsets(T)
    fig_layouts_train(LAY, TP)
    fig_train_loss(LOSS)
    fig_timeline(rd("timeline_200_L9-1.csv"))
    print("figs:", ", ".join(sorted(p.name for p in FIG.glob("fig_*.png"))))


if __name__ == "__main__":
    main()
