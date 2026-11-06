#!/usr/bin/env python3
"""fig/*.png 를 data/*.csv 에서 다시 만든다.

    python3 tools/make_figures.py

색은 Okabe & Ito (2008) 팔레트. 좌표는 로봇 베이스 기준 mm (x 좌우, y 앞).
"""
import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Circle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA, FIG = ROOT / "data", ROOT / "fig"

OI = {"orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73", "yellow": "#F0E442",
      "blue": "#0072B2", "vermillion": "#D55E00", "purple": "#CC79A7", "black": "#000000"}
INK, INK2, GRID = "#222222", "#555555", "#DDDDDD"

plt.rcParams.update({
    "font.family": ["Noto Sans CJK KR", "Noto Sans CJK JP", "DejaVu Sans"],
    "font.size": 10, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "figure.dpi": 150, "savefig.dpi": 150, "savefig.bbox": "tight", "axes.titleweight": "bold",
    "axes.titlesize": 11, "legend.frameon": False,
})

FIXED_RED = (8.1, 537.4)        # 고정 배치 — 벤치마크 기록 시작 장면 인식의 중앙값
FIXED_SLOT = (226.6, 458.0)


def rd(name):
    with open(DATA / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def wilson(k, n, z=1.959964):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def ramp(hex_color):
    return LinearSegmentedColormap.from_list("r", ["#FFFFFF", hex_color])


# ------------------------------------------------------------------ 1. 학습 배치 분포
def fig_train_layout(T):
    red = np.array([[float(t["red_x"]), float(t["red_y"])] for t in T])
    slot = np.array([[float(t["slot_x"]), float(t["slot_y"])] for t in T])
    both80 = sum(max(math.dist(r, FIXED_RED), math.dist(s, FIXED_SLOT)) < 80 for r, s in zip(red, slot))
    gx, gy = np.meshgrid(np.arange(-280, 341, 5), np.arange(390, 701, 5))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    for ax, P, fx, col, title, who in ((axes[0], red, FIXED_RED, OI["vermillion"], "빨간 튜브를 잡은 자리", "튜브"),
                                       (axes[1], slot, FIXED_SLOT, OI["blue"], "튜브를 꽂은 링 칸 자리", "링 칸")):
        cnt = np.zeros_like(gx, dtype=float)
        for x, y in P:
            cnt += np.hypot(gx - x, gy - y) < 50
        im = ax.pcolormesh(gx, gy, np.ma.masked_less(cnt, 0.5), cmap=ramp(col), vmin=0, vmax=max(8, cnt.max()), shading="auto", alpha=0.55)
        ax.scatter(P[:, 0], P[:, 1], s=13, color=col, edgecolor="white", linewidth=0.4, zorder=3, label=f"학습 판 ({len(P)})")
        n80 = int(sum(math.dist(p, fx) < 80 for p in P))
        ax.add_patch(Circle(fx, 80, fill=False, ls="--", lw=1.2, ec=INK, zorder=4))
        ax.scatter([fx[0]], [fx[1]], marker="X", s=110, color=INK, edgecolor="white", linewidth=0.8, zorder=5, label="벤치마크 고정 배치")
        ax.set_xlim(-280, 340)
        ax.set_ylim(390, 700)
        ax.set_aspect("equal")
        ax.set_title(f"{title} (200판)\n", loc="left")
        ax.text(0, 1.015, f"✕ 고정 배치 {who} · 점선 반경 80 mm 안 학습 판 {n80}", transform=ax.transAxes, fontsize=9, color=INK2)
        ax.set_xlabel("x 좌우 (mm, 로봇 베이스)")
        ax.set_ylabel("y 앞 (mm)")
        cb = fig.colorbar(im, ax=ax, orientation="horizontal", shrink=0.6, pad=0.2, aspect=40)
        cb.set_label("반경 50 mm 안 학습 판 수", color=INK2)
        cb.outline.set_visible(False)
        ax.legend(loc="lower left", fontsize=8.5, frameon=True, facecolor="white", edgecolor="none", framealpha=0.85)
    fig.suptitle(f"학습 데이터 배치 분포 — 고정 배치는 튜브·링 칸 둘 다 80 mm 안에 드는 학습 판이 {both80}판뿐이다",
                 x=0.01, y=1.02, ha="left", fontsize=11.5, color=INK)
    fig.savefig(FIG / "train_layout.png")
    plt.close(fig)


# ------------------------------------------------------------------ 2. 배치 통계
def fig_layout_stats(T):
    dist = np.array([math.dist((float(t["red_x"]), float(t["red_y"])), (float(t["slot_x"]), float(t["slot_y"]))) for t in T])
    same = np.array([t["src_rack"] == t["dst_rack"] for t in T])
    dur = np.array([float(t["dur_s"]) for t in T])
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), gridspec_kw={"width_ratios": [1.35, 1, 1]})
    ax = axes[0]
    bins = np.arange(0, 525, 25)
    ax.hist([dist[same], dist[~same]], bins=bins, stacked=True, color=[OI["orange"], OI["sky"]], edgecolor="white", linewidth=1.0,
            label=[f"같은 받침 안 ({same.sum()})", f"다른 받침으로 ({(~same).sum()})"])
    ax.axvline(100, color=INK2, lw=0.9, ls="--")
    ax.text(104, ax.get_ylim()[1] * 0.92, f"100 mm 이하 {int((dist <= 100).sum())}판", fontsize=8.5, color=INK)
    ax.set_title("옮긴 거리", loc="left")
    ax.set_xlabel("튜브 자리 → 링 칸 (mm)")
    ax.set_ylabel("판 수")
    ax.legend(fontsize=8.5)
    ax = axes[1]
    sh = np.array([int(t["src_hole"]) for t in T])
    dh = np.array([int(t["dst_hole"]) for t in T])
    x = np.arange(4)
    ax.bar(x - 0.2, [int((sh == i).sum()) for i in x], 0.38, color=OI["vermillion"], label="튜브를 뺀 칸")
    ax.bar(x + 0.2, [int((dh == i).sum()) for i in x], 0.38, color=OI["blue"], label="꽂은 칸")
    ax.axhline(50, color=INK2, lw=0.8, ls=":", label="고르게면 50")
    ax.set_ylim(0, 82)
    ax.set_xticks(x, [f"{i}번" for i in x])
    ax.set_title("받침 칸 번호", loc="left")
    ax.set_ylabel("판 수")
    ax.legend(fontsize=8.5, loc="upper center", ncol=3, handlelength=1.4, columnspacing=0.8)
    ax = axes[2]
    ax.hist(dur, bins=np.arange(14, 30, 1), color=OI["green"], edgecolor="white", linewidth=1.0)
    ax.set_title("판 길이", loc="left")
    ax.set_xlabel("초 (10 Hz 기록)")
    ax.set_ylabel("판 수")
    ax.text(0.02, 0.92, f"중앙 {np.median(dur):.1f} s", transform=ax.transAxes, fontsize=8.5, color=INK)
    fig.tight_layout()
    fig.savefig(FIG / "layout_stats.png")
    plt.close(fig)


