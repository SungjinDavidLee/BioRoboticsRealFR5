#!/usr/bin/env python3
"""fr5rec 원본 → GR00T LeRobot v2.1 데이터셋 (Isaac-GR00T launch_finetune 용).

  python fr5_to_gr00t.py SRC OUT --resize {squash,crop,pad} [--size 256] [--outcome success|any]
                         [--workers 8] [--max-eps N] [--force]

SRC  fr5rec 데이터셋 폴더: ep_NNN/meta.json + rgb/NNNNN.png(3인칭) + wrist/NNNNN.png(손목)
OUT  새 폴더. 있으면 --force 없이는 멈춘다.

규약(B0 변환과 같은 뜻 — docs/TRAINING.md. 회전만 축각 → rot6d):
  meta 프레임 state = [x y z (m, 작업 프레임), 축각 3, g, -g]
  observation.state[11] = [x y z, rot6d 6, g, -g]   rot6d = 회전행렬 첫 두 행(GR00T pose.py 와 같은 규약)
  action[10]            = 다음 프레임 state 앞 10개 → action[t] == state[t+1][:10], 판의 마지막 프레임은 뺀다
  축각은 각이 π 근처에서 부호가 뒤집혀 값이 튄다(B0 ROTATION.md) — rot6d 는 연속이라 정규화·학습이 안정하다
  영상                 = rgb → observation.images.agentview, wrist → observation.images.wrist, 정사각 size×size
                         squash = PIL .convert("RGB").resize((size, size), BILINEAR) — 예전 to_lerobot_groot.py 135~138줄과 같음
  timestamp            = frame_index / fps (명목 — GR00T 는 프레임 번호로 영상을 읽는다)
읽기만 한다: SRC 는 바꾸지 않는다.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image

CHUNK = 1000
CAMS = (("rgb", "agentview"), ("wrist", "wrist"))
ANN = "annotation.human.task_description"
STATE_NAMES = ["x", "y", "z", "r00", "r01", "r02", "r10", "r11", "r12", "gripper", "gripper_neg"]
ACTION_NAMES = STATE_NAMES[:10]


def rotvec_to_rot6d(rv: np.ndarray) -> np.ndarray:
    """(N,3) 축각 → (N,6) 회전행렬 첫 두 행(행 순서로 펼침). 로드리게스 공식."""
    rv = np.asarray(rv, np.float64)
    th = np.linalg.norm(rv, axis=1, keepdims=True)
    k = np.divide(rv, th, out=np.zeros_like(rv), where=th > 1e-12)
    K = np.zeros((len(rv), 3, 3))
    K[:, 0, 1], K[:, 0, 2], K[:, 1, 0] = -k[:, 2], k[:, 1], k[:, 2]
    K[:, 1, 2], K[:, 2, 0], K[:, 2, 1] = -k[:, 0], -k[:, 1], k[:, 0]
    s, c = np.sin(th)[:, :, None], np.cos(th)[:, :, None]
    R = np.eye(3)[None] + s * K + (1 - c) * (K @ K)
    return R[:, :2, :].reshape(len(rv), 6)


def fr5_state(S8: np.ndarray) -> np.ndarray:
    """meta state(N,8) → (N,11) [xyz, rot6d, g, -g]."""
    return np.concatenate([S8[:, :3], rotvec_to_rot6d(S8[:, 3:6]), S8[:, 6:8]], axis=1)


def rotvec_flips(S8: np.ndarray) -> int:
    """이웃 프레임 축각이 1 rad 넘게 튄 횟수(같은 회전의 다른 표현으로 뒤집힌 것)."""
    return int(np.sum(np.linalg.norm(np.diff(S8[:, 3:6], axis=0), axis=1) > 1.0))


# ------------------------------------------------------------------ 영상
def to_square(img: np.ndarray, size: int, mode: str) -> np.ndarray:
    h, w = img.shape[:2]
    if mode == "crop":                                   # 가운데 정사각만 남김
        s = min(h, w)
        y0, x0 = (h - s) // 2, (w - s) // 2
        img = img[y0:y0 + s, x0:x0 + s]
    elif mode == "pad":                                  # 위아래(또는 좌우)를 검정으로 채워 정사각
        s = max(h, w)
        out = np.zeros((s, s, 3), img.dtype)
        y0, x0 = (s - h) // 2, (s - w) // 2
        out[y0:y0 + h, x0:x0 + w] = img
        img = out
    elif mode != "squash":                               # squash = 비율을 무시하고 바로 줄임
        raise ValueError(mode)
    return np.asarray(Image.fromarray(img).resize((size, size), Image.BILINEAR), dtype=np.uint8)


def load_rgb(p: Path) -> np.ndarray:
    """PNG → RGB uint8 (예전 변환기와 같은 PIL 경로)."""
    with Image.open(p) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


class Writer:
    """RGB 프레임 → mp4. ffmpeg(libx264, crf 18)가 있으면 그것, 없으면 OpenCV mp4v."""

    def __init__(self, path: Path, size: int, fps: float):
        self.path, self.n = path, 0
        self.proc = self.cv = None
        if shutil.which("ffmpeg"):
            self.kind = "h264"
            self.proc = subprocess.Popen(
                ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size}x{size}",
                 "-r", f"{fps:g}", "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                 "-pix_fmt", "yuv420p", "-g", "20", str(path)],
                stdin=subprocess.PIPE)
        else:
            self.kind = "mpeg4"
            self.cv = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (size, size))
            if not self.cv.isOpened():
                raise RuntimeError(f"영상 파일을 못 연다: {path}")

    def add(self, img):
        if self.proc is not None:
            self.proc.stdin.write(np.ascontiguousarray(img).tobytes())
        else:
            self.cv.write(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        self.n += 1

    def close(self):
        if self.proc is not None:
            self.proc.stdin.close()
            if self.proc.wait() != 0:
                raise RuntimeError(f"ffmpeg 실패: {self.path}")
        else:
            self.cv.release()


def codec_name() -> str:
    return "h264" if shutil.which("ffmpeg") else "mpeg4"


# ------------------------------------------------------------------ 원본 읽기
def list_episodes(src: Path) -> list[Path]:
    eps = [p for p in src.iterdir() if p.is_dir() and re.fullmatch(r"ep_\d{3,}", p.name) and (p / "meta.json").is_file()]
    return sorted(eps, key=lambda p: int(p.name[3:]))


def n_png(d: Path) -> int:
    return len(list(d.glob("[0-9]*.png"))) if d.is_dir() else 0


def scan(ep: Path) -> dict:
    """판 하나의 메타만 읽는다(영상은 안 읽음). 못 쓰면 why."""
    m = json.loads((ep / "meta.json").read_text())
    fr = m.get("frames") or []
    fx = m.get("fr5rec") or {}
    n = len(fr)
    nr, nw = n_png(ep / "rgb"), n_png(ep / "wrist")
    why = []
    if n < 2:
        why.append(f"프레임 {n}")
    if nr < n or nw < n:
        why.append(f"영상 부족(rgb {nr}·wrist {nw} < 프레임 {n})")
    bad = [i for i, f in enumerate(fr) if not (isinstance(f.get("state"), list) and len(f["state"]) == 8
                                                and all(isinstance(v, (int, float)) and math.isfinite(v) for v in f["state"]))]
    if bad:
        why.append(f"state 이상 프레임 {len(bad)}개(처음 {bad[0]})")
    return {"ep": ep.name, "path": str(ep), "n": n, "hz": m.get("hz"), "instr": m.get("instruction"),
            "outcome": m.get("outcome"), "scene": m.get("scene"), "hz_real": fx.get("hz_real"),
            "overruns": fx.get("overruns"), "stale": fx.get("stale"), "why": why}


# ------------------------------------------------------------------ 판 하나 쓰기
def convert_one(job: dict) -> dict:
    ep, out, size, mode, fps = Path(job["path"]), Path(job["out"]), job["size"], job["mode"], job["fps"]
    k, base, task = job["k"], job["base"], job["task"]
    m = json.loads((ep / "meta.json").read_text())
    S8 = np.asarray([f["state"] for f in m["frames"]], np.float64)
    S = fr5_state(S8)
    A = len(ACTION_NAMES)
    T = len(S) - 1                                       # 마지막 프레임은 다음 state 가 없어 뺀다
    state = S[:T].astype(np.float32)
    action = S[1:T + 1, :A].astype(np.float32)
    ch = k // CHUNK
    for cam, key in CAMS:
        vd = out / "videos" / f"chunk-{ch:03d}" / f"observation.images.{key}"
        vd.mkdir(parents=True, exist_ok=True)
        w = Writer(vd / f"episode_{k:06d}.mp4", size, fps)
        for i in range(T):
            try:
                img = load_rgb(ep / cam / f"{i:05d}.png")
            except Exception as e:                       # noqa: BLE001
                w.close()
                raise RuntimeError(f"{ep.name}/{cam}/{i:05d}.png 를 못 읽었다: {e}")
            w.add(to_square(img, size, mode))
        w.close()
    df = pd.DataFrame({
        "observation.state": list(state),
        "action": list(action),
        "timestamp": (np.arange(T) / fps).astype(np.float32),
        "frame_index": np.arange(T, dtype=np.int64),
        "episode_index": np.full(T, k, np.int64),
        "index": np.arange(base, base + T, dtype=np.int64),
        "task_index": np.full(T, task, np.int64),
        ANN: np.full(T, task, np.int64),
        "next.reward": np.zeros(T, np.float32),
        "next.done": np.arange(T) == T - 1,
    })
    dd = out / "data" / f"chunk-{ch:03d}"
    dd.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dd / f"episode_{k:06d}.parquet", index=False)
    return {"k": k, "T": T, "flips": rotvec_flips(S8)}


# ------------------------------------------------------------------ 메타
def write_meta(out: Path, rows: list[dict], tasks: list[str], fps: float, size: int):
    md = out / "meta"
    md.mkdir(parents=True, exist_ok=True)
    N, F = len(rows), sum(r["T"] for r in rows)
    vid = lambda: {"dtype": "video", "shape": [size, size, 3], "names": ["height", "width", "channels"],
                   "info": {"video.height": size, "video.width": size, "video.codec": codec_name(), "video.pix_fmt": "yuv420p",
                            "video.is_depth_map": False, "video.fps": fps, "video.channels": 3, "has_audio": False}}
    info = {
        "codebase_version": "v2.1", "robot_type": "fairino_fr5", "total_episodes": N, "total_frames": F,
        "total_tasks": len(tasks), "total_videos": N * len(CAMS), "total_chunks": (N - 1) // CHUNK + 1, "chunks_size": CHUNK,
        "fps": fps, "splits": {"train": f"0:{N}"},
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4",
        "features": {
            "action": {"dtype": "float32", "shape": [len(ACTION_NAMES)], "names": ACTION_NAMES},
            "observation.state": {"dtype": "float32", "shape": [len(STATE_NAMES)], "names": STATE_NAMES},
            **{f"observation.images.{key}": vid() for _, key in CAMS},
            "timestamp": {"dtype": "float32", "shape": [1], "names": None},
            "frame_index": {"dtype": "int64", "shape": [1], "names": None},
            "episode_index": {"dtype": "int64", "shape": [1], "names": None},
            "index": {"dtype": "int64", "shape": [1], "names": None},
            "task_index": {"dtype": "int64", "shape": [1], "names": None},
            ANN: {"dtype": "int64", "shape": [1], "names": None},
            "next.reward": {"dtype": "float32", "shape": [1], "names": None},
            "next.done": {"dtype": "bool", "shape": [1], "names": None},
        },
    }
    (md / "info.json").write_text(json.dumps(info, indent=4, ensure_ascii=False))
    with open(md / "tasks.jsonl", "w") as f:
        for i, t in enumerate(tasks):
            f.write(json.dumps({"task_index": i, "task": t}, ensure_ascii=False) + "\n")
    with open(md / "episodes.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps({"episode_index": r["k"], "tasks": [tasks[r["task"]]], "length": r["T"]}, ensure_ascii=False) + "\n")
    modality = {
        "state": {"eef": {"start": 0, "end": 9}, "gripper": {"start": 9, "end": 11}},
        "action": {"eef": {"start": 0, "end": 9}, "gripper": {"start": 9, "end": 10}},
        "video": {key: {"original_key": f"observation.images.{key}"} for _, key in CAMS},
        "annotation": {"human.task_description": {"original_key": ANN}},
    }
    (md / "modality.json").write_text(json.dumps(modality, indent=4))


# ------------------------------------------------------------------ 확인
def verify(out: Path, src_rows: list[dict], size: int, mode: str, picks: list[int]) -> list[str]:
    """action[t] == state[t+1][:10], rot6d → 원본 축각과 같은 회전, 행 수 == 영상 프레임 수, 영상 화질(PSNR)."""
    msgs = []
    try:
        from torchcodec.decoders import VideoDecoder          # GR00T 가 읽는 방식 그대로
        dec = "torchcodec"
    except Exception as e:                                   # noqa: BLE001
        VideoDecoder, dec = None, f"OpenCV(torchcodec 못 씀: {str(e).splitlines()[0][:60]})"
    for k in picks:
        r = src_rows[k]
        ch = k // CHUNK
        df = pd.read_parquet(out / "data" / f"chunk-{ch:03d}" / f"episode_{k:06d}.parquet")
        st, ac = np.stack(df["observation.state"].to_numpy()), np.stack(df["action"].to_numpy())
        A = ac.shape[1]
        a_err = float(np.abs(ac[:-1] - st[1:, :A]).max()) if len(st) > 1 else 0.0
        m = json.loads((Path(r["path"]) / "meta.json").read_text())
        S8 = np.asarray([f["state"] for f in m["frames"]], np.float64)[:len(st)]
        r_err = float(np.abs(fr5_state(S8)[:, 3:9] - st[:, 3:9]).max())     # float32 반올림만 남아야 한다
        for cam, key in CAMS:
            vp = out / "videos" / f"chunk-{ch:03d}" / f"observation.images.{key}" / f"episode_{k:06d}.mp4"
            idx = sorted({0, len(df) // 2, len(df) - 1})
            if VideoDecoder is not None:
                d = VideoDecoder(str(vp), dimension_order="NHWC")
                nv = d.metadata.num_frames
                frames = d.get_frames_at(indices=idx).data.numpy()                  # RGB
            else:
                cap = cv2.VideoCapture(str(vp))
                nv = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                allf = []
                while True:
                    ok, fr = cap.read()
                    if not ok:
                        break
                    allf.append(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
                frames = np.stack([allf[i] for i in idx])
            ps = []
            for j, i in enumerate(idx):
                ref = to_square(load_rgb(Path(r["path"]) / cam / f"{i:05d}.png"), size, mode).astype(np.float64)
                mse = float(np.mean((frames[j].astype(np.float64) - ref) ** 2))
                ps.append(99.0 if mse == 0 else 10 * math.log10(255.0 ** 2 / mse))
            msgs.append(f"  판 {k:3d}({r['ep']}) {key:9s} 행 {len(df)} · 영상 {nv} 프레임 · PSNR {min(ps):.1f} dB"
                        + ("" if nv == len(df) else "  ← 프레임 수 다름!"))
        msgs.append(f"  판 {k:3d} action[t] − state[t+1][:{A}] 최대 {a_err:.2e} · rot6d 재계산 차 {r_err:.1e}")
    msgs.insert(0, f"확인(영상 읽기: {dec})")
    return msgs


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--resize", required=True, choices=["squash", "crop", "pad"],
                    help="848×480 → 정사각: squash 비율 무시 · crop 가운데 정사각 · pad 검정 채움 (롤아웃이 보내는 영상과 같게)")
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--outcome", default="success", help="success(기본) | any")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-eps", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    src, out = a.src.expanduser().resolve(), a.out.expanduser().resolve()
    if out.exists():
        if not a.force:
            sys.exit(f"{out} 가 이미 있다 — 다른 이름을 주거나 --force")
        shutil.rmtree(out)
    eps = list_episodes(src)
    if not eps:
        sys.exit(f"{src} 에 ep_NNN/meta.json 이 없다")
    S = [scan(e) for e in eps]
    skip = [(s["ep"], "; ".join(s["why"])) for s in S if s["why"]]
    skip += [(s["ep"], f"outcome {s['outcome']}") for s in S if not s["why"] and a.outcome != "any" and s["outcome"] != a.outcome]
    bad = {e for e, _ in skip}
    use = [s for s in S if s["ep"] not in bad]
    if a.max_eps:
        use = use[:a.max_eps]
    if not use:
        sys.exit("쓸 판이 없다: " + "; ".join(f"{e} {w}" for e, w in skip[:5]))
    hzs = sorted({float(s["hz"]) for s in use if s["hz"]})
    if len(hzs) != 1:
        sys.exit(f"판마다 기록 주기가 다르다: {hzs} — 주기별로 나눠 변환한다")
    fps = hzs[0]
    tasks = sorted({s["instr"] for s in use if s["instr"]})
    if not tasks or any(not s["instr"] for s in use):
        sys.exit("지시문(instruction)이 없는 판이 있다")
    jobs, base = [], 0
    for k, s in enumerate(use):
        T = s["n"] - 1
        jobs.append({"path": s["path"], "out": str(out), "size": a.size, "mode": a.resize, "fps": fps,
                     "k": k, "base": base, "task": tasks.index(s["instr"])})
        s["k"], s["T"], s["task"] = k, T, tasks.index(s["instr"])
        base += T
    print(f"원본 {src.name}: 판 {len(S)} · 씀 {len(use)} · 뺌 {len(skip)} · {fps:g} Hz · 지시문 {tasks}")
    for e, w in skip:
        print(f"  뺌 {e}: {w}")
    print(f"영상 {codec_name()} {a.size}×{a.size} ({a.resize}) · 작업자 {a.workers}")
    done = []
    with ProcessPoolExecutor(max_workers=max(1, a.workers)) as ex:
        for i, r in enumerate(ex.map(convert_one, jobs), 1):
            done.append(r)
            if i % 10 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} 판 · {time.time() - t0:.0f} s", flush=True)
    write_meta(out, use, tasks, fps, a.size)
    fl = sum(r["flips"] for r in done)
    (out / "meta" / "fr5_source.json").write_text(json.dumps(
        {"src": str(src), "made": time.strftime("%Y-%m-%dT%H:%M:%S"), "resize": a.resize, "size": a.size, "fps": fps,
         "convention": "state=[xyz, rot6d(rows 0-1 of R from meta rotvec), g, -g](11); action[t]=state[t+1][:10]; last frame dropped",
         "episodes": [{k_: s[k_] for k_ in ("k", "ep", "T", "hz_real", "overruns", "stale", "outcome", "scene")} for s in use],
         "skipped": [{"ep": e, "why": w} for e, w in skip]}, ensure_ascii=False, indent=1))
    F = sum(s["T"] for s in use)
    L = np.array([s["T"] for s in use])
    hr = [float(s["hz_real"]) for s in use if s.get("hz_real")]
    print(f"\n완료 {out}  ({time.time() - t0:.0f} s)")
    print(f"판 {len(use)} · 프레임 {F} · 판 길이 프레임 최소 {L.min()} / 중앙 {int(np.median(L))} / 최대 {L.max()}"
          f" (= {L.min() / fps:.1f} / {np.median(L) / fps:.1f} / {L.max() / fps:.1f} s)")
    if hr:
        print(f"실제 기록 주기 최소 {min(hr):.2f} / 중앙 {float(np.median(hr)):.2f} Hz")
    print(f"원본 축각이 뒤집혀 튄 곳 {fl}번(판 {sum(1 for r in done if r['flips'])}개) — rot6d 로 바꿔 학습에는 영향 없음")
    print("에폭(= 스텝 × batch ÷ 프레임):")
    for bs in (16, 32, 64):
        print(f"  batch {bs:2d}: " + " · ".join(f"{st} 스텝 {st * bs / F:.1f}" for st in (7000, 14000, 20000)))
    picks = sorted({0, len(use) // 2, len(use) - 1})
    for line in verify(out, use, a.size, a.resize, picks):
        print(line)


if __name__ == "__main__":
    main()
