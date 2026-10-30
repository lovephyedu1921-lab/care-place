#!/usr/bin/env bash
# 소담한방병원 릴스 v2 빌드: 프레임 렌더(Playwright) → 음악 합성 → mp4
set -euo pipefail
cd "$(dirname "$0")"
WORK="${WORK:-$(mktemp -d)}"
mkdir -p out
node render.cjs "$WORK/frames" 30
python3 make_music.py "$WORK/music.wav"
ffmpeg -y -loglevel error -framerate 30 -i "$WORK/frames/f%05d.jpg" -i "$WORK/music.wav" \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11" -c:a aac -b:a 192k -ar 48000 -shortest \
  out/sodam-reels-v2.mp4
echo "완료: out/sodam-reels-v2.mp4"