# ------------------------------------------------------------------ 3. 성공률
def fig_success(S):
    cols = [OI["black"], OI["blue"], OI["green"]]
    fig, ax = plt.subplots(figsize=(8.6, 2.9))
    for i, (s, c) in enumerate(zip(S, cols)):
        k, n = int(s["success"]), int(s["trials"])
        lo, hi = wilson(k, n)
        y = len(S) - 1 - i
        ax.plot([lo * 100, hi * 100], [y, y], color=c, lw=2.2, solid_capstyle="round")
        ax.scatter([k / n * 100], [y], s=70, color=c, edgecolor="white", linewidth=1.2, zorder=3)
        ax.text(hi * 100 + 1.5, y, f"{k}/{n} = {k / n * 100:.0f}%   (95% {lo * 100:.0f}–{hi * 100:.0f}%)", va="center", fontsize=9.5, color=INK)
        ax.text(-1.5, y - 0.33, s["source"], va="center", ha="left", fontsize=7.5, color=INK2)
    ax.set_yticks(range(len(S)), [s["condition"] for s in reversed(S)])
    ax.set_xlim(-2, 85)
    ax.set_ylim(-0.7, len(S) - 0.4)
    ax.set_xlabel("성공률 (%) — 점: 관측값, 선: Wilson 95% 구간")
    ax.grid(axis="y", visible=False)
    ax.set_title("실물 벤치마크 성공률 (같은 과제, 시행 30회씩)", loc="left")
    fig.savefig(FIG / "success_rate.png")
    plt.close(fig)


