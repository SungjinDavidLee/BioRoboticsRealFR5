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
    gx, gy = np.meshgrid(np.arange(-280, 341, 5), np.arange(390, 701, 5))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    for ax, P, col, title in ((axes[0], red, OI["vermillion"], "빨간 튜브를 잡은 자리"),
                              (axes[1], slot, OI["blue"], "튜브를 꽂은 링 칸 자리")):
        cnt = np.zeros_like(gx, dtype=float)
        for x, y in P:
            cnt += np.hypot(gx - x, gy - y) < 50
        im = ax.pcolormesh(gx, gy, np.ma.masked_less(cnt, 0.5), cmap=ramp(col), vmin=0, vmax=max(8, cnt.max()), shading="auto", alpha=0.55)
        ax.scatter(P[:, 0], P[:, 1], s=13, color=col, edgecolor="white", linewidth=0.4, zorder=3, label=f"학습 판 ({len(P)})")
        ax.set_xlim(-280, 340)
        ax.set_ylim(390, 700)
        ax.set_aspect("equal")
        ax.set_title(f"{title} (200판)", loc="left")
        ax.set_xlabel("x 좌우 (mm, 로봇 베이스)")
        ax.set_ylabel("y 앞 (mm)")
        cb = fig.colorbar(im, ax=ax, orientation="horizontal", shrink=0.6, pad=0.2, aspect=40)
        cb.set_label("반경 50 mm 안 학습 판 수", color=INK2)
        cb.outline.set_visible(False)
        ax.legend(loc="lower left", fontsize=8.5, frameon=True, facecolor="white", edgecolor="none", framealpha=0.85)
    fig.suptitle("학습 데이터 배치 분포 — 작업대 위 튜브 자리와 링 칸 자리", x=0.01, y=1.02, ha="left", fontsize=11.5, color=INK)
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
    cols = [OI["black"], OI["green"]]
    fig, ax = plt.subplots(figsize=(8.6, 2.2))
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
    ax.set_title("실물 성공률 — 랜덤 배치, 시행 30회씩", loc="left")
    fig.savefig(FIG / "success_rate.png")
    plt.close(fig)


# ------------------------------------------------------------------ 4. 결과 구성 (200판 정책, 랜덤 배치)
def fig_breakdown(Rn, Lay):
    d = {"성공": sum(int(r["success"]) for r in Rn), "꽂기 실패": sum(int(r["place_miss"]) for r in Rn),
         "잡은 뒤 실패": sum(int(r["after_grasp_fail"]) for r in Rn), "잡기 실패": sum(int(r["grasp_fail"]) for r in Rn)}
    colors = {"성공": OI["green"], "꽂기 실패": OI["orange"], "잡은 뒤 실패": OI["sky"], "잡기 실패": OI["vermillion"]}
    fig, axes = plt.subplots(1, 2, figsize=(11, 2.9), gridspec_kw={"width_ratios": [2.2, 1], "wspace": 0.28})
    ax = axes[0]
    left = 0
    for k, v in d.items():
        if v:
            ax.barh(0, v, left=left, height=0.5, color=colors[k], edgecolor="white", linewidth=2, label=k)
            ax.text(left + v / 2, 0, str(v), ha="center", va="center", fontsize=10, fontweight="bold",
                    color="white" if k in ("성공", "잡기 실패") else INK)
        left += v
    grasp = d["성공"] + d["꽂기 실패"] + d["잡은 뒤 실패"]
    ax.set_xlim(0, 30)
    ax.set_ylim(-0.6, 0.9)
    ax.set_yticks([])
    ax.set_xticks(range(0, 31, 5))
    ax.set_xlabel("시행 수 (30회)")
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.legend(ncol=4, loc="upper left", bbox_to_anchor=(0, 1.02), fontsize=9, handlelength=1.2)
    ax.set_title(f"30회 결과 구성 — 잡기 {grasp}/30, 잡은 뒤 성공 {d['성공']}/{grasp} (운영자 집계)", loc="left")
    ax = axes[1]
    k = [int(r["successes_in_3"]) for r in Lay]
    n = [int(r["layouts"]) for r in Lay]
    ax.bar(k, n, 0.6, color=[OI["vermillion"] if i == 0 else OI["green"] for i in k], edgecolor="white")
    for i, v in zip(k, n):
        ax.text(i, v + 0.15, str(v), ha="center", fontsize=9.5, color=INK)
    ax.set_xticks(k, [f"{i}/3" for i in k])
    ax.set_ylim(0, max(n) + 1.2)
    ax.set_xlabel("배치 하나에서 성공한 횟수")
    ax.set_ylabel("배치 수")
    ax.set_title(f"배치 {sum(n)}개 × 3회", loc="left")
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


