#!/usr/bin/env bash
# 소담한방병원 홍보영상 시안 빌드: 한지 텍스처 → 프레임 렌더 → 음악 합성 → mp4 합치기
set -euo pipefail
cd "$(dirname "$0")"
WORK="${WORK:-$(mktemp -d)}"
mkdir -p out

[ -f hanji.png ] || python3 make_hanji.py hanji.png
node render.cjs "$WORK/frames" 30
python3 make_music.py "$WORK/music.wav"

ffmpeg -y -loglevel error -framerate 30 -i "$WORK/frames/f%05d.jpg" -i "$WORK/music.wav" \
  -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p -movflags +faststart \
  -af "loudnorm=I=-16:TP=-1.5:LRA=11" -c:a aac -b:a 192k -ar 48000 -shortest \
  out/sodam-promo-60s-draft.mp4
echo "완료: out/sodam-promo-60s-draft.mp4"
