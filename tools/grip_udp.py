"""그리퍼를 정책 실행과 같은 길(fr5auto 송신 → UDP 8097 → 제어판)로 반쯤 닫았다가 연다. 팔은 지금 자세에 선다.
제어판이 UDP 그리퍼 값을 무시하는지 가리는 진단(docs/ISSUES.md 1절)."""
import os
import sys
import time

sys.path.insert(0, os.path.expanduser("~/fr5cap/fr5auto"))
from fr5auto import config as CF  # noqa: E402
from fr5auto.run import Runner  # noqa: E402

cfg = CF.load(None)
r = Runner(cfg, {}, [], CF.work_dir(cfg), say=print)
r.task = "rack"
try:
    r.start()
    q = list(r.sender.target[0])
    for want in (0.5, 1.0):
        p0, last, first = (r.st().get("gripper") or {}).get("pos"), None, None
        t0 = time.monotonic()
        r.sender.set(q, want)
        print(f"-> UDP grip {want} (지금 pos {p0})")
        while time.monotonic() - t0 < 5.0:
            g, t = r.st().get("gripper") or {}, time.monotonic() - t0
            cur = (g.get("target"), g.get("pos"), g.get("state"), g.get("err"))
            if cur != last:
                print(f"  {t:4.1f}s target {cur[0]} pos {cur[1]} state {cur[2]} err {cur[3]!r}")
                last = cur
            if first is None and isinstance(g.get("pos"), (int, float)) and abs(g["pos"] - p0) >= 20:
                first = t
            time.sleep(0.1)
        print(f"  pos 가 움직이기 시작: {'5 s 동안 안 움직임' if first is None else f'{first:.1f} s'}")
    L = r.ld()
    print("추종 상태:", {k: L.get(k) for k in ("status", "following", "connected")})
finally:
    r.stop()