# ------------------------------------------------------------------ 4. 결과 구성
def fig_breakdown(F, Rn):
    c = {k: 0 for k in ("성공", "꽂기 실패", "잡은 뒤 실패·부분", "잡기 실패")}
    for r in F:
        cat = r["category"]
        key = "성공" if cat == "성공" else "잡기 실패" if cat.startswith("잡기") else "꽂기 실패" if cat.startswith("꽂기") else "잡은 뒤 실패·부분"
        c[key] += 1
    rnd = {"성공": sum(int(r["success"]) for r in Rn), "꽂기 실패": sum(int(r["place_miss"]) for r in Rn),
           "잡은 뒤 실패·부분": sum(int(r["after_grasp_fail"]) for r in Rn), "잡기 실패": sum(int(r["grasp_fail"]) for r in Rn)}
    rows = [("고정 배치 30회\n(벤치마크 기록)", c), ("랜덤 배치 30회\n(운영자 집계, 근사)", rnd)]
    colors = {"성공": OI["green"], "꽂기 실패": OI["orange"], "잡은 뒤 실패·부분": OI["sky"], "잡기 실패": OI["vermillion"]}
    fig, ax = plt.subplots(figsize=(9.2, 2.8))
    for i, (name, d) in enumerate(rows):
        y, left = 1 - i, 0
        for k, v in d.items():
            if v:
                ax.barh(y, v, left=left, height=0.55, color=colors[k], edgecolor="white", linewidth=2)
                ax.text(left + v / 2, y, str(v), ha="center", va="center", fontsize=9.5, color="white" if k in ("성공", "잡기 실패") else INK,
                        fontweight="bold")
            left += v
        grasp = d["성공"] + d["꽂기 실패"] + d["잡은 뒤 실패·부분"]
        ax.text(30.6, y, f"잡기 {grasp}/30 · 잡은 뒤 성공 {d['성공']}/{grasp}", va="center", fontsize=9, color=INK)
    ax.set_yticks([1, 0], [r[0] for r in rows])
    ax.set_xlim(0, 44)
    ax.set_xticks(range(0, 31, 5))
    ax.set_xlabel("시행 수")
    ax.grid(axis="y", visible=False)
    ax.spines["bottom"].set_bounds(0, 30)
    handles = [plt.Rectangle((0, 0), 1, 1, color=colors[k]) for k in colors]
    fig.subplots_adjust(top=0.74)
    fig.text(0.01, 0.97, "시행 결과 구성", fontsize=11, fontweight="bold", color=INK, va="top")
    fig.legend(handles, list(colors), ncol=4, loc="upper left", bbox_to_anchor=(0.01, 0.89), fontsize=9)
    fig.savefig(FIG / "outcome_breakdown.png")
    plt.close(fig)