# ------------------------------------------------------------------ 6. 시연 한 판의 움직임
def fig_motion(M):
    eps = {}
    for r in M:
        eps.setdefault(r["ep"], []).append((float(r["t_s"]), float(r["x_mm"]), float(r["y_mm"]), float(r["z_mm"]), float(r["grip_mm"])))
    fig = plt.figure(figsize=(12, 5.2))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.45, 1], height_ratios=[1.25, 1], hspace=0.12, wspace=0.18)
    az, ag, ax = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[:, 1])
    grid = np.arange(-7.0, 21.01, 0.1)
    Z, Gw, opens = [], [], []
    for ep, A in eps.items():
        A = np.array(A)
        t, g = A[:, 0], A[:, 4]
        ic = int(np.argmax(g < 34))
        io = next((k for k in range(ic + 1, len(g)) if g[k] > 20 and g[ic:k].min() < 20), None)
        tt = t - t[ic]
        az.plot(tt, A[:, 3], color=INK2, lw=0.4, alpha=0.18)
        ag.plot(tt, g, color=INK2, lw=0.4, alpha=0.18)
        Z.append(np.interp(grid, tt, A[:, 3], left=np.nan, right=np.nan))
        Gw.append(np.interp(grid, tt, g, left=np.nan, right=np.nan))
        if io is not None:
            opens.append(tt[io])
        held = slice(ic, (io or len(A)) + 1)
        ax.plot(A[: ic + 1, 1], A[: ic + 1, 2], color=OI["vermillion"], lw=0.5, alpha=0.35)
        ax.plot(A[held, 1], A[held, 2], color=OI["blue"], lw=0.5, alpha=0.35)
    with np.errstate(all="ignore"):
        Zm, Gm = np.nanmedian(np.array(Z), 0), np.nanmedian(np.array(Gw), 0)
    ok = np.sum(~np.isnan(np.array(Z)), 0) >= 100
    az.plot(grid[ok], Zm[ok], color=OI["black"], lw=2, label="중앙값")
    ag.plot(grid[ok], Gm[ok], color=OI["black"], lw=2)
    to = float(np.median(opens))
    for a in (az, ag):
        a.axvline(0, color=OI["vermillion"], lw=1.2, ls="--")
        a.axvline(to, color=OI["blue"], lw=1.2, ls="--")
        a.set_xlim(-7, 20)
    az.text(0.2, 300, "닫기 시작", color=OI["vermillion"], fontsize=9)
    az.text(to + 0.2, 300, f"열기 시작 (중앙 +{to:.1f} s)", color=OI["blue"], fontsize=9)
    az.set_ylim(100, 315)
    az.set_ylabel("손끝 높이 z (mm)")
    az.set_xticklabels([])
    az.set_title(f"시연 {len(eps)}판 — 닫기 시작 시각에 맞춰 겹침", loc="left")
    az.legend(loc="lower left", fontsize=8.5)
    ag.set_ylim(0, 45)
    ag.set_ylabel("손가락 폭 (mm)")
    ag.set_xlabel("닫기 시작으로부터 시간 (s)")
    ax.scatter([eps[next(iter(eps))][0][1]], [eps[next(iter(eps))][0][2]], marker="s", s=60, color=INK, zorder=5, label="초기 자세")
    ax.plot([], [], color=OI["vermillion"], lw=2, label="잡기까지")
    ax.plot([], [], color=OI["blue"], lw=2, label="쥐고 옮기기")
    ax.set_aspect("equal")
    ax.set_xlim(-280, 340)
    ax.set_ylim(390, 700)
    ax.set_xlabel("x 좌우 (mm, 로봇 베이스)")
    ax.set_ylabel("y 앞 (mm)")
    ax.set_title("위에서 본 손끝 경로", loc="left")
    ax.legend(loc="upper left", fontsize=8.5, frameon=True, facecolor="white", edgecolor="none", framealpha=0.85)
    fig.savefig(FIG / "demo_motion.png")
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
    fig_breakdown(rd("bench_random_30.csv"), rd("bench_random_layouts.csv"))
    fig_motion(rd("train_motion.csv"))
    fig_frames()
    fig_views()
    print("그림:", ", ".join(sorted(p.name for p in FIG.iterdir())))


if __name__ == "__main__":
    main()
