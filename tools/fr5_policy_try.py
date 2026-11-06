#!/usr/bin/env python3
"""GR00T 정책 시험 실행 — 제어 PC(Thor). 독립 스크립트: 설치된 fr5auto(v1.0.0)의 실행기·기구학·송신을 빌려 쓴다.

  conv  <판 폴더>   로봇 안 움직임 · 기록된 판에서 tcp_base_mm_deg·grip_raw → state8 을 다시 계산해 meta state 와 비교
  check             로봇 안 움직임 · 제어판·카메라·정책 서버를 두 번 돌리고 첫 묶음을 IK·안전 검사까지만
  run               정책으로 한 판(시작 전 'y' 확인). Ctrl+C = 송신을 끊어 그 자리 멈춤
  home              멈춘 뒤 초기 자세로(쥔 채면 튜브 받기 → 그리퍼 열기)
v6.4: 학습 200판(fr5_autocollect10hz_20261103)·체크포인트 fr5_rack_v2 에 맞춤 — 학습 범위를 200판으로, 벤치마크 이름 기본 rack_v2_20000,
    시작 장면마다 '학습 판 이웃'(빨강·링이 모두 50·80 mm 안인 학습 판 수)을 보이고 시행 기록에 남긴다(--train-data).
v6.3: ringaudit(학습 데이터의 링 칸 인식과 실제로 꽂은 칸이 맞는지 판마다 점검 — 로봇 안 움직임).
v6.2: mark(기록 고치기 — 지우지 않고 사람 판정·메모를 바꾸고 내력을 남김).
v6.1: 시행 번호·배치-회차는 같은 조건 안에서만 센다(conds.json · 보고서에 조건 값).
v6.0: 벤치마크(GR00T 실물 평가 기준 — 배치 10개 × 3회) — run --layout N: 시작·끝 장면을 fr5auto 3인칭 인식으로 보고(판정에만),
    10 Hz 실측으로 단계(잡기·들기·칸 위로·꽂기·놓기·끝 장면) 자동 판정 → 사람 확인(Enter) → bench/<이름>/results.csv.
    look --layout N(배치 사진·인식 저장) · report(성공률 Wilson 95%·배치별·단계별·유형). 벤치마크 기본: 최대 120 s · 놓은 뒤 2.5 s.
v5.4: 관절 순간 0 읽기는 다시 읽는다(판이 끝나던 것) · snap(정책이 보는 영상 vs 학습 영상) · datarot 에 자주 나온 잡는·놓는 자리.
v5.3: J6 가 ±창을 조금(--j6-clamp 10°까지) 넘으면 버리지 않고 창 끝에 묶는다 — J6 는 공구 축 둘레만 돌려 튜브 위치는 그대로
    · --lift-guard(선택): 쥔 뒤 60 mm 까지 곧게 들기 · datarot 고침(빈 범위) + J6 학습 범위.
v5.2: 안전 검사에 걸린 묶음은 버리고 다시 묻는다(연속 --max-reject 번이면 끝) · 닫은·연 자리 출력 · datarot 에 학습 데이터 잡는·놓는 자리
    · splice 에 쥔 뒤 들 때 옆으로 끌린 거리.
v5.1: IK 를 행동 사이 4칸으로 나눠 푼다(정상 손목 회전이 '갈래 바뀜'으로 걸리던 것) · 한 스텝 이동 한계 30 mm(학습 최대 25.8)
    · 안전 검사로 서면 Enter 전까지 그 자리에서 기다린다.
v5: 보내기를 따로 도는 스레드(Streamer)로 — 다음 묶음이 늦어도 지금 묶음의 남은 행동(꼬리)을 계속 보내 서지 않는다.
    새 묶음은 '지금 + 계획 시간' 시각부터 시간에 맞춰 끼우고(섞기 포함), 제어판보다 빠르지 않게 속도를 묶는다.
    따라오기 감시는 기다리지 않고 벗어남만 본다. 묶음마다 멈춤(ms)·계획 시간·스텝 회전을 남긴다.
v4: 묶음 이음 섞기 — 새 묶음 앞 몇 스텝을 이전 묶음이 같은 스텝에 대해 낸 행동에서 서서히 넘긴다(앞뒤 흔들림·J6 이탈).
    splice <묶음 기록> 으로 이음마다 점프·뒤로 간 거리를 본다.
v3: 그리퍼 문턱을 '닫기 시작'에 맞춤 — 학습 행동 g 는 다음 프레임의 측정값이라 닫을 때 0.040 → 0.012 로 서서히 준다.
    중간값(0.022)을 기다리면 실제 그리퍼가 안 닫혀 상태가 '열림'으로 남고, 정책은 잡는 자리에서 헤맨다(실물 2026-11-02 14000).
v2: 묶음 사이에 서지 않는다 — 지금 묶음이 끝나기 왕복 시간 전에 다음 묶음을 미리 묻고, 응답이 오면 지난 시간만큼의 행동을
    건너뛰어 이어 붙인다. 영상은 제어 PC 에서 256×256 으로 줄여 보낸다(학습과 같은 PIL BILINEAR). 빈손으로 닫으면 판을 끝낸다.

공통: --url http://<학습서버>:8300   보정: --dx --dy (베이스 mm) --dzg(잡기 전 z) --dzr(쥔 뒤 z) --speed(1.0 = 10 Hz)
판마다 기록: ~/fr5cap/fr5auto/work/policy_try.jsonl (판 요약) · policy_try_<시각>.jsonl (묶음마다)
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import sys
import threading
import time
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.expanduser("~/fr5cap/fr5auto"))
from fr5auto import config as CF  # noqa: E402
from fr5auto import geom as G  # noqa: E402
from fr5auto import kin as K  # noqa: E402
from fr5auto.run import Abort, Http, Runner, Stuck, leader_send_running  # noqa: E402

YAW = math.radians(77.2)                       # fr5rec meta.task_yaw_deg — 작업 프레임 = Rz(−77.2°)·베이스


def Rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


RZ_W, RZ_B = Rz(-YAW), Rz(YAW)                  # 베이스 → 작업, 작업 → 베이스


def rotvec_to_R(rv):
    rv = np.asarray(rv, float).reshape(3)
    th = float(np.linalg.norm(rv))
    if th < 1e-12:
        return np.eye(3)
    k = rv / th
    Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(th) * Kx + (1 - math.cos(th)) * (Kx @ Kx)


def R_to_rotvec(R):
    R = np.asarray(R, float)
    th = math.acos(max(-1.0, min(1.0, (np.trace(R) - 1.0) / 2.0)))
    if th < 1e-9:
        return np.zeros(3)
    if math.pi - th < 1e-6:
        M = (R + np.eye(3)) / 2.0
        i = int(np.argmax(np.diag(M)))
        k = M[:, i] / math.sqrt(max(M[i, i], 1e-12))
        return k / np.linalg.norm(k) * th
    w = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2.0 * math.sin(th))
    return w * th


def rot_deg(Ra, Rb):
    return math.degrees(float(np.linalg.norm(R_to_rotvec(np.asarray(Ra).T @ np.asarray(Rb)))))


def state8(tcp, gpos):
    """제어판 tcp(베이스 mm·deg, 고정축 XYZ)·그리퍼 pos → fr5rec meta state 규약."""
    p = RZ_W @ (np.asarray(tcp[:3], float) / 1000.0)
    R = RZ_W @ G.rot_xyz(*[float(v) for v in tcp[3:6]])
    g = float(gpos) / 1000.0 * 0.04
    return [float(v) for v in p] + [float(v) for v in R_to_rotvec(R)] + [g, -g]


def to_base(a7, dx=0.0, dy=0.0, dz=0.0):
    """정책 행동(작업 프레임 m·축각) → 베이스 목표(mm, 3×3) + 보정(베이스 mm)."""
    p = RZ_B @ np.asarray(a7[:3], float) * 1000.0 + np.array([dx, dy, dz])
    return p, RZ_B @ rotvec_to_R(a7[3:6])


def tilt_deg(R):
    """공구 z 축이 수직 아래와 이루는 각."""
    return math.degrees(math.acos(max(-1.0, min(1.0, float(-np.asarray(R)[2, 2])))))


def blend_rows(new, old, nmax):
    """새 묶음 앞 행동(n×7, 작업 프레임)을 이전 묶음의 이어지는 행동(같은 스텝)에서 서서히 넘긴다 — 이음에서 앞뒤로 튀지 않게.
    w = (j+1)/(nb+1): 첫 스텝은 거의 이전 계획, nb 스텝 뒤부터 새 묶음 그대로. 위치는 선형, 회전은 측지선(slerp). 그리퍼는 새 묶음."""
    out = np.array(new, float)
    nb = min(len(old), len(out), int(nmax))
    for j in range(nb):
        w = (j + 1) / (nb + 1)
        out[j, :3] = (1 - w) * old[j, :3] + w * out[j, :3]
        Ro = rotvec_to_R(old[j, 3:6])
        out[j, 3:6] = R_to_rotvec(Ro @ rotvec_to_R(w * R_to_rotvec(Ro.T @ rotvec_to_R(out[j, 3:6]))))
    return out, nb


# ------------------------------------------------------------------ conv
def cmd_conv(ep: Path):
    m = json.loads((ep / "meta.json").read_text())
    dp, dr, dg = [], [], []
    for f in m["frames"]:
        s8 = state8(f["tcp_base_mm_deg"], f["grip_raw"])
        st = f["state"]
        dp.append(float(np.linalg.norm(np.asarray(s8[:3]) - np.asarray(st[:3]))) * 1000)
        dr.append(rot_deg(rotvec_to_R(s8[3:6]), rotvec_to_R(st[3:6])))
        dg.append(abs(s8[6] - st[6]) * 1000)
    print(f"{ep.name}: 프레임 {len(dp)} · 위치 차 최대 {max(dp):.4f} mm · 회전 차 최대 {max(dr):.5f}° · 그리퍼 차 최대 {max(dg):.4f} mm")
    print("→ 0 에 가까우면(위치 0.01 mm·회전 0.01° 아래) 이 스크립트의 state8 이 학습 데이터와 같은 규약이다")


# ------------------------------------------------------------------ 공통
def grab(r, cam, fresh_ms=150):
    age = 1e9
    for _ in range(6):
        code, hdr, body = r.rec.fetch(f"/api/frame/{cam}.png", timeout=3.0)
        if code != 200:
            raise Abort(f"fr5rec {cam} 프레임을 못 받았다(HTTP {code}) — fr5rec 세션을 열어 카메라를 켠다")
        age = float(hdr.get("x-frame-age-ms") or 1e9)
        if age <= fresh_ms:
            return body, age
        time.sleep(0.03)
    raise Abort(f"{cam} 프레임이 {age:.0f} ms 묵었다")


def small_png(raw: bytes) -> bytes:
    """fr5rec PNG → RGB 256×256(PIL BILINEAR, 학습 변환·서버와 같음) PNG. 서버 쪽 줄이기는 같은 크기라 그대로 지나간다."""
    with Image.open(BytesIO(raw)) as im:
        out = BytesIO()
        im.convert("RGB").resize((256, 256), Image.BILINEAR).save(out, "PNG")
        return out.getvalue()


class Ask:
    """따로 도는 스레드에서 관측(제어판 상태 + 두 카메라)을 잡아 정책에 묻는다. t_obs = 상태를 읽은 순간."""

    def __init__(self, r, pol, instr, timeout):
        self.r, self.pol, self.instr, self.timeout = r, pol, instr, timeout
        self.res, self.err = None, None
        self.th = threading.Thread(target=self._run, daemon=True)
        self.th.start()

    def _run(self):
        try:
            for _k in range(4):                                          # 제어판이 가끔 관절을 순간 0 으로 읽는다(fr5auto kin 주석) — 다시 읽는다
                s = self.r.st()
                if s.get("fault"):
                    raise Abort(f"제어기 오류: {s.get('fault')}")
                if self.r._joints_ok(s.get("joints")):
                    break
                time.sleep(0.04)
            else:
                raise Abort("제어판 관절 값이 네 번 연속 이상하다")
            t_obs = time.monotonic()
            tcp = [float(v) for v in s["tcp"][:6]]
            s8 = state8(tcp, float((s.get("gripper") or {}).get("pos", 0.0)))
            third = small_png(grab(self.r, "third")[0])
            wrist = small_png(grab(self.r, "wrist")[0])
            chunk, rtt, inf = ask_policy(self.pol, third, wrist, s8, self.instr, self.timeout)
            self.res = (chunk, t_obs, s8, (time.monotonic() - t_obs) * 1000, inf)
        except BaseException as e:                                       # noqa: BLE001 — 부르는 쪽에서 다시 던진다
            self.err = e

    def get(self, st=None):
        t_end = time.monotonic() + self.timeout + 8.0
        while self.th.is_alive() and time.monotonic() < t_end:
            if st is not None and st.err is not None:
                raise st.err
            self.th.join(0.02)
        if self.err is not None:
            raise self.err
        if self.res is None:
            raise Abort("정책 응답이 오지 않았다")
        return self.res


def stream(r, T, Q, grip, on_tick=None):
    """관절 경로를 시간 맞춰 보낸다(제어판 속도 상한으로 늘림·따라오기 감시). 끝에서 서지 않는다(settle 없음)."""
    t2, _ = K.retime(T, Q, r.vmax_eff(), r.rc["vmax_frac"])
    hz = r.rc["send_hz"]
    grid = np.arange(0.0, t2[-1] + 1e-9, 1.0 / hz)
    Qr, = K.resample(t2, grid, Q)
    nxt = time.monotonic()
    n = len(Qr)
    for i, q in enumerate(Qr):
        if r.stop_req:
            raise Stuck(str(r.stop_req))
        r.sender.set(q, grip)
        if on_tick is not None:
            on_tick((n - 1 - i) / hz)
        if i % 20 == 0:
            nxt += r._pace(Qr, i)
        nxt += 1.0 / hz
        time.sleep(max(0.0, nxt - time.monotonic()))
    return np.asarray(Qr[-1], float)


class Streamer:
    """따로 도는 스레드가 send_hz 로 관절 시간표 (tq, Q) 를 지금 시각에서 보간해 보낸다 — 묶음이 바뀌어도 서지 않는다.
    새 묶음은 replace(t_s, tq, Q): t_s 까지는 지금 시간표, 그 뒤는 새 시간표. 시간표가 끝나면 마지막 자세에 선다.
    보내는 목표의 관절 속도는 제어판이 낼 속도(vmax_eff) × vmax_frac 로 묶는다(제어판보다 빨리 보내 뒤처지지 않게).
    팔이 최근 3 s 동안 보낸 목표 어디에서도 track_deg 넘게 벗어나면 Stuck(막힘·다른 길)."""

    def __init__(self, r, q0, grip):
        self.r, self.hz = r, float(r.rc["send_hz"])
        self.vlim = float(r.vmax_eff()) * float(r.rc["vmax_frac"])
        self.track = float(r.rc.get("track_deg", 4.0))
        self.lock = threading.Lock()
        self.tq, self.Q = np.array([time.monotonic()]), np.asarray(q0, float)[None].copy()
        self.q_sent = np.asarray(q0, float).copy()
        self.grip = float(grip)
        self.hist = []
        self.err = None
        self.dev_max = 0.0
        self.trace = []                                                 # 10 Hz 실측(시각, 관절, 그리퍼 pos) — 벤치마크 단계 판정
        self._stop = threading.Event()
        self.th = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.th.start()
        return self

    def halt(self):
        self._stop.set()
        self.th.join(2.0)

    def _interp(self, t):
        tq, Q = self.tq, self.Q
        if t <= tq[0]:
            return Q[0].copy()
        if t >= tq[-1]:
            return Q[-1].copy()
        i = int(np.searchsorted(tq, t)) - 1
        u = (t - tq[i]) / max(1e-9, tq[i + 1] - tq[i])
        return Q[i] + u * (Q[i + 1] - Q[i])

    def at(self, t):
        with self.lock:
            return self._interp(t)

    def end(self):
        with self.lock:
            return float(self.tq[-1]), self.Q[-1].copy()

    def replace(self, t_s, tq, Q):
        with self.lock:
            q_s = self._interp(t_s)
            keep = self.tq < t_s
            self.tq = np.r_[self.tq[keep], t_s, np.asarray(tq, float)]
            self.Q = np.vstack([self.Q[keep], q_s[None], np.asarray(Q, float)])

    def _run(self):
        try:
            dt = 1.0 / self.hz
            nxt = time.monotonic()
            i = 0
            while not self._stop.is_set():
                if self.r.stop_req:
                    raise Stuck(str(self.r.stop_req))
                d = self.at(time.monotonic()) - self.q_sent
                mx, lim = float(np.abs(d).max()), self.vlim * dt
                if mx > lim:
                    d = d * (lim / mx)
                self.q_sent = self.q_sent + d
                self.r.sender.set(self.q_sent, self.grip)
                self.hist.append(self.q_sent.copy())
                if len(self.hist) > int(3 * self.hz):
                    del self.hist[0]
                if i % 5 == 0:
                    s, _age = self.r._guard_c()
                    j = np.asarray(s["joints"][:6], float)
                    gp = (s.get("gripper") or {}).get("pos")
                    self.trace.append((round(time.monotonic(), 3), [round(float(v), 3) for v in j], float(gp) if gp is not None else float("nan")))
                    D = np.abs(np.asarray(self.hist) - j[None, :])
                    k = int(D.max(axis=1).argmin())
                    dev = float(D[k].max())
                    self.dev_max = max(self.dev_max, dev)
                    if dev > self.track:
                        raise Stuck(f"팔이 보낸 목표를 따라오지 않는다(최근 3 s 목표에서 J{int(D[k].argmax()) + 1} {dev:.1f}° 벗어남)")
                i += 1
                nxt += dt
                time.sleep(max(0.0, nxt - time.monotonic()))
        except BaseException as e:                                       # noqa: BLE001 — 실행 루프가 다시 던진다
            self.err = e


def wait_until(t, st):
    while True:
        if st.err is not None:
            raise st.err
        dt = t - time.monotonic()
        if dt <= 0:
            return
        time.sleep(min(0.02, dt))


def pose_at(tk, rows, t):
    """시각 tk 의 행동들(작업 프레임 7)을 시각 t 에서 보간. 범위 밖이면 None."""
    if len(tk) == 0 or t < tk[0] - 1e-6 or t > tk[-1] + 1e-6:
        return None
    if len(tk) == 1:
        return np.array(rows[0], float)
    i = int(np.clip(np.searchsorted(tk, t) - 1, 0, len(tk) - 2))
    u = float(np.clip((t - tk[i]) / max(1e-9, tk[i + 1] - tk[i]), 0.0, 1.0))
    a, b = np.asarray(rows[i], float), np.asarray(rows[i + 1], float)
    out = a.copy()
    out[:3] = a[:3] + u * (b[:3] - a[:3])
    Ra = rotvec_to_R(a[3:6])
    out[3:6] = R_to_rotvec(Ra @ rotvec_to_R(u * R_to_rotvec(Ra.T @ rotvec_to_R(b[3:6]))))
    return out


def rot_steps(rows):
    """행동 사이 회전(°) — 학습 한 스텝(0.1 s) 단위."""
    return [rot_deg(rotvec_to_R(rows[i][3:6]), rotvec_to_R(rows[i + 1][3:6])) for i in range(len(rows) - 1)]


def R_to_rotvec_row(R_base, p_base_mm):
    """베이스 자세(FK) → 작업 프레임 행동 행(m·축각, 그리퍼 0) — 회전 스텝 비교용."""
    return np.r_[RZ_W @ (np.asarray(p_base_mm, float) / 1000.0), R_to_rotvec(RZ_W @ np.asarray(R_base)), 0.0]


def ask_policy(pol, third, wrist, s8, instr, timeout):
    t0 = time.monotonic()
    d = pol.post("/act", {"third": base64.b64encode(third).decode(), "wrist": base64.b64encode(wrist).decode(),
                          "state8": s8, "instruction": instr}, timeout=timeout)
    if not d.get("ok"):
        raise Abort(f"정책 서버 오류: {d.get('error')}")
    return np.asarray(d["chunk"], float), (time.monotonic() - t0) * 1000, float(d.get("infer_ms") or 0)


def plan_steps(chunk, n, q_now, p_now, R_now, home, a, closed, floor_z, limits):
    """묶음 앞 n 개 → 베이스 목표·관절. 안전 검사에 걸리면 (None, 이유들)."""
    dz = a.dzr if closed else a.dzg
    P, Rs = zip(*[to_base(chunk[j], a.dx, a.dy, dz) for j in range(n)])
    P, Rs = np.asarray(P), list(Rs)
    why = []
    if P[:, 2].min() < floor_z:
        why.append(f"목표 z {P[:, 2].min():.0f} mm < 바닥 한계 {floor_z:.0f} mm")
    seq = np.vstack([p_now, P])
    st = np.linalg.norm(np.diff(seq, axis=0), axis=1)
    if st.max() > a.max_step_mm:
        why.append(f"한 스텝(0.1 s) 이동 {st.max():.0f} mm > {a.max_step_mm:g} mm")
    Rq = [R_now] + Rs
    rs = max(rot_deg(Rq[i], Rq[i + 1]) for i in range(len(Rq) - 1))
    if rs > a.max_rot_step:
        why.append(f"한 스텝 회전 {rs:.1f}° > {a.max_rot_step:g}°")
    tl = max(tilt_deg(R) for R in Rs)
    if tl > a.max_tilt:
        why.append(f"공구 기울기 {tl:.0f}° > {a.max_tilt:g}°")
    rad = np.linalg.norm(P[:, :2], axis=1)
    if rad.max() > a.max_radius or rad.min() < a.min_radius:
        why.append(f"베이스에서 수평 거리 {rad.min():.0f}~{rad.max():.0f} mm(허용 {a.min_radius:g}~{a.max_radius:g})")
    if why:
        return None, why, P
    # 행동 사이(0.1 s 학습 스텝, 최대 약 26 mm·6°)를 SUB 칸으로 잘게 나눠 푼다 — solve_path 의 '이웃한 점 5° 튐 = 갈래 바뀜' 검사는
    # 촘촘한 경로용이라 학습 스텝 간격 그대로 넣으면 정상 손목 회전(5~6°/스텝)도 갈래 바뀜으로 잘못 걸린다(실물 2026-11-02 15:08).
    SUB = 4
    Pd, qd = [], []
    pa, Ra = np.asarray(p_now, float), np.asarray(R_now, float)
    for pb, Rb in zip(P, Rs):
        rv = R_to_rotvec(Ra.T @ Rb)
        for k in range(1, SUB + 1):
            u = k / SUB
            Pd.append(pa + u * (pb - pa))
            qd.append(G.quat_from_rot(Ra @ rotvec_to_R(u * rv)))
        pa, Ra = pb, Rb
    Qd, errs, probs = K.solve_path(np.asarray(Pd), qd, q_now, 1.0, stride=1)
    Q = Qd[SUB - 1::SUB]
    probs += K.limits_problems(Q, limits)
    notes = []
    lo6, hi6 = home[5] - a.j6_window, home[5] + a.j6_window
    over = float(max(0.0, Q[:, 5].max() - hi6, lo6 - Q[:, 5].min()))
    if over > 0:
        if over <= a.j6_clamp:                                          # J6 는 공구 z(= 쥔 튜브 축) 둘레로만 돈다 — TCP 위치·공구 z 축 그대로
            Q = Q.copy()                                                # (FK 확인: J6 +5° → 위치 0.0 mm · 공구 z 0.000°)
            Q[:, 5] = np.clip(Q[:, 5], lo6, hi6)
            notes.append(f"J6 {over:.1f}° 묶음(±{a.j6_window:g}°)")
        else:
            probs.append(f"J6 가 초기 자세에서 {a.j6_window + over:.0f}° 돈다(허용 {a.j6_window:g}°, 묶기 {a.j6_clamp:g}° 까지)")
    jmp = float(np.abs(np.diff(np.vstack([q_now, Q]), axis=0)).max())
    if jmp > 15.0:
        probs.append(f"관절이 한 스텝에 {jmp:.0f}° 튄다(자세 갈래 바뀜?)")
    if probs:
        return None, probs, P
    return Q, notes, P


def setup(a, need_sender, need_policy=True):
    cfg = CF.load(a.config)
    wd = CF.work_dir(cfg)
    r = Runner(cfg, {}, [], wd, say=print)
    r.task = "rack"
    s = r.st()
    if s.get("fault"):
        raise Abort(f"제어기 오류: {s.get('fault')}")
    L = r.ld()
    if abs(float(L.get("scale", 1.0)) - 1.0) > 1e-6:
        raise Abort(f"리더 배율 {L.get('scale')} — 1.0 이어야 한다")
    lp = leader_send_running()
    if lp:
        raise Abort("제어판으로 보내는 다른 프로그램이 떠 있다 — 끈다: " + "; ".join(lp))
    j = np.asarray(s["joints"][:6], float)
    Rf, pf = K.fk(j)                                                    # fr5auto 기구학 TCP == 제어판 TCP 인지
    tcp = s["tcp"]
    dp, dr = float(np.linalg.norm(pf - np.asarray(tcp[:3], float))), rot_deg(Rf, G.rot_xyz(*tcp[3:6]))
    print(f"기구학 확인: FK 와 제어판 tcp 차 {dp:.2f} mm · {dr:.3f}°")
    if dp > 3.0 or dr > 1.0:
        raise Abort("fr5auto 기구학 TCP 와 제어판 TCP 가 다르다 — 제어판 공구 설정 확인")
    pol, info = None, {}
    if need_policy:
        pol = Http(a.url, timeout=a.timeout)
        info = pol.get("/info", timeout=5.0)
        print(f"정책 서버: {info.get('ckpt')} · H {info.get('H')} · '{info.get('instruction')}'")
    if need_sender:
        r.start()
    return r, pol, info, cfg


def snapshot(r):
    s = r._guard() if r.sender else r.st()
    j = np.asarray(s["joints"][:6], float)
    tcp = [float(v) for v in s["tcp"][:6]]
    gpos = float((s.get("gripper") or {}).get("pos", 0.0))
    return j, tcp, gpos


# ------------------------------------------------------------------ check
def cmd_check(a):
    r, pol, info, cfg = setup(a, need_sender=False)
    for k in range(2):                                                  # 처음 한 번은 서버가 데워지느라 느릴 수 있다
        j, tcp, gpos = snapshot(r)
        s8 = state8(tcp, gpos)
        third, a1 = grab(r, "third")
        wrist, a2 = grab(r, "wrist")
        t0 = time.monotonic()
        th_s, wr_s = small_png(third), small_png(wrist)
        t_pre = (time.monotonic() - t0) * 1000
        chunk, rtt, inf = ask_policy(pol, th_s, wr_s, s8, info.get("instruction"), a.timeout)
        print(f"[{k + 1}] 프레임 나이 3인칭 {a1:.0f} · 손목 {a2:.0f} ms · 줄이기 {t_pre:.0f} ms · 왕복 {rtt:.0f} ms(추론 {inf:.0f}) · "
              f"보낸 크기 {(len(th_s) + len(wr_s)) / 1024:.0f} KB · 상태 g {s8[6] * 1000:.1f} mm")
    p_now, R_now = np.asarray(tcp[:3]), G.rot_xyz(*tcp[3:6])
    for i, c in enumerate(chunk):
        p, R = to_base(c)
        d = p - p_now
        print(f"  {i:2d}  Δ베이스 x {d[0]:+7.1f} y {d[1]:+7.1f} z {d[2]:+7.1f} mm · 회전 {rot_deg(R_now, R):5.2f}° · g {c[6] * 1000:5.1f} mm")
    L = r.ld()
    home = r.home()
    Q, why, _ = plan_steps(chunk, min(a.exec_steps, len(chunk)), j, p_now, R_now, home, a, gpos < 500,
                           float(L.get("z_min") or 45.0) + a.floor_margin, r.rc["joint_limits"])
    print("안전 검사·IK: " + ("통과 — 앞 %d 스텝 관절 변화 최대 %.2f°" % (len(Q), float(np.abs(Q - j).max())) if Q is not None
                          else "걸림 — " + "; ".join(why)))
    print(f"초기 자세와 관절 차 최대 {float(np.abs(j - np.asarray(home)).max()):.2f}°(run 은 1.5° 안이어야 시작)")


# ------------------------------------------------------------------ splice
def cmd_splice(path: Path):
    """묶음 기록에서 이음마다: 이전 묶음의 마지막 명령 → 새 묶음의 첫 명령 점프. 진행 방향 성분이 − 면 뒤로 갔다(앞뒤 흔들림)."""
    D = [json.loads(l) for l in open(path)]
    print("묶음 · 직전 한 스텝 mm · 이음 점프 mm(진행 방향 성분, − = 뒤로) · 회전 점프° · 섞음")
    prev, back = None, []
    if D and "stall_ms" in D[0]:                                        # v5 기록: 시간 맞춰 끼우므로 멈춤·회전을 본다
        print("묶음 · 건너뜀 · 섞음 · 계획 ms · 멈춤 ms(시간표가 끝나 서 있던 시간) · 최대 스텝 회전° · 따라오기 최대 벗어남°")
        for d in D:
            rs = d.get("rot_steps") or [0.0]
            print(f"  {d['q']:3d} · {d['skip']} · {d['blend']} · {d['plan_ms']:4d} · {d['stall_ms']:4d} · {max(rs):5.2f} · {d['dev_max']:.2f}"
                  + (f" · 그리퍼 스텝 {d['grip_change']}" if d.get("grip_change") is not None else "") + (" · 걸림: " + "; ".join(d["why"]) if d.get("why") else ""))
        for n, d in enumerate(D):                                       # 쥔 뒤 들어 올리는 동안(60 mm 까지) 옆으로 끌림
            if d.get("grip_change") is None or d["s8"][6] < 0.03:            # 열린 채 관측한 묶음의 그리퍼 바뀜 = 닫기
                continue
            g0 = np.asarray(d["exec"][-1][:3]) * 1000
            pts = []
            for e in D[n + 1:]:
                ne = e["exec_end"] - e["idx"][0] + 1
                pts += [np.asarray(x[:3]) * 1000 for x in e["exec"][:ne]]
                if e.get("grip_change") is not None:
                    break
            lift = [(p[2] - g0[2], float(np.linalg.norm(p[:2] - g0[:2]))) for p in pts]
            inside = [h for z, h in lift if z < 60.0]
            if inside:
                print(f"쥔 뒤 60 mm 들 때까지 옆으로 최대 {max(inside):.1f} mm 끌림({len(inside)} 스텝, 학습 수집기는 곧게 듦)")
        sm = [d["stall_ms"] for d in D if not d.get("from_rest")]
        if sm:
            print(f"이음 {len(sm)} · 선 이음 {sum(1 for v in sm if v > 0)} · 멈춤 합 {sum(sm)} ms · 최대 {max(sm)} ms")
        return
    for d in D:
        C = np.asarray(d["chunk"], float)
        i0, i1 = d["idx"]
        E = np.asarray(d.get("exec") or C[i0:i1 + 1].tolist(), float)
        if prev is not None:
            pl, pp = prev[-1], prev[-2] if len(prev) > 1 else prev[-1]
            jump = (E[0, :3] - pl[:3]) * 1000
            v = (pl[:3] - pp[:3]) * 1000
            nv = float(np.linalg.norm(v))
            along = float(jump @ v / nv) if nv > 1e-3 else 0.0
            back.append(along)
            print(f"  {d['q']:3d} · {nv:5.1f} · {np.linalg.norm(jump):5.1f} ({along:+5.1f}) · {rot_deg(rotvec_to_R(pl[3:6]), rotvec_to_R(E[0, 3:6])):5.2f} · {d.get('blend', 0)}")
        prev = None if d.get("grip_change") is not None else E
    if back:
        b = np.asarray(back)
        print(f"이음 {len(b)} · 뒤로 간 이음 {int((b < 0).sum())} · 진행 방향 성분 중앙 {np.median(b):+.1f} mm · 가장 뒤로 {b.min():+.1f} mm")


def cmd_snap(a):
    """정책이 보는 영상(제어 PC 에서 줄인 256×256)을 학습 판 첫 프레임(같은 방식으로 줄임)과 나란히 저장 — 색·화각·자르기 비교."""
    r, _, _, _ = setup(a, need_sender=False, need_policy=False)
    live, info = [], []
    for cam in ("third", "wrist"):
        raw, age = grab(r, cam)
        with Image.open(BytesIO(raw)) as im:
            info.append(f"실시간 {cam}: 원본 {im.size[0]}×{im.size[1]} {im.mode} · 나이 {age:.0f} ms")
        live.append(Image.open(BytesIO(small_png(raw))).convert("RGB"))
    train = []
    if a.ep:
        for sub in ("rgb", "wrist"):
            f = a.ep.expanduser() / sub / "00000.png"
            raw = f.read_bytes()
            with Image.open(BytesIO(raw)) as im:
                info.append(f"학습 {f.parent.parent.name}/{sub}: 원본 {im.size[0]}×{im.size[1]} {im.mode}")
            train.append(Image.open(BytesIO(small_png(raw))).convert("RGB"))
    rows = [live] + ([train] if train else [])
    out = Image.new("RGB", (512, 256 * len(rows)), (255, 255, 255))
    for i, row in enumerate(rows):
        for k, im in enumerate(row):
            out.paste(im, (256 * k, 256 * i))
    for t in info:
        print(t)
    for i, row in enumerate(rows):
        m = [np.asarray(im, float).reshape(-1, 3).mean(0).round(1).tolist() for im in row]
        print(("실시간" if i == 0 else "학습") + f" 평균 RGB 3인칭 {m[0]} · 손목 {m[1]}")
    f = r.work / f"snap_{time.strftime('%Y%m%d_%H%M%S')}.png"
    out.save(f)
    print(f"저장: {f}  (위 = 실시간, 아래 = 학습 첫 프레임 · 왼쪽 3인칭, 오른쪽 손목)")


def cmd_datarot(ds: Path):
    """학습 데이터(fr5rec 판 폴더들)의 한 스텝(0.1 s) 회전·이동 — 안전 검사 한계(--max-rot-step, --max-step-mm)와 비교."""
    eps = sorted(ds.glob("ep_*"))
    mr, mp, allr = [], [], []
    for ep in eps:
        S = np.asarray([f["state"] for f in json.loads((ep / "meta.json").read_text())["frames"]], float)
        r_ = rot_steps(S[:, :7])
        p_ = np.linalg.norm(np.diff(S[:, :3], axis=0), axis=1) * 1000
        mr.append(max(r_))
        mp.append(float(p_.max()))
        allr += r_
    G_, O_, D_ = [], [], []
    for ep in eps:                                                      # 닫기 시작(g < 0.034)·열기 시작(쥔 뒤 g > 0.020) 자리(베이스 mm)
        S = np.asarray([f["state"] for f in json.loads((ep / "meta.json").read_text())["frames"]], float)
        g = S[:, 6]
        ic = next((k for k in range(len(g)) if g[k] < 0.034), None)
        if ic is None:
            continue
        G_.append(RZ_B @ S[ic, :3] * 1000)
        io = next((k for k in range(ic + 1, len(g)) if g[k] > 0.020 and g[ic:k].min() < 0.020), None)
        if io is not None:
            O_.append(RZ_B @ S[io, :3] * 1000)
            D_.append((io - ic) / 10.0)
    for name, A in (("닫기 시작", G_), ("열기 시작", O_)):
        if A:
            A = np.asarray(A)
            print(f"{name} {len(A)} 판 · 베이스 x {np.median(A[:, 0]):.0f}({A[:, 0].min():.0f}~{A[:, 0].max():.0f}) · "
                  f"y {np.median(A[:, 1]):.0f}({A[:, 1].min():.0f}~{A[:, 1].max():.0f}) · z {np.median(A[:, 2]):.0f}({A[:, 2].min():.0f}~{A[:, 2].max():.0f}) mm")
    for name, A in (("잡는 자리", G_), ("놓는 자리", O_)):              # 자주 나온 자리(12 mm 안을 한 자리로) — 고정 배치를 학습에 많은 자리로
        cs = []
        for v in A:
            for c in cs:
                if np.linalg.norm(c["p"][:2] - v[:2]) < 12.0:
                    c["n"] += 1
                    c["s"] += v
                    c["p"] = c["s"] / c["n"]
                    break
            else:
                cs.append({"p": np.asarray(v, float), "s": np.asarray(v, float), "n": 1})
        cs.sort(key=lambda c: -c["n"])
        print(f"{name} 자주 나온 곳(판 수): " + " · ".join(f"x {c['p'][0]:.0f} y {c['p'][1]:.0f}({c['n']})" for c in cs[:8]) + f" · 전체 {len(cs)} 곳")
    J = []
    for ep in eps:                                                      # 기록된 관절(joints_deg)이 있으면 J6 가 판 첫 자세에서 얼마나 도는지
        fr = json.loads((ep / "meta.json").read_text())["frames"]
        q6 = [f["joints_deg"][5] for f in fr if isinstance(f.get("joints_deg"), list) and len(f["joints_deg"]) >= 6]
        if q6:
            J.append(max(abs(v - q6[0]) for v in q6))
    if J:
        print(f"J6 가 판 첫 자세에서 돈 최대: 중앙 {np.median(J):.0f}° · 90% {np.percentile(J, 90):.0f}° · 최대 {max(J):.0f}° ({len(J)} 판)")
    else:
        print("J6: 프레임에 joints_deg 가 없다 — 키: " + ", ".join(sorted(json.loads((eps[0] / 'meta.json').read_text())["frames"][0].keys())))
    if D_:
        print(f"닫기 → 열기 {np.median(D_):.1f} s(학습 속도 1.0 기준, {min(D_):.1f}~{max(D_):.1f})")
    i = int(np.argmax(mr))
    print(f"{len(eps)} 판 · 스텝 회전: 판별 최대의 중앙 {np.median(mr):.1f}° · 99.9% {np.percentile(allr, 99.9):.1f}° · 전체 최대 {max(mr):.1f}°({eps[i].name})")
    print(f"        스텝 이동: 판별 최대의 중앙 {np.median(mp):.1f} mm · 전체 최대 {max(mp):.1f} mm")


# ------------------------------------------------------------------ run
def grip_to(r, q, g_cmd, closing):
    r.settle(q)
    p0 = r._grip_pos(r._guard())
    r.sender.set(q, g_cmd)
    return r.grip_wait(closing=closing, want=g_cmd, p0=p0)


# ------------------------------------------------------------------ 벤치마크(GR00T 실물 평가 기준 — 배치 10개 × 3회)
VERSION = "v6.4"
BENCH_RANGE = {"grasp": ((-218, 272), (425, 646)), "release": ((-204, 279), (440, 652))}   # 학습 200판 잡은·링 자리(베이스 mm, fr5auto rack cover)
_TRAIN = {}


def train_xy(path):
    """학습 데이터셋 꼬리표의 (빨강 자리, 링 칸 자리) 목록 — 처음 한 번 읽어 둔다."""
    key = str(path)
    if key not in _TRAIN:
        out = []
        for m in sorted(Path(path).expanduser().glob("ep_*/meta.json")):
            try:
                t = (json.loads(m.read_text(encoding="utf-8")).get("fr5rec") or {}).get("tag") or {}
            except Exception:                                            # noqa: BLE001
                continue
            if t.get("red_xy") and t.get("slot_xy"):
                out.append((tuple(t["red_xy"][:2]), tuple(t["slot_xy"][:2])))
        _TRAIN[key] = out
    return _TRAIN[key]


def train_nb(sc, path):
    """시작 장면의 빨강·링 칸이 모두 50 mm·80 mm 안에 드는 학습 판 수(없으면 None)."""
    if not (sc.get("red_xy") and sc.get("slot_xy")):
        return None
    T = train_xy(path)
    if not T:
        return None
    d = [max(math.dist(r, sc["red_xy"]), math.dist(q, sc["slot_xy"])) for r, q in T]
    return {"n_train": len(T), "within50": sum(x < 50 for x in d), "within80": sum(x < 80 for x in d), "nearest_mm": round(min(d), 1)}
KO = {"success": "성공", "partial": "부분", "fail": "실패", "invalid": "무효", "?": "?"}
STAGES = [("grasp", "잡기"), ("lift", "들기"), ("over_slot", "칸 위로"), ("insert", "꽂기"), ("release", "놓기"), ("end", "끝 장면")]
CSV_COLS = ["n", "stamp", "layout", "k", "cond", "auto", "human", "type", "reason", "grasp", "lift", "over_slot", "insert", "release",
            "end", "width_3s", "slot_min_mm", "insert_min_z", "end_mm", "t_exec", "rtt_med", "memo", "dir"]


def bench_dir(work, name):
    d = Path(work) / "bench" / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def bench_rows(d):
    import csv
    p = Path(d) / "results.csv"
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def bench_look(r, prefix):
    """3인칭 한 장으로 받침·구멍·빨강·빨간 링 칸을 찾는다(fr5auto 인식 그대로 — 판정에만 쓰고 정책에는 안 준다, 로봇 안 움직임).
    3인칭·손목 원본과 인식 겹친 그림을 prefix_*.png 로 남긴다."""
    out = {"ok": False}
    try:
        for cam in ("third", "wrist"):
            raw, _ = grab(r, cam)
            Path(f"{prefix}_{cam}.png").write_bytes(raw)
    except Exception as e:                                               # noqa: BLE001
        out["img_err"] = str(e)
    try:
        from fr5auto import rackcal as RCAL
        from fr5auto import rackcli as RCLI
        from fr5auto import rackvis as RV
        from fr5auto.rackstation import summary as rs_summary
        cfg, wd = r.cfg, r.work
        rc = cfg["rack"]
        intr = RCLI._intr(cfg.get("fr5rec_url", "http://127.0.0.1:8780")) or ((RCAL.load(wd) or {}).get("third") or {}).get("intr")
        cam, T_bc = RCAL.third_cam(RCAL.load(wd), intr)
        if cam is None:
            raise RuntimeError("3인칭 카메라 보정이 없다")
        img = RCLI._frame(cfg)
        sc = RV.scene(img, cam, T_bc, rc, float(rc["z_top_mm"]), roi=rc.get("roi"), n_racks=int(rc["n_racks"]))
        RV.by_x(sc)
        RCLI.draw_look(img, sc, cam, T_bc, rc, Path(f"{prefix}_look.png"))
        reds = [(i, j) for i, F in enumerate(sc["racks"]) for j, s in enumerate(F["state"]) if s == "red"]

        def hxy(h):
            hh = sc["racks"][h[0]]["holes"][h[1]]
            return [round(float(hh[0]), 1), round(float(hh[1]), 1)]
        out.update(ok=bool(sc.get("ok")), why=list(sc.get("why") or []), summary=rs_summary(sc), n_red=len(reds),
                   red=list(reds[0]) if len(reds) == 1 else None,
                   slot=list(sc["slot"]) if sc.get("slot") is not None else None,
                   racks=[{"x": round(float(F["x"]), 1), "y": round(float(F["y"]), 1), "yaw": round(float(F["yaw"]), 1),
                           "state": list(F["state"])} for F in sc["racks"]],
                   holes=[[hxy((i, j)) for j in range(len(F["holes"]))] for i, F in enumerate(sc["racks"])])
        if out["red"]:
            out["red_xy"] = hxy(out["red"])
        if out["slot"]:
            out["slot_xy"] = hxy(out["slot"])
    except Exception as e:                                               # noqa: BLE001 — 인식이 안 되면 자동 판정만 빠진다
        out["why"] = [f"{type(e).__name__}: {e}"]
    return out


def look_text(sc):
    if not sc.get("racks"):
        return "인식 실패: " + "; ".join(sc.get("why") or [])
    s = sc.get("summary", "")
    if sc.get("red_xy"):
        s += f" · 빨강 받침{sc['red'][0]}:{sc['red'][1]} {sc['red_xy']}"
    else:
        s += f" · 빨강 {sc.get('n_red', 0)}개(하나여야 함)"
    s += f" · 링 받침{sc['slot'][0]}:{sc['slot'][1]} {sc['slot_xy']}" if sc.get("slot_xy") else " · 링 칸 못 찾음"
    return s


def range_warn(sc):
    out = []
    for key, nm, k2 in (("red_xy", "빨간 튜브", "grasp"), ("slot_xy", "빨간 링 칸", "release")):
        xy = sc.get(key)
        if not xy:
            continue
        (x0, x1), (y0, y1) = BENCH_RANGE[k2]
        if not (x0 <= xy[0] <= x1 and y0 <= xy[1] <= y1):
            out.append(f"{nm} {xy} 가 학습 범위(x {x0}~{x1}, y {y0}~{y1}) 밖")
    return out


def bench_cond(a, info):
    c = {"ckpt": info.get("ckpt"), "instr": info.get("instruction"), "speed": a.speed, "exec_steps": a.exec_steps, "blend": a.blend,
         "max_s": a.max_s, "post_release_s": a.post_release_s, "g_close": a.g_close, "g_open": a.g_open, "j6_window": a.j6_window,
         "j6_clamp": a.j6_clamp, "lift_guard": a.lift_guard, "dx": a.dx, "dy": a.dy, "dzg": a.dzg, "dzr": a.dzr,
         "max_reject": a.max_reject, "version": VERSION}
    import hashlib
    return c, hashlib.md5(json.dumps(c, sort_keys=True).encode()).hexdigest()[:6]


def bench_begin(r, a, info, stamp):
    d = bench_dir(r.work, a.bench_name)
    rows = bench_rows(d)
    cond, cid = bench_cond(a, info)
    cj = d / "conds.json"                                               # 조건 번호 → 조건 값(보고서가 조건별로 나눠 적는다)
    C = json.loads(cj.read_text()) if cj.exists() else {}
    if cid not in C:
        C[cid] = cond
        cj.write_text(json.dumps(C, ensure_ascii=False, indent=1))
    prev = {x.get("cond") for x in rows}
    valid = [x for x in rows if x.get("human") != "invalid" and x.get("cond") == cid]   # 같은 조건 안에서만 센다
    k = 1 + sum(1 for x in valid if str(x.get("layout")) == str(a.layout))
    n = 1 + len(valid)
    td = d / f"{stamp}_L{a.layout}-{k}"
    td.mkdir(parents=True, exist_ok=True)
    print(f"벤치마크 '{a.bench_name}' · 유효 시행 {n}번째 · 배치 {a.layout}-{k} · 조건 {cid}"
          + ("  ⚠ 이 배치는 이미 3회" if k > 3 else "") + ("  ⚠ 앞 시행과 조건이 다르다(따로 묶인다)" if prev and cid not in prev else ""))
    before = bench_look(r, td / "start")
    print("  시작 장면: " + look_text(before))
    for w in range_warn(before):
        print("  ⚠ " + w)
    nb = train_nb(before, a.train_data)
    if nb:
        before["train_nb"] = nb
        print(f"  학습 판 이웃: 빨강·링 칸이 모두 50 mm 안 {nb['within50']}판 · 80 mm 안 {nb['within80']}판(학습 {nb['n_train']}판) · 가장 가까운 판 {nb['nearest_mm']} mm"
              + ("  ⚠ 이웃이 적다 — 이 배치는 학습 분포 가장자리" if nb['within80'] < 6 else ""))
    ref = d / "layouts" / f"L{a.layout}.json"
    if ref.exists():
        R0 = json.loads(ref.read_text())
        for key, nm in (("red_xy", "빨간 튜브"), ("slot_xy", "빨간 링 칸")):
            if R0.get(key) and before.get(key):
                dd = math.dist(R0[key], before[key])
                if dd > 5.0:
                    print(f"  ⚠ {nm} 자리가 배치 사진 때보다 {dd:.0f} mm 다르다 — 테이프 표시대로 복원")
    else:
        print(f"  (배치 사진 없음 — look --layout {a.layout} 로 먼저 남기면 복원을 비교한다)")
    if not (before.get("red_xy") and before.get("slot_xy")):
        print("  ⚠ 빨강·링 칸을 못 찾아 칸 위로·꽂기·끝 장면은 자동 판정을 못 한다(사람 판정은 된다)")
        if input("그래도 시작? y > ").strip().lower() != "y":
            raise Abort("시작 장면 인식 실패 — 시작 안 함")
    return {"dir": td, "root": d, "layout": a.layout, "k": k, "n": n, "before": before, "after": None, "cond": cond, "cid": cid}


def bench_stages(trace, events, before, after, z_rel_med, reason):
    """10 Hz 실측(관절·그리퍼 pos)과 시작·끝 장면으로 단계 판정. 앞 단계를 못 하면 뒤 단계는 None(못 감)."""
    S = {k: None for k, _ in STAGES}
    M = {}
    close = next((e for e in events if e.get("ev") == "close"), None)
    opn = next((e for e in events if e.get("ev") == "open"), None)
    T = [(t, np.asarray(j, float), float(p)) for t, j, p in trace if j is not None]
    if close is None:
        S["grasp"] = False
    else:
        tc = float(close.get("tm") or 0.0)
        aft = [x for x in T if x[0] >= tc]
        s3 = next((x for x in aft if x[0] >= tc + 3.0), aft[-1] if aft else None)
        w3 = None if s3 is None else s3[2] / 1000.0 * 95.0               # DH AG-95: pos 1000 = 95 mm
        if w3 is None and close.get("pos") is not None:
            w3 = float(close["pos"]) / 1000.0 * 95.0
        M["width_3s"] = None if w3 is None else round(w3, 1)
        S["grasp"] = bool(w3 is not None and 20.0 <= w3 <= 50.0)
    if S["grasp"]:
        to = float(opn["tm"]) if opn and opn.get("tm") else float("inf")
        hold = [(t, K.fk(j)[1], p / 1000.0 * 95.0) for t, j, p in T if tc <= t < to]
        z0 = hold[0][1][2] if hold else None
        rise, drop, H = 0.0, False, []
        for t, p, w in hold:
            if w < 12.0:
                if rise > 30.0:
                    drop = True
                break
            rise = max(rise, p[2] - z0)
            H.append(p)
        M["lift_mm"] = round(float(rise), 1)
        M["dropped"] = bool(drop)
        S["lift"] = bool(rise > 30.0 and not drop)
        if S["lift"] and before.get("slot_xy") and H:
            sx = np.asarray(before["slot_xy"], float)
            dh = [float(np.linalg.norm(p[:2] - sx)) for p in H]
            M["slot_min_mm"] = round(min(dh), 1)
            S["over_slot"] = bool(min(dh) < 20.0)
            zin = [p[2] for p, d in zip(H, dh) if d < 14.0]
            M["insert_min_z"] = round(float(min(zin)), 1) if zin else None
            S["insert"] = bool(S["over_slot"] and zin and min(zin) < z_rel_med + 12.0)
        if S["lift"]:
            S["release"] = opn is not None
        if S["release"] and after is not None and before.get("slot_xy"):
            if after.get("red_xy"):
                de = math.dist(after["red_xy"], before["slot_xy"])
                M["end_mm"] = round(de, 1)
                S["end"] = bool(de <= 14.0)
                if not S["end"] and de <= 32.0:
                    M["end_note"] = "옆 칸"
            else:
                S["end"] = False
                M["end_note"] = f"끝 장면에서 빨강 {after.get('n_red', 0)}개"
    # 자동 결과·유형
    stop = ("안전장치 중단" if reason.startswith("안전 검사") else "사람 멈춤" if reason.startswith("Ctrl") else
            "시간 초과" if reason.startswith("시간") else "멈춤(" + reason[4:40] + ")" if reason.startswith("멈춤") else "")
    if not S["grasp"]:
        auto = "fail"
        w3 = M.get("width_3s")
        typ = (stop or "쥐기 시도 없음") if close is None else ("헛잡음" if w3 is not None and w3 < 5.0 else
                                                          "걸림(폭 50 mm 넘음)" if w3 is not None and w3 > 50.0 else "쥐기 실패")
    elif S["release"] and S["end"]:
        auto, typ = ("success", "") if S["insert"] else ("partial", "얹힘 의심 — 눈으로")
    else:
        auto = "partial"
        typ = ("떨어뜨림" if M.get("dropped") else "못 듦" if not S["lift"] else
               (stop or "못 놓음") if not S["release"] else
               "칸 옆에 놓음" if S["over_slot"] is False else "얹힘·덜 꽂힘" if S["insert"] is False else
               "끝 장면 확인 못 함" if S["end"] is None else "칸 옆에 놓음")
    if any(s in reason for s in ("제어기 오류", "fr5rec", "정책 서버", "송신 스레드", "관절 값")):
        typ = (typ + " · " if typ else "") + "무효 후보(정책과 무관한 멈춤인지 확인)"
    return S, M, auto, typ


def bench_finish(r, a, summ, bench, st):
    """자동 판정 → 사람 확인(Enter = 맞음) → 시행 폴더(meta.json·trace.jsonl·사진)·results.csv."""
    import csv
    trace = list(st.trace) if st is not None else []
    S, M, auto, typ = bench_stages(trace, summ.get("events") or [], bench["before"], bench.get("after"), a.z_release_med,
                                   str(summ.get("reason", "")))
    mk = {True: "✓", False: "✗", None: "-"}
    print("자동 판정: " + KO[auto] + " — " + " · ".join(f"{nm} {mk[S[k]]}" for k, nm in STAGES)
          + (f" · {typ}" if typ else "") + (f" · 끝 장면 칸에서 {M['end_mm']} mm" if M.get("end_mm") is not None else ""))
    v = input("Enter = 자동 판정 맞음 · 고치려면 s 성공 / p 부분 / f 실패 / x 무효 (뒤에 메모) > ").strip()
    letters = {"s": "success", "p": "partial", "f": "fail", "x": "invalid"}
    if v and v[0].lower() in letters and (len(v) == 1 or v[1] == " "):
        human, memo = letters[v[0].lower()], v[1:].strip()
    else:
        human, memo = auto, v
    memo = f"{bench['layout']}-{bench['k']}" + (f" {memo}" if memo else "")
    summ.update(verdict=human, note=memo, auto=auto, type=typ, stages=S, metrics=M, layout=bench["layout"], k=bench["k"],
                bench=a.bench_name, cond=bench["cond"], cond_id=bench["cid"])
    td = bench["dir"]
    with open(td / "trace.jsonl", "w") as f:
        for t, j, p in trace:
            f.write(json.dumps({"t": t, "joints": j, "grip_pos": p}) + "\n")
    meta = {k: summ.get(k) for k in summ if k not in ("rtt", "infer")}
    meta.update(before=bench["before"], after=bench.get("after"), rtt_med=float(np.median(summ["rtt"])) if summ.get("rtt") else None,
                z_release_med=a.z_release_med, chunk_log=str(summ.get("chunk_log")))
    (td / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    p = bench["root"] / "results.csv"
    new = not p.exists()
    yn = lambda x: "-" if x is None else ("1" if x else "0")                      # noqa: E731
    row = {"n": bench["n"] if human != "invalid" else "", "stamp": summ["t"], "layout": bench["layout"], "k": bench["k"],
           "cond": bench["cid"], "auto": auto, "human": human, "type": typ, "reason": summ.get("reason"),
           **{k: yn(S[k]) for k, _ in STAGES}, "width_3s": M.get("width_3s"), "slot_min_mm": M.get("slot_min_mm"),
           "insert_min_z": M.get("insert_min_z"), "end_mm": M.get("end_mm"), "t_exec": summ.get("t_exec"),
           "rtt_med": meta["rtt_med"], "memo": memo, "dir": td.name}
    with open(p, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        if new:
            w.writeheader()
        w.writerow(row)
    print(f"벤치마크 기록: {td} · {p}  ({KO[human]}{'' if human == auto else ' — 자동 ' + KO[auto] + '에서 고침'})")


def cmd_look(a):
    """배치 사진·인식(로봇 안 움직임, 초기 자세에서). --layout N 이면 bench/<이름>/layouts/LN.* 로 남겨 시행마다 복원을 비교한다."""
    r, _, _, _ = setup(a, need_sender=False, need_policy=False)
    d = bench_dir(r.work, a.bench_name) / "layouts"
    d.mkdir(parents=True, exist_ok=True)
    tag = f"L{a.layout}" if a.layout else time.strftime("look_%Y%m%d_%H%M%S")
    sc = bench_look(r, d / tag)
    print(look_text(sc))
    for i, F in enumerate(sc.get("racks") or []):
        print(f"  받침{i}: ({F['x']}, {F['y']}) mm · {F['yaw']}° · {F['state']}")
    for w in range_warn(sc):
        print("  ⚠ " + w)
    if a.layout:
        if sc.get("red_xy") and sc.get("slot_xy"):
            (d / f"{tag}.json").write_text(json.dumps(sc, ensure_ascii=False, indent=1))
            print(f"배치 {a.layout} 저장: {d / tag}.json · 사진 {d / tag}_third.png · 인식 {d / tag}_look.png")
        else:
            print("빨강·링 칸을 못 찾아 배치를 저장하지 않았다 — 받침이 3인칭 화면에 다 보이게, 링이 보이게")


def cmd_report(a):
    """results.csv → 보고 지표(조건별): 성공률(Wilson 95%) · 배치별 x/3 · 단계별 · 실패 유형 · 소요 시간·왕복 · 무효 · 자동-사람 일치."""
    from collections import Counter, defaultdict
    cfg = CF.load(a.config)
    d = bench_dir(CF.work_dir(cfg), a.bench_name)
    rows = bench_rows(d)
    if not rows:
        sys.exit(f"기록 없음: {d / 'results.csv'}")
    by = defaultdict(list)
    for x in rows:
        by[x["cond"]].append(x)

    def wilson(s, n, z=1.96):
        if n == 0:
            return 0.0, 0.0
        p = s / n
        c = (p + z * z / (2 * n)) / (1 + z * z / n)
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
        return max(0.0, c - h), min(1.0, c + h)
    for cid, R in by.items():
        V = [x for x in R if x["human"] != "invalid"]
        I = [x for x in R if x["human"] == "invalid"]
        n = len(V)
        cnt = Counter(x["human"] for x in V)
        lo, hi = wilson(cnt["success"], n)
        cv = (json.loads((d / "conds.json").read_text()) if (d / "conds.json").exists() else {}).get(cid, {})
        print(f"\n## 조건 {cid} — 유효 {n}회 (무효 {len(I)})"
              + (f" · 속도 {cv.get('speed')} · 실행 칸 {cv.get('exec_steps')} · 최대 {cv.get('max_s')} s · {str(cv.get('ckpt', '')).split('/')[-1]}" if cv else ""))
        if n:
            print(f"성공률 {cnt['success']}/{n} = {cnt['success'] / n * 100:.0f}% (Wilson 95% {lo * 100:.0f}–{hi * 100:.0f}%) · "
                  f"부분 {cnt['partial']} · 실패 {cnt['fail']}")
        L = defaultdict(list)
        for x in V:
            L[x["layout"]].append(x)
        print("\n| 배치 | 성공 | 결과 |\n|---|---|---|")
        for lay in sorted(L, key=lambda s: int(s) if str(s).isdigit() else 999):
            X = L[lay]
            print(f"| {lay} | {sum(1 for x in X if x['human'] == 'success')}/{len(X)} | "
                  + " ".join(KO[x["human"]] for x in sorted(X, key=lambda x: x["stamp"])) + " |")
        print(f"3회 모두 성공한 배치: {sum(1 for X in L.values() if len(X) >= 3 and all(x['human'] == 'success' for x in X))}개")
        print("\n| 단계 | 간 시행 | 비율 |\n|---|---|---|")
        for k, nm in STAGES:
            s = sum(1 for x in V if x.get(k) == "1")
            print(f"| {nm} | {s}/{n} | {s / max(1, n) * 100:.0f}% |")
        ty = Counter(x["type"] or "-" for x in V if x["human"] != "success")
        print("\n실패·부분 유형: " + (" · ".join(f"{t} {c}" for t, c in ty.most_common()) or "-"))
        ts = [float(x["t_exec"]) for x in V if x["human"] == "success" and x.get("t_exec")]
        rt = [float(x["rtt_med"]) for x in V if x.get("rtt_med")]
        print(f"성공 시행 소요 시간 중간값 {np.median(ts):.1f} s" if ts else "성공 시행 없음", end=" · ")
        print(f"왕복 지연 중간값 {np.median(rt):.0f} ms" if rt else "")
        if I:
            print("무효 사유: " + " · ".join(f"{x['memo']}" for x in I))
        agree = sum(1 for x in R if x["auto"] == x["human"])
        print(f"자동 판정–사람 판정 일치 {agree}/{len(R)}")
    print("\n주의: 같은 배치의 3회는 서로 비슷하게 나오기 쉬워 30회 전체의 95% 구간은 실제보다 조금 좁다.")


def cmd_ringaudit(a):
    """학습 데이터 점검(로봇 안 움직임): 판마다 첫 프레임에서 fr5auto 인식으로 빨간 링 칸을 다시 찾고,
    수집기가 실제로 꽂은 칸(tag slot_xy)·마지막 프레임의 빨간 튜브 자리와 비교한다 — 링과 다른 칸에 꽂은 판이 섞였는지."""
    from fr5auto import rackcal as RCAL
    from fr5auto import rackcli as RCLI
    from fr5auto import rackvis as RV
    from fr5auto.rackstation import summary as rs_summary
    cfg = CF.load(a.config)
    wd = CF.work_dir(cfg)
    rc = cfg["rack"]
    intr = RCLI._intr(cfg.get("fr5rec_url", "http://127.0.0.1:8780")) or ((RCAL.load(wd) or {}).get("third") or {}).get("intr")
    cam, T_bc = RCAL.third_cam(RCAL.load(wd), intr)
    if cam is None:
        sys.exit("3인칭 카메라 보정이 없다")
    ds = a.ep.expanduser()

    def look(img_path):
        img = RCLI._frame(cfg, str(img_path))
        sc = RV.scene(img, cam, T_bc, rc, float(rc["z_top_mm"]), roi=rc.get("roi"), n_racks=int(rc["n_racks"]))
        RV.by_x(sc)
        reds = [(i, j) for i, F in enumerate(sc["racks"]) for j, st_ in enumerate(F["state"]) if st_ == "red"]

        def hxy(h):
            hh = sc["racks"][h[0]]["holes"][h[1]]
            return np.array([float(hh[0]), float(hh[1])])
        return sc, (hxy(sc["slot"]) if sc.get("slot") is not None else None), (hxy(reds[0]) if len(reds) == 1 else None)
    rows, n_ring, n_bad, n_end_bad, n_end = [], 0, 0, 0, 0
    print("판 · 첫 프레임 인식 · 링 칸(첫) · 꽂은 칸(tag) · 링↔꽂은 칸 mm · 끝 프레임 빨강 · 빨강↔링 mm")
    for ep in sorted(p for p in ds.glob("ep_*") if (p / "meta.json").exists()):
        m = json.loads((ep / "meta.json").read_text())
        tag = ((m.get("fr5rec") or {}).get("tag") or {})
        tgt = np.array(tag["slot_xy"], float) if tag.get("slot_xy") else None
        n = int(m.get("n_frames") or len(m.get("frames") or []))
        try:
            sc0, ring0, _ = look(ep / "rgb" / "00000.png")
            sc1, _, red1 = look(ep / "rgb" / f"{n - 1:05d}.png")
        except Exception as e:                                           # noqa: BLE001
            print(f"  {ep.name}: 인식 실패 {type(e).__name__}: {e}")
            continue
        d_rt = None if ring0 is None or tgt is None else float(np.linalg.norm(ring0 - tgt))
        d_er = None if ring0 is None or red1 is None else float(np.linalg.norm(red1 - ring0))
        n_ring += ring0 is not None
        bad = d_rt is not None and d_rt > 15.0
        n_bad += bad
        if d_er is not None:
            n_end += 1
            n_end_bad += d_er > 15.0
        flag = " ◀ 링과 다른 칸" if bad else (" ◀ 끝 빨강이 링 칸 아님" if d_er is not None and d_er > 15.0 else "")
        if a.all or flag or ring0 is None:
            f = lambda v: "-" if v is None else f"({v[0]:.0f}, {v[1]:.0f})"          # noqa: E731
            print(f"  {ep.name} · {rs_summary(sc0)} · {f(ring0)} · {f(tgt)} · {'-' if d_rt is None else f'{d_rt:.0f}'} · "
                  f"{f(red1)} · {'-' if d_er is None else f'{d_er:.0f}'}{flag}{'  (첫 프레임에서 링 못 찾음)' if ring0 is None else ''}")
        rows.append({"ep": ep.name, "ring0": None if ring0 is None else ring0.round(1).tolist(), "target": None if tgt is None else tgt.round(1).tolist(),
                     "d_ring_target": d_rt, "red_end": None if red1 is None else red1.round(1).tolist(), "d_end_ring": d_er})
    N = len(rows)
    print(f"\n{N} 판 · 첫 프레임에서 링을 찾은 판 {n_ring} · 링과 꽂은 칸이 15 mm 넘게 다른 판 {n_bad} · "
          f"끝 프레임 빨강이 링 칸에서 15 mm 넘게 떨어진 판 {n_end_bad}/{n_end}")
    out = Path(f"ringaudit_{time.strftime('%Y%m%d_%H%M%S')}.json")
    out.write_text(json.dumps(rows, ensure_ascii=False))
    print(f"판별 결과: {out.resolve()}")


def cmd_mark(a):
    """기록 고치기(지우지 않음): results.csv 의 그 시행 사람 판정·메모를 바꾸고, 고친 내력을 meta.json·marks.jsonl 에 남긴다."""
    import csv
    cfg = CF.load(a.config)
    d = bench_dir(CF.work_dir(cfg), a.bench_name)
    rows = bench_rows(d)
    letters = {"s": "success", "p": "partial", "f": "fail", "x": "invalid"}
    if not a.stamp or a.set not in letters:
        sys.exit("mark --stamp <시행 시각> --set s|p|f|x --memo \"이유\"")
    hit = [x for x in rows if x["stamp"] == a.stamp]
    if len(hit) != 1:
        sys.exit(f"시행 {a.stamp} 를 results.csv 에서 {len(hit)}개 찾음(1개여야)")
    x = hit[0]
    old = x["human"]
    x["human"] = letters[a.set]
    x["memo"] = (x.get("memo") or "") + f" · 고침 {KO[old]}→{KO[x['human']]}: {a.memo}"
    with open(d / "results.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        w.writeheader()
        for y in rows:
            w.writerow({c: y.get(c, "") for c in CSV_COLS})
    rec = {"t": time.strftime("%Y%m%d_%H%M%S"), "stamp": a.stamp, "from": old, "to": x["human"], "memo": a.memo}
    with open(d / "marks.jsonl", "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    mp = d / x["dir"] / "meta.json"
    if mp.exists():
        m = json.loads(mp.read_text())
        m.setdefault("marks", []).append(rec)
        m["verdict"] = x["human"]
        mp.write_text(json.dumps(m, ensure_ascii=False, indent=1))
    print(f"{a.stamp} ({x['layout']}-{x['k']}): {KO[old]} → {KO[x['human']]} · {a.memo}")


def cmd_run(a):
    r, pol, info, cfg = setup(a, need_sender=False)
    instr = info.get("instruction")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    log = r.work / f"policy_try_{stamp}.jsonl"
    summ = {"t": stamp, "ckpt": info.get("ckpt"), "corr": {"dx": a.dx, "dy": a.dy, "dzg": a.dzg, "dzr": a.dzr, "speed": a.speed,
                                                                      "j6_clamp": a.j6_clamp, "lift_guard": a.lift_guard},
            "exec_steps": a.exec_steps, "events": [], "rtt": [], "infer": [], "chunk_log": str(log)}
    print(f"보정 dx {a.dx:+g} dy {a.dy:+g} mm · 잡기 전 dz {a.dzg:+g} · 쥔 뒤 dz {a.dzr:+g} mm · 속도 ×{a.speed:g} · 앞 {a.exec_steps} 스텝씩 · 최대 {a.max_s:g} s")
    if input("받침·튜브·링이 정한 자리에 있고 팔 주변이 비었으면 y > ").strip().lower() != "y":
        print("시작 안 함")
        return
    ep, bench, box = None, None, {"st": None}
    try:
        r.start()                                                       # 송신 시작 → 제어판 [리더 추종 시작]
        home = np.asarray(r.home())
        j, tcp, gpos = snapshot(r)
        if float(np.abs(j - home).max()) > 1.5:
            if input(f"초기 자세에서 {float(np.abs(j - home).max()):.1f}° 벗어나 있다 — 초기 자세로 갈까? y > ").strip().lower() != "y":
                raise Abort("초기 자세가 아니다")
            r.go_home()
            j, tcp, gpos = snapshot(r)
        if gpos < 980:                                                  # 학습 데이터는 다 연 상태(pos 1000, g 0.040)에서 시작
            grip_to(r, j, 1.0, False)
        if a.layout:                                                    # 벤치마크: 시작 장면(인식·사진)·배치-회차
            bench = bench_begin(r, a, info, stamp)
        if a.record:
            st = r.rec.get("/api/status")["rec"]
            name = str((st.get("session") or {}).get("name") or "")
            if st.get("state") != "ready" or not any(k in name for k in ("eval", "policy")):
                raise Abort(f"녹화는 이름에 eval/policy 가 든 fr5rec 세션에서만(지금 '{name}', {st.get('state')}) — 수집 데이터셋과 섞이지 않게")
            rr = r.rec.post("/api/episode/start", {"tag": {"by": "policy_try", "ckpt": info.get("ckpt"), "corr": summ["corr"]}}, timeout=15.0)
            if not rr.get("ok"):
                raise Abort(f"fr5rec 녹화 시작 실패: {rr.get('error')}")
            ep = rr.get("episode")
        L = r.ld()
        floor_z = float(L.get("z_min") or 45.0) + a.floor_margin
        limits = r.rc["joint_limits"]
        closed, released_at, nq, t_exec = False, None, 0, 0.0
        j, _, _ = snapshot(r)
        dtx = 0.1 / a.speed                                             # 학습 한 스텝(0.1 s)이 실행에서 걸리는 시간
        rtt_est, plan_est = 350.0, 80.0
        st = Streamer(r, j, 1.0).start()                                # 이제부터 보내기는 Streamer 만 한다
        box["st"] = st
        cur = None                                                      # (시각들, 작업 프레임 행동들) — 지금 시간표가 따르는 행동(섞기 기준)
        from_rest = True                                                # 서 있다가 물은 묶음(시작·그리퍼 뒤)은 지금부터 시간을 센다
        pending = Ask(r, pol, instr, a.timeout)
        rej = 0                                                         # 연속으로 버린 묶음 수
        grasp_w, lifted, guard_n = None, False, 0                       # 잡은 자리(작업 프레임 m) · 60 mm 들었는지 · 곧게 들기 묶음 수
        t0 = time.monotonic()
        reason = "?"
        try:
            while True:
                if time.monotonic() - t0 > a.max_s:
                    reason = f"시간 {a.max_s:g} s"
                    break
                if pending is None:
                    pending = Ask(r, pol, instr, a.timeout)
                chunk, t_obs, s8, rtt, inf = pending.get(st)
                pending = None
                nq += 1
                rtt_est = 0.7 * rtt_est + 0.3 * rtt
                summ["rtt"].append(round(rtt))
                summ["infer"].append(round(inf))
                tp0 = time.monotonic()
                lead = min(0.4, max(0.08, 1.5 * plan_est / 1000.0))      # 계획(IK)이 끝나기 전에 끼울 시각이 오지 않게
                t_s = tp0 + lead
                H = len(chunk)
                if from_rest:
                    tk_all, m = t_s + (np.arange(H) + 1) * dtx, 0
                else:                                                   # 행동 k 의 시각 = 관측 + (k+1)·dtx, t_s 뒤 첫 행동부터
                    tk_all = t_obs + (np.arange(H) + 1) * dtx
                    m = min(int(np.searchsorted(tk_all, t_s + 0.02)), H - 1)
                k_end = min(m + a.exec_steps, H)

                def flips(i):
                    g = chunk[i, 6]
                    return (not closed and g < a.g_close) or (closed and g > a.g_open)
                jc = next((i for i in range(m, k_end) if flips(i)), None)
                if jc is not None:
                    k_last = jc
                else:                                                   # 꼬리(다음 묶음이 늦을 때만 감)에는 그리퍼 바뀜을 넣지 않는다
                    k_last = next((i - 1 for i in range(k_end, H) if flips(i)), H - 1)
                idx = list(range(m, k_last + 1))
                tk = tk_all[idx]
                rows, nb = chunk[idx].copy(), 0
                if cur is not None and a.blend > 0:                     # 지금 따르는 행동(같은 시각)에서 새 묶음으로 서서히
                    old = []
                    for t in tk[: a.blend]:
                        o = pose_at(cur[0], cur[1], t)
                        if o is None:
                            break
                        old.append(o)
                    if old:
                        rows, nb = blend_rows(rows, np.asarray(old), len(old))
                if tk[0] < t_s + 0.02:                                  # 응답이 아주 늦었으면 시각을 민다(시간표가 거꾸로 가지 않게)
                    tk = tk + (t_s + 0.02 - tk[0])
                q_s = st.at(t_s)
                Rc, pc = K.fk(q_s)
                guarded = False
                if closed and a.lift_guard and grasp_w is not None and not lifted:   # 튜브가 구멍 안인 동안 옆으로 끌지 않게(선택, 기록됨)
                    guard_n += 1
                    if pc[2] - grasp_w[2] * 1000 >= a.lift_mm or guard_n > 6:   # 다 들었거나 6 묶음 넘게 못 들면 놓아준다(제자리 맴돌기 방지)
                        lifted = True
                    else:
                        for jj in range(len(rows)):
                            if (rows[jj, 2] - grasp_w[2]) * 1000 < a.lift_mm:
                                rows[jj, :2] = grasp_w[:2]
                                guarded = True
                Q, why, P = plan_steps(rows, len(idx), q_s, pc, Rc, home, a, closed, floor_z, limits)
                n_x = (jc - m + 1) if jc is not None else (k_end - m)    # 실행할 스텝 수(나머지는 꼬리)
                tail_why = []
                if Q is None and len(idx) > n_x:                        # 꼬리만 걸리면 꼬리를 버리고 실행할 스텝만
                    tail_why = why
                    idx, tk, rows = idx[:n_x], tk[:n_x], rows[:n_x]
                    Q, why, P = plan_steps(rows, len(idx), q_s, pc, Rc, home, a, closed, floor_z, limits)
                plan_ms = (time.monotonic() - tp0) * 1000
                plan_est = 0.7 * plan_est + 0.3 * plan_ms
                t_old_end, _ = st.end()
                stall = max(0.0, time.monotonic() - t_old_end) * 1000   # 시간표가 끝나 서 있던 시간(끊김)
                rs = rot_steps(np.vstack([R_to_rotvec_row(Rc, pc), rows])) if len(rows) else []
                with open(log, "a") as f:
                    f.write(json.dumps({"q": nq, "t": round(time.monotonic() - t0, 2), "s8": s8, "chunk": chunk.round(5).tolist(),
                                        "skip": m, "idx": [idx[0], idx[-1]], "exec_end": k_end - 1, "grip_change": jc, "why": why,
                                        "rtt": round(rtt), "infer": round(inf), "blend": nb, "exec": np.asarray(rows).round(5).tolist(),
                                        "plan_ms": round(plan_ms), "lead_ms": round(lead * 1000), "stall_ms": round(stall),
                                        "dev_max": round(st.dev_max, 2), "rot_steps": [round(v, 2) for v in rs],
                                        "from_rest": from_rest, "tail_why": tail_why}) + "\n")
                if Q is None:                                           # 위험한 묶음은 보내지 않는다 — 지금 시간표(꼬리)를 가며 바로 다시 묻는다
                    rej += 1
                    print(f"  묶음 {nq:3d} 버림({rej}/{a.max_reject}): {'; '.join(why)} · 스텝 회전(°) {' '.join(f'{v:.1f}' for v in rs)}")
                    if rej >= a.max_reject:
                        reason = f"안전 검사(연속 {rej}번): " + "; ".join(why)
                        break
                    pending = Ask(r, pol, instr, a.timeout)
                    continue
                rej = 0
                st.replace(t_s, tk, Q)
                cur = (tk, rows)
                from_rest = False
                t_exec = time.monotonic() - t0
                print(f"  묶음 {nq:3d} · 건너뜀 {m} · {len(idx)} 스텝(실행 {min(k_end, k_last + 1) - m}) · 섞음 {nb} · 왕복 {rtt:.0f} · 계획 {plan_ms:.0f} · "
                      f"멈춤 {stall:.0f} ms · z {P[min(len(P), k_end - m) - 1, 2]:.0f} mm · g {chunk[min(k_end, k_last + 1) - 1, 6] * 1000:.1f} mm"
                      + (f" · {'; '.join(why)}" if why else "") + (" · 곧게 들기" if guarded else "")
                      + ("" if jc is None else (" → 닫기" if not closed else " → 열기")))
                if jc is not None:                                      # 바뀌는 스텝까지 간 뒤 서서 그리퍼
                    t_e, q_e = st.end()
                    wait_until(t_e, st)
                    r.settle(q_e)
                    p0 = r._grip_pos(r._guard())
                    st.grip = 1.0 if closed else 0.0
                    gs = r.grip_wait(closing=not closed, want=st.grip, p0=p0)
                    xyz = [round(float(v), 1) for v in K.fk(q_e)[1]]           # 닫은·연 자리(베이스 mm) — 학습 데이터와 비교(datarot)
                    cur, from_rest = None, True
                    t_exec = time.monotonic() - t0
                    if not closed:
                        grasp_w, lifted, guard_n = RZ_W @ (np.asarray(K.fk(q_e)[1]) / 1000.0), False, 0
                        closed = True
                        caught = bool(gs.get("caught"))
                        summ["events"].append({"t": round(t_exec, 1), "ev": "close", "caught": caught, "pos": gs.get("pos"), "xyz": xyz,
                                                "tm": round(time.monotonic(), 3)})
                        print(f"  닫음 — 물체 {'잡음' if caught else '못 잡음'}(위치 {gs.get('pos')}) · 베이스 x {xyz[0]} y {xyz[1]} z {xyz[2]} mm")
                        if not caught and a.end_on_miss:
                            reason = "빈손으로 닫음"
                            break
                    else:
                        closed = False
                        released_at = time.monotonic()
                        grasp_w = None
                        summ["events"].append({"t": round(t_exec, 1), "ev": "open", "pos": gs.get("pos"), "xyz": xyz,
                                                "tm": round(time.monotonic(), 3)})
                        print(f"  열음 · 베이스 x {xyz[0]} y {xyz[1]} z {xyz[2]} mm")
                else:                                                   # 실행 끝 스텝 전에 응답·계획이 오도록 다음 묶음을 미리 묻는다
                    wait_until(tk_all[k_end - 1] - rtt_est / 1000.0 - lead - 0.05, st)
                    pending = Ask(r, pol, instr, a.timeout)
                if released_at is not None and time.monotonic() - released_at >= a.post_release_s:
                    reason = "놓은 뒤 끝"
                    break
        finally:
            st.halt()
        if st.err is not None and not isinstance(st.err, (Abort, Stuck)):
            raise Abort(f"송신 스레드 오류: {st.err}")
        t_exec = time.monotonic() - t0
        summ["dev_max"] = round(st.dev_max, 2)
        summ["reason"] = reason
        summ["t_exec"] = round(t_exec, 1)
        print(f"끝: {reason} · 묶음 {nq} · 실행 {t_exec:.1f} s")
        if ep is not None:
            r.rec.post("/api/episode/stop", {"reason": "자동: 정책 판 끝"}, timeout=120.0)
        if reason.startswith("안전 검사"):                               # 정책이 끝낸 게 아니다 — 선 자리를 보고 돌아간다
            input("정책이 끝낸 것이 아니라 안전 검사로 그 자리에 섰다 — 자리를 확인하고 Enter(초기 자세로) > ")
        r.go_home()                                                     # 곧게 들어 올린 뒤 초기 자세
        if bench is not None:                                           # 끝 장면: 초기 자세에서 3인칭 인식·사진(손목 사진도)
            bench["after"] = bench_look(r, bench["dir"] / "end")
            print("  끝 장면: " + look_text(bench["after"]))
        if float(r.sender.target[1]) < 0.5:
            input("그리퍼가 튜브를 쥔 채 초기 자세다 — 튜브를 손으로 잡고 Enter(그리퍼를 연다) > ")
            j, _, _ = snapshot(r)
            grip_to(r, j, 1.0, False)
    except KeyboardInterrupt:
        summ["reason"] = "Ctrl+C"
        print("\nCtrl+C — 송신을 끊는다(그 자리 멈춤). 제어판에서 확인한다")
    except (Abort, Stuck) as e:
        summ["reason"] = f"멈춤: {e}"
        print(f"멈춤: {e} — 그 자리에 섰다. 제어판에서 확인한 뒤 초기 자세로")
    finally:
        r.stop()
    if bench is not None:
        if bench.get("after") is None:
            print("  (그 자리에 섰다 — 끝 장면은 home 뒤 look 으로 다시 볼 수 있다. 판정은 사람이 정한다)")
        bench_finish(r, a, summ, bench, box["st"])
    else:
        v = input("결과 — s 성공 / f 실패 / x 무효 (뒤에 메모) > ").strip()
        summ["verdict"] = {"s": "success", "f": "fail", "x": "invalid"}.get(v[:1].lower(), "?")
        summ["note"] = v[1:].strip()
    if ep is not None:
        try:
            if summ["verdict"] in ("success", "fail", "partial"):
                r.rec.post("/api/episode/keep", {"outcome": "success" if summ["verdict"] == "success" else "fail",
                                                 "note": f"policy_try {summ['verdict']} {summ['note']}"}, timeout=30.0)
            else:
                r.rec.post("/api/episode/discard", {"reason": "policy_try 무효"}, timeout=30.0)
        except Abort as e:
            print(f"fr5rec 결정 실패: {e} — fr5rec 화면에서 정한다")
    with open(r.work / "policy_try.jsonl", "a") as f:
        f.write(json.dumps(summ, ensure_ascii=False) + "\n")
    print(f"기록: {r.work / 'policy_try.jsonl'} · 묶음 기록 {log}")


def cmd_home(a):
    r, _, _, _ = setup(a, need_sender=False, need_policy=False)
    try:
        r.start()
        r.go_home()
        if float(r.sender.target[1]) < 0.5:
            input("그리퍼가 닫힌 채 초기 자세다 — 튜브를 쥐고 있으면 손으로 잡고 Enter(그리퍼를 연다) > ")
            j, _, _ = snapshot(r)
            grip_to(r, j, 1.0, False)
        print("초기 자세 · 그리퍼 열림")
    except KeyboardInterrupt:
        print("\nCtrl+C — 그 자리 멈춤")
    finally:
        r.stop()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["conv", "check", "run", "home", "splice", "datarot", "snap", "look", "report", "mark", "ringaudit"])
    ap.add_argument("ep", nargs="?", type=Path, help="conv: 기록된 판 폴더(ep_NNN) · splice: 묶음 기록 policy_try_<시각>.jsonl")
    ap.add_argument("--url", default="http://127.0.0.1:8300")
    ap.add_argument("--config", default=None)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--exec-steps", type=int, default=8)
    ap.add_argument("--max-reject", type=int, default=3, help="안전 검사에 걸린 묶음을 버리고 다시 묻는 연속 횟수 한계")
    ap.add_argument("--blend", type=int, default=6, help="이음에서 이전 묶음 → 새 묶음으로 넘기는 스텝 수(0 = 끔)")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--max-s", type=float, default=None, help="판 시간 한계(기본 45/속도 s — 학습 판 평균 약 24 s)")
    ap.add_argument("--post-release-s", type=float, default=None, help="놓은 뒤 끝내기까지(기본 1.5 s · 벤치마크 2.5 s)")
    ap.add_argument("--layout", type=int, default=None, help="벤치마크 배치 번호(1~10) — 주면 시작·끝 장면 인식, 단계 판정, results.csv")
    ap.add_argument("--bench-name", default="rack_v2_20000", help="벤치마크 이름(기록 폴더 ~/fr5cap/fr5auto/work/bench/<이름>)")
    ap.add_argument("--train-data", default="~/fr5cap/datasets/fr5_autocollect10hz_20261103", help="학습 데이터셋 폴더 — 시작 장면의 학습 판 이웃 수를 센다")
    ap.add_argument("--stamp", default=None, help="mark: 고칠 시행 시각(results.csv stamp)")
    ap.add_argument("--set", default=None, help="mark: s 성공 / p 부분 / f 실패 / x 무효")
    ap.add_argument("--memo", default="", help="mark: 고친 이유")
    ap.add_argument("--all", action="store_true", help="ringaudit: 문제없는 판도 모두 출력")
    ap.add_argument("--z-release-med", type=float, default=148.1, help="학습 시연의 놓은 높이 중간값(베이스 mm) — 꽂기 판정 = 이것 + 12 mm 아래")
    ap.add_argument("--dx", type=float, default=0.0)
    ap.add_argument("--dy", type=float, default=0.0)
    ap.add_argument("--dzg", type=float, default=0.0)
    ap.add_argument("--dzr", type=float, default=0.0)
    ap.add_argument("--g-close", type=float, default=0.034, help="예측 g 가 이 아래로 내려가는 첫 스텝에서 서서 닫는다(다 열림 0.040)")
    ap.add_argument("--g-open", type=float, default=0.020, help="쥔 뒤 예측 g 가 이 위로 오르는 첫 스텝에서 서서 연다(튜브 쥠 ≈ 0.012)")
    ap.add_argument("--max-step-mm", type=float, default=30.0, help="한 스텝(0.1 s) 이동 한계 — 학습 데이터 최대 25.8 mm")
    ap.add_argument("--max-rot-step", type=float, default=8.0)
    ap.add_argument("--max-tilt", type=float, default=30.0)
    ap.add_argument("--min-radius", type=float, default=200.0)
    ap.add_argument("--max-radius", type=float, default=850.0)
    ap.add_argument("--floor-margin", type=float, default=10.0)
    ap.add_argument("--j6-window", type=float, default=60.0)
    ap.add_argument("--j6-clamp", type=float, default=10.0, help="J6 가 창을 이만큼까지 넘으면 창 끝에 묶는다(공구 축 둘레 회전만 바뀜) · 0 = 묶지 않고 버림")
    ap.add_argument("--lift-guard", action="store_true", help="쥔 뒤 --lift-mm 까지는 잡은 자리에서 곧게 든다(정책 수정 — 판 기록에 남음)")
    ap.add_argument("--lift-mm", type=float, default=60.0, help="곧게 들기 높이 — 튜브가 구멍에 든 길이(tube_len − tube_above = 60)")
    ap.add_argument("--record", action="store_true", help="이름에 eval/policy 가 든 fr5rec 세션에 녹화")
    ap.add_argument("--keep-going-on-miss", dest="end_on_miss", action="store_false", help="빈손으로 닫아도 판을 계속(기본: 끝냄)")
    a = ap.parse_args()
    if not (0.2 <= a.speed <= 1.5) or not (1 <= a.exec_steps <= 16):
        sys.exit("--speed 0.2~1.5 · --exec-steps 1~16")
    if a.max_s is None:
        a.max_s = 120.0 if a.layout else 45.0 / a.speed               # 벤치마크 최대 시간 120 s(평가 기준)
    if a.post_release_s is None:
        a.post_release_s = 2.5 if a.layout else 1.5
    try:
        if a.cmd == "conv":
            if not a.ep:
                sys.exit("conv 는 판 폴더를 준다: conv ~/fr5cap/datasets/<데이터셋>/ep_000")
            cmd_conv(a.ep.expanduser())
        elif a.cmd == "check":
            cmd_check(a)
        elif a.cmd == "home":
            cmd_home(a)
        elif a.cmd == "look":
            cmd_look(a)
        elif a.cmd == "report":
            cmd_report(a)
        elif a.cmd == "mark":
            cmd_mark(a)
        elif a.cmd == "ringaudit":
            if not a.ep:
                sys.exit("ringaudit 는 데이터셋 폴더를 준다: ringaudit ~/fr5cap/datasets/<데이터셋>")
            cmd_ringaudit(a)
        elif a.cmd == "snap":
            cmd_snap(a)
        elif a.cmd == "datarot":
            cmd_datarot(a.ep.expanduser())
        elif a.cmd == "splice":
            if not a.ep:
                sys.exit("splice 는 묶음 기록을 준다: splice ~/fr5cap/fr5auto/work/policy_try_<시각>.jsonl")
            cmd_splice(a.ep.expanduser())
        else:
            cmd_run(a)
    except Abort as e:
        sys.exit(f"멈춤: {e}")


if __name__ == "__main__":
    main()
