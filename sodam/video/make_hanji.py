"""한지 질감 텍스처(hanji.png)를 생성한다. 영상 배경에 multiply로 겹쳐 쓴다."""
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1920, 1080
rng = np.random.default_rng(7)

# 기본 종이 결: 저주파 + 고주파 노이즈
base = np.full((H, W), 236.0)
for scale, amp in ((240, 6), (60, 4), (12, 3), (3, 4)):
    small = rng.normal(0, 1, (H // scale + 2, W // scale + 2))
    img = Image.fromarray(((small - small.min()) / (np.ptp(small) + 1e-9) * 255).astype(np.uint8))
    img = img.resize((W, H), Image.BICUBIC)
    base += (np.asarray(img, dtype=float) / 255 - 0.5) * 2 * amp

paper = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert("RGB")

# 닥나무 섬유: 가늘고 긴 곡선
fibers = Image.new("L", (W, H), 0)
d = ImageDraw.Draw(fibers)
for _ in range(1400):
    x, y = rng.uniform(0, W), rng.uniform(0, H)
    ang = rng.uniform(0, np.pi)
    pts = []
    for _ in range(int(rng.integers(4, 9))):
        pts.append((x, y))
        ang += rng.normal(0, 0.35)
        step = rng.uniform(6, 22)
        x += np.cos(ang) * step
        y += np.sin(ang) * step
    d.line(pts, fill=int(rng.integers(18, 55)), width=1)
fibers = fibers.filter(ImageFilter.GaussianBlur(0.6))

paper_arr = np.asarray(paper, dtype=float)
fib = np.asarray(fibers, dtype=float)[..., None] / 255
paper_arr = paper_arr * (1 - fib * 0.35)
# 살짝 따뜻한 톤
paper_arr *= np.array([1.0, 0.985, 0.95])
Image.fromarray(np.clip(paper_arr, 0, 255).astype(np.uint8)).save(sys.argv[1] if len(sys.argv) > 1 else "hanji.png")
