#!/usr/bin/env python3
"""FR5 받침 과제 GR00T N1.7 정책 서버 (학습 서버에서 실행, HTTP/JSON — 제어 PC 쪽은 표준 라이브러리만으로 부른다).

  CUDA_HOME=~/cuda_shim CUDA_VISIBLE_DEVICES=1 ~/groot/Isaac-GR00T/.venv/bin/python fr5_policy_server.py \
      --ckpt ~/gr00t_runs/fr5_rack_v1/checkpoint-14000 [--port 8300] [--host 0.0.0.0]
  자체 확인(로봇 없이, 원본 판으로 전처리·자세 변환·복원까지):
      ... fr5_policy_server.py --ckpt ... --selftest ~/fr5cap/datasets/<원본> --episodes 0 50

요청  POST /act  {"third": <base64 PNG/JPEG 원본 크기>, "wrist": <base64>, "state8": [x,y,z,rx,ry,rz,g,-g], "instruction": str}
      state8 = fr5rec meta 프레임 state 와 같은 규약(작업 프레임 m, 축각, g = 그리퍼 pos/1000×0.04)
응답  {"ok": true, "chunk": [[x,y,z,rx,ry,rz,g] × H], "infer_ms": .., "pre_ms": ..}  — 절대 자세(작업 프레임 m, 축각), 10 Hz 간격
      GET /info → 체크포인트·H·fps·지시문·키
영상은 서버가 학습 변환과 똑같이 줄인다: PIL .convert("RGB").resize((256, 256), BILINEAR) (fr5_to_gr00t.py squash).
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
from PIL import Image

SIZE = 256


# ------------------------------------------------------------------ 회전 (fr5_to_gr00t.py 와 같은 규약)
def rotvec_to_R(rv) -> np.ndarray:
    rv = np.asarray(rv, np.float64).reshape(3)
    th = float(np.linalg.norm(rv))
    if th < 1e-12:
        return np.eye(3)
    k = rv / th
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * (K @ K)


def R_to_rotvec(R) -> np.ndarray:
    """회전행렬 → 축각(각 0~π, SciPy as_rotvec 과 같은 표현)."""
    R = np.asarray(R, np.float64)
    c = max(-1.0, min(1.0, (np.trace(R) - 1.0) / 2.0))
    th = float(np.arccos(c))
    if th < 1e-9:
        return np.zeros(3)
    if np.pi - th < 1e-6:                                # π 근처: 대칭 부분에서 축
        M = (R + np.eye(3)) / 2.0
        i = int(np.argmax(np.diag(M)))
        k = M[:, i] / np.sqrt(max(M[i, i], 1e-12))
        return k / np.linalg.norm(k) * th
    w = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2.0 * np.sin(th))
    return w * th


def rot6d_to_R(r6) -> np.ndarray:
    """회전행렬 첫 두 행(GR00T pose.py 규약) → R. 행을 정규화·직교화하고 셋째 행 = 교차곱."""
    r = np.asarray(r6, np.float64).reshape(2, 3)
    a = r[0] / max(np.linalg.norm(r[0]), 1e-12)
    b = r[1] - a * np.dot(a, r[1])
    b = b / max(np.linalg.norm(b), 1e-12)
    return np.stack([a, b, np.cross(a, b)])


def state8_to_obs(s8):
    s8 = np.asarray(s8, np.float64).reshape(8)
    eef = np.concatenate([s8[:3], rotvec_to_R(s8[3:6])[:2, :].reshape(6)])
    return eef.astype(np.float32), s8[6:8].astype(np.float32)


def eef9_to_7(eef, grip) -> list:
    out = []
    for e, g in zip(np.asarray(eef, np.float64), np.asarray(grip, np.float64)):
        out.append([float(v) for v in e[:3]] + [float(v) for v in R_to_rotvec(rot6d_to_R(e[3:9]))] + [float(np.ravel(g)[0])])
    return out


def to_input_image(raw: bytes | np.ndarray) -> np.ndarray:
    im = Image.open(io.BytesIO(raw)) if isinstance(raw, (bytes, bytearray)) else Image.fromarray(np.asarray(raw))
    return np.asarray(im.convert("RGB").resize((SIZE, SIZE), Image.BILINEAR), dtype=np.uint8)


# ------------------------------------------------------------------ 정책
class Policy:
    def __init__(self, ckpt: str, device: str = "cuda:0", policy=None):
        self.ckpt = str(ckpt)
        if policy is None:
            from gr00t.data.embodiment_tags import EmbodimentTag
            from gr00t.policy import Gr00tPolicy
            policy = Gr00tPolicy(model_path=self.ckpt, embodiment_tag=EmbodimentTag.NEW_EMBODIMENT, device=device, strict=True)
        self.p = policy
        mc = self.p.get_modality_config()
        self.vkeys = list(mc["video"].modality_keys)            # 학습 설정: agentview, wrist
        self.skeys = list(mc["state"].modality_keys)            # eef, gripper
        self.lkeys = list(mc["language"].modality_keys)         # annotation.human.task_description
        self.akeys = list(mc["action"].modality_keys)           # eef, gripper
        self.H = len(mc["action"].delta_indices)
        self.lock = threading.Lock()

    def act(self, third: np.ndarray, wrist: np.ndarray, state8, instruction: str) -> dict:
        t0 = time.perf_counter()
        imgs = {"agentview": third, "wrist": wrist}
        eef, grip = state8_to_obs(state8)
        st = {"eef": eef, "gripper": grip}
        obs = {"video": {k: imgs[k][None, None] for k in self.vkeys},
               "state": {k: st[k][None, None] for k in self.skeys},
               "language": {k: [[instruction]] for k in self.lkeys}}
        t1 = time.perf_counter()
        with self.lock:
            action, _info = self.p.get_action(obs)
        t2 = time.perf_counter()
        a_eef = np.asarray(action["eef"])[0]                    # (H, 9)
        a_g = np.asarray(action["gripper"])[0]                  # (H, 1)
        return {"ok": True, "chunk": eef9_to_7(a_eef, a_g), "pre_ms": round((t1 - t0) * 1e3, 1),
                "infer_ms": round((t2 - t1) * 1e3, 1), "H": int(a_eef.shape[0])}


# ------------------------------------------------------------------ HTTP
def make_handler(pol: Policy, info: dict):
    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt, *a):                         # 요청마다 줄을 찍지 않는다(너무 많다)
            pass

        def _send(self, code, obj):
            b = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path.split("?")[0] == "/info":
                return self._send(200, info)
            self._send(404, {"ok": False, "error": "GET /info 만"})

        def do_POST(self):
            if self.path.split("?")[0] != "/act":
                return self._send(404, {"ok": False, "error": "POST /act 만"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                d = json.loads(self.rfile.read(n))
                if "third" in d:                                # 제어 PC 스크립트: PNG/JPEG 원본 크기 + state8
                    third = to_input_image(base64.b64decode(d["third"]))
                    wrist = to_input_image(base64.b64decode(d["wrist"]))
                    s8 = [float(v) for v in d["state8"]]
                else:                                           # fr5lens GR00T 탭: 256×256×3 uint8 원시 바이트 + state 8(같은 규약)
                    third, wrist = (np.frombuffer(base64.b64decode(d[k]), np.uint8).reshape(SIZE, SIZE, 3).copy() for k in ("image", "wrist"))
                    s8 = [float(v) for v in d["state"]]
                if len(s8) != 8 or not all(np.isfinite(s8)):
                    raise ValueError(f"state8 은 유한한 수 8개(지금 {len(s8)}개)")
                r = pol.act(third, wrist, s8, str(d.get("instruction") or info["instruction"]))
                self._send(200, r)
            except Exception as e:                              # noqa: BLE001 — 호출 쪽이 이유를 보고 멈춘다
                self._send(400, {"ok": False, "error": f"{type(e).__name__}: {e}"})
    return H


# ------------------------------------------------------------------ 자체 확인
def selftest(pol: Policy, src: Path, episodes, instruction: str, stride: int = 20):
    """원본 판(meta.json + rgb/ + wrist/)의 프레임을 서버와 같은 전처리로 넣고, 예측 첫 행동 vs 다음 프레임 state 를 잰다.
    학습 때 본 판이므로 '맞는지'가 아니라 '전처리·자세 변환·복원이 맞물리는지'를 본다(절대 자세로 나오면 오차가 mm 단위)."""
    for ep in episodes:
        d = src / f"ep_{ep:03d}"
        m = json.loads((d / "meta.json").read_text())
        S = np.asarray([f["state"] for f in m["frames"]], np.float64)
        errs, rerr, gerr, tms = [], [], [], []
        for i in range(0, len(S) - 2, stride):
            third = to_input_image((d / "rgb" / f"{i:05d}.png").read_bytes())
            wrist = to_input_image((d / "wrist" / f"{i:05d}.png").read_bytes())
            r = pol.act(third, wrist, S[i], instruction)
            a0 = np.asarray(r["chunk"][0])
            errs.append(float(np.linalg.norm(a0[:3] - S[i + 1, :3])) * 1000)
            Rd = rotvec_to_R(a0[3:6]).T @ rotvec_to_R(S[i + 1, 3:6])
            rerr.append(float(np.degrees(np.linalg.norm(R_to_rotvec(Rd)))))
            gerr.append(abs(float(a0[6]) - float(S[i + 1, 6])) * 1000)
            tms.append(r["infer_ms"])
        print(f"ep_{ep:03d}: 표본 {len(errs)} · 첫 행동 위치 오차 중앙 {np.median(errs):.1f} mm(최대 {max(errs):.1f}) · "
              f"회전 {np.median(rerr):.2f}°(최대 {max(rerr):.2f}) · 그리퍼 {np.median(gerr):.2f} mm · 추론 {np.median(tms):.0f} ms", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8300)
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--instruction", default="put the red tube in the red slot")
    ap.add_argument("--selftest", type=Path, default=None, help="원본 fr5rec 데이터셋 폴더 — 서버를 띄우지 않고 확인만")
    ap.add_argument("--episodes", type=int, nargs="*", default=[0, 50, 99])
    a = ap.parse_args()
    t0 = time.time()
    pol = Policy(a.ckpt, a.device)
    print(f"정책 로드 {time.time() - t0:.0f} s · {a.ckpt} · 영상 {pol.vkeys} · 상태 {pol.skeys} · 언어 {pol.lkeys} · 행동 {pol.akeys} × {pol.H}",
          flush=True)
    if a.selftest:
        selftest(pol, a.selftest.expanduser(), a.episodes, a.instruction)
        return
    info = {"ok": True, "ckpt": a.ckpt, "H": pol.H, "fps": 10.0, "size": SIZE, "instruction": a.instruction,
            "video": pol.vkeys, "state": pol.skeys, "language": pol.lkeys, "action": pol.akeys,
            "state8": "x y z(m, 작업 프레임) rx ry rz(축각) g -g", "chunk": "x y z rx ry rz g(절대, 10 Hz)"}
    srv = ThreadingHTTPServer((a.host, a.port), make_handler(pol, info))
    print(f"정책 서버 http://{a.host}:{a.port}  (POST /act · GET /info) — Ctrl+C 로 끝", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