# ------------------------------------------------------------------ 5. 학습 데이터 예시
def fig_frames():
    from PIL import Image
    fr = DATA / "frames"
    eps = sorted({p.name[:6] for p in fr.glob("ep_*_third_*.jpg")})
    if not eps:
        return
    fig, axes = plt.subplots(2 * len(eps), 4, figsize=(11, 1.6 * 2 * len(eps) + 0.3))
    heads = ["시작", "1/3 지점", "2/3 지점", "끝"]
    for i, ep in enumerate(eps):
        for r, cam, lab in ((2 * i, "third", "3인칭"), (2 * i + 1, "wrist", "손목")):
            files = sorted(fr.glob(f"{ep}_{cam}_*.jpg"))
            for j, f in enumerate(files[:4]):
                ax = axes[r, j]
                ax.imshow(Image.open(f))
                ax.set_xticks([])
                ax.set_yticks([])
                for s in ax.spines.values():
                    s.set_visible(False)
                ax.grid(False)
                if r == 0:
                    ax.set_title(heads[j], fontsize=10, color=INK)
                if j == 0:
                    ax.set_ylabel(f"{ep}\n{lab}", fontsize=9, color=INK)
                ax.text(0.98, 0.04, f"{int(f.stem.split('_')[-1]) / 10:.1f} s", transform=ax.transAxes, ha="right", fontsize=7.5,
                        color="white", bbox=dict(boxstyle="round,pad=0.15", fc="#00000088", ec="none"))
    fig.subplots_adjust(wspace=0.02, hspace=0.04)
    fig.savefig(FIG / "dataset_frames.jpg", pil_kwargs={"quality": 85})
    plt.close(fig)


# ------------------------------------------------------------------ 6. 고정 배치에서 닫은 자리
def fig_close(F):
    fig, ax = plt.subplots(figsize=(5.4, 5.0))
    ax.add_patch(Circle((0, 0), 14.3, fill=False, ec=INK2, lw=1.0, ls="--"))
    ax.text(11, 11, "튜브 지름\n28.6 mm", ha="left", va="bottom", fontsize=8, color=INK2)
    for ok, col, lab in ((True, OI["green"], "잡음"), (False, OI["vermillion"], "빈손으로 닫음")):
        P = [(float(r["close_x"]) - FIXED_RED[0], float(r["close_y"]) - FIXED_RED[1]) for r in F
             if r["close_x"] != "" and (r["grasp"] == "1") == ok]
        if P:
            P = np.array(P)
            med = float(np.median(np.hypot(P[:, 0], P[:, 1])))
            ax.scatter(P[:, 0], P[:, 1], s=46, color=col, edgecolor="white", linewidth=0.8, zorder=3,
                       label=f"{lab} {len(P)}회 · 중앙 {med:.0f} mm")
    ax.axhline(0, color=GRID, lw=0.8)
    ax.axvline(0, color=GRID, lw=0.8)
    ax.set_xlim(-40, 40)
    ax.set_ylim(-40, 40)
    ax.set_aspect("equal")
    ax.set_xlabel("x 좌우 차이 (mm)")
    ax.set_ylabel("y 앞 차이 (mm) — 음수 = 로봇 쪽")
    ax.set_title("고정 배치: 그리퍼를 닫은 자리 − 튜브 자리", loc="left")
    ax.legend(loc="upper left", fontsize=8.5)
    fig.savefig(FIG / "fixed_close_offset.png")
    plt.close(fig)


# ------------------------------------------------------------------ 7. 정책이 보는 두 화면
def fig_views():
    from PIL import Image
    a, b = DATA / "frames" / "ep_080_third_00000.jpg", DATA / "frames" / "ep_080_wrist_00000.jpg"
    if not (a.is_file() and b.is_file()):
        return
    fig, axes = plt.subplots(1, 2, figsize=(10, 2.95))
    for ax, f, t in ((axes[0], a, "3인칭 (agentview)"), (axes[1], b, "손목 (wrist)")):
        ax.imshow(Image.open(f))
        ax.set_title(t, fontsize=10, color=INK, loc="left")
        ax.axis("off")
    fig.subplots_adjust(wspace=0.03)
    fig.savefig(FIG / "views.jpg", pil_kwargs={"quality": 88})
    plt.close(fig)


def main():
    FIG.mkdir(exist_ok=True)
    T = rd("train_layouts.csv")
    fig_train_layout(T)
    fig_layout_stats(T)
    fig_success(rd("bench_summary.csv"))
    fig_breakdown(rd("bench_fixed_30.csv"), rd("bench_random_30.csv"))
    fig_close(rd("bench_fixed_30.csv"))
    fig_frames()
    fig_views()
    print("그림:", ", ".join(sorted(p.name for p in FIG.iterdir())))


if __name__ == "__main__":
    main()
