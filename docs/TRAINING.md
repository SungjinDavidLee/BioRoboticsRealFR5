# 학습

## 설정

| | |
|---|---|
| 모델 | GR00T N1.7 (`nvidia/GR00T-N1.7-3B`), Isaac-GR00T 커밋 `51d4c89` |
| 몸체 태그 | `NEW_EMBODIMENT` (모달리티 설정 `tools/fr5_rack_config.py`) |
| 입력 | 3인칭·손목 영상 각 1장(256×256), 손끝 자세(위치 + 회전 6D), 그리퍼, 지시문 |
| 출력 | 행동 16개(10 Hz에서 1.6 s). 손끝은 현재 자세 기준 상대값, 그리퍼는 절대값 |
| 데이터 | 200판, 학습 프레임 43,768 |
| 스텝 / batch | 20,000 / 16 (약 7.3 에폭) |
| GPU | RTX PRO 6000 Blackwell 1장 |
| 걸린 시간 | 6,461 s (약 1시간 48분), 3.1 it/s |
| 끝 무렵 손실 | 0.017 ~ 0.027 |
| 저장 | 20,000 스텝 체크포인트 하나만 |

손끝 행동을 상대값으로 학습하면 같은 동작이 받침 자리에 따라 다른 절대 좌표로 나와도 한 가지 모양으로 배운다.
그리퍼는 열림·닫힘 자체가 의미라서 절대값으로 둔다.

## 명령

```bash
# [학습 서버] 원본 → GR00T 데이터셋 (256×256, 성공 판만)
python3 tools/fr5_to_gr00t.py ~/fr5cap/datasets/<원본> ~/gr00t_data/fr5_rack_v2 --resize squash --size 256

# [학습 서버] 통계 계산 + 미세조정 (백그라운드, 로그는 <출력>.log)
STEPS=20000 SAVE=20000 BS=16 bash tools/train_fr5.sh ~/gr00t_data/fr5_rack_v2 ~/gr00t_runs/fr5_rack_v2 1
```

`train_fr5.sh`는 Isaac-GR00T의 `gr00t/data/stats.py`로 정규화 통계를 먼저 만들고 `launch_finetune.py`를 띄운다.
CUDA 툴킷이 없는 환경이면 deepspeed가 import 때 `nvcc`를 찾으므로, 가상환경 안의 nvcc나 대체 경로를 `CUDA_HOME`으로 잡는다.

## 로봇 없이 한 확인

정책 서버(`tools/fr5_policy_server.py`)에는 기록된 판을 그대로 넣어 보는 모드가 있다.
서버와 같은 전처리로 영상을 줄이고, 자세를 작업 좌표로 바꿔 넣은 뒤, 첫 행동을 다음 프레임 실제 자세와 비교한다.
학습에 쓴 판이라 일반화를 재는 것이 아니라, 전처리·자세 변환·상대값 복원이 서로 맞물리는지를 본다.
어긋나면 오차가 수십~수백 mm로 나온다.

```bash
python3 tools/fr5_policy_server.py --ckpt ~/gr00t_runs/fr5_rack_v2/checkpoint-20000 \
    --selftest ~/fr5cap/datasets/<원본> --episodes 0 100 199
```

| 판 | 표본 | 첫 행동 위치 오차 중앙 (최대) | 회전 | 그리퍼 | 추론 |
|---|---|---|---|---|---|
| ep_000 | 12 | 0.6 mm (2.6) | 0.05° | 0.12 mm | 122 ms |
| ep_100 | 13 | 1.1 mm (6.0) | 0.08° | 0.08 mm | 125 ms |
| ep_199 | 12 | 0.5 mm (7.4) | 0.09° | 0.04 mm | 123 ms |

## 정책 서버

```bash
python3 tools/fr5_policy_server.py --ckpt ~/gr00t_runs/fr5_rack_v2/checkpoint-20000 --port 8300
```

| | |
|---|---|
| `POST /act` | `{"third": PNG/JPEG base64, "wrist": base64, "state8": [x,y,z,rx,ry,rz,g,−g], "instruction": "..."}` → `{"chunk": [[x,y,z,rx,ry,rz,g] × 16], "infer_ms": ...}` |
| `GET /info` | 체크포인트, 행동 수, 지시문 |

`state8`은 작업 좌표 m·축각이다. 서버가 회전 6D로 바꿔 모델에 넣고, 모델이 낸 상대 행동을 절대 자세로 되돌려 축각으로 돌려준다.
평가 중 왕복 시간은 중앙 약 300 ms(영상 전송 포함), 추론만은 약 120 ms였다.
