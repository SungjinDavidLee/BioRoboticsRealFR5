#!/usr/bin/env bash
# FR5 받침 과제 GR00T N1.7 미세조정 (Isaac-GR00T launch_finetune, 백그라운드)
#   bash train_fr5.sh <변환한 데이터셋 폴더> <출력 폴더> [GPU 번호=1 | 두 장이면 0,1]
#   바꿀 때: STEPS=20000 SAVE=7000 BS=32 bash train_fr5.sh ...   (BS = 모든 GPU 합친 batch)
# 먼저 meta/stats.json·relative_stats.json 을 만들고(gr00t/data/stats.py) 학습을 띄운다.
# 로그: <출력 폴더>.log · 끝나면 <출력 폴더>/checkpoint-7000, -14000, -20000
set -euo pipefail
DS=$(realpath "$1"); OUT=$(realpath -m "$2"); GPU=${3:-1}; NG=$(echo "$GPU" | tr ',' '\n' | wc -l)
STEPS=${STEPS:-20000}; SAVE=${SAVE:-7000}; BS=${BS:-32}
HERE=$(dirname "$(realpath "$0")"); CFG=$HERE/fr5_rack_config.py
G=~/groot/Isaac-GR00T
[ -f "$DS/meta/modality.json" ] || { echo "데이터셋이 아니다: $DS"; exit 2; }
[ -e "$OUT" ] && { echo "출력 폴더가 이미 있다: $OUT — 다른 이름으로"; exit 2; }
pgrep -af launch_finetune.py && { echo "이미 학습이 돌고 있다(위) — 끝난 뒤"; exit 2; }
mkdir -p "$(dirname "$OUT")"                         # 로그(<출력>.log)를 쓸 상위 폴더
cd "$G"
# shellcheck disable=SC1091
source .venv/bin/activate
python -c "from torchcodec.decoders import VideoDecoder" || { echo "torchcodec 이 안 된다 — FFmpeg 설치부터"; exit 2; }
if [ -z "${CUDA_HOME:-}" ] && ! command -v nvcc >/dev/null; then    # deepspeed 가 import 때 nvcc 를 찾는다(CUDA 툴킷 없음)
  F=$(find .venv/lib/python3.12/site-packages/nvidia -path '*/bin/nvcc' -type f 2>/dev/null | head -1)
  if [ -n "$F" ]; then export CUDA_HOME=$(realpath "$(dirname "$(dirname "$F")")")
  elif [ -x ~/cuda_shim/bin/nvcc ]; then export CUDA_HOME=~/cuda_shim
  else echo "nvcc 없음 — ~/cuda_home.sh 로 CUDA_HOME 을 정한다"; exit 2; fi
fi
echo "== 통계(stats.json · relative_stats.json)"
CUDA_VISIBLE_DEVICES=${GPU%%,*} python gr00t/data/stats.py --dataset-path "$DS" --embodiment-tag NEW_EMBODIMENT --modality-config-path "$CFG"
ls -la "$DS/meta/"
echo "== 학습 시작: GPU $GPU · $STEPS 스텝 · $SAVE 마다 저장 · batch $BS → $OUT"
if [ "$NG" -gt 1 ]; then RUN=(torchrun --nproc_per_node="$NG" --master_port=29517); else RUN=(python); fi
CUDA_VISIBLE_DEVICES=$GPU nohup "${RUN[@]}" gr00t/experiment/launch_finetune.py \
  --base-model-path nvidia/GR00T-N1.7-3B \
  --dataset-path "$DS" \
  --embodiment-tag NEW_EMBODIMENT \
  --modality-config-path "$CFG" \
  --num-gpus "$NG" \
  --output-dir "$OUT" \
  --max-steps "$STEPS" --save-steps "$SAVE" --save-total-limit 5 \
  --global-batch-size "$BS" \
  --dataloader-num-workers 8 \
  > "$OUT.log" 2>&1 &
echo "pid $! · 로그: tail -f $OUT.log"
