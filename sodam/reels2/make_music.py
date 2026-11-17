"""릴스 v2용 32초 배경음악 + 효과음(music.wav)을 합성한다.

120BPM(1박=0.5초), D장조. 장면 전환(whoosh), 카드 등장(tick), 로고(bell) 타이밍은
index.html의 SCENES·data-a 값과 맞춰 두었다.
"""
import sys
import wave

import numpy as np

SR = 44100
DUR = 32.0
N = int(SR * DUR)
BEAT = 0.5
rng = np.random.default_rng(5)
L = np.zeros(N)
R = np.zeros(N)
DRY_L = np.zeros(N)  # 리버브를 거치지 않는 타악기·효과음
DRY_R = np.zeros(N)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def add(sig, start, gain=1.0, pan=0.0, dry=False):
    i = int(round(start * SR))
    if i >= N or i < 0:
        return
    sig = sig[: N - i] * gain
    l, r = (DRY_L, DRY_R) if dry else (L, R)
    l[i:i + len(sig)] += sig * np.sqrt(0.5 * (1 - pan))
    r[i:i + len(sig)] += sig * np.sqrt(0.5 * (1 + pan))


def tvec(n):
    return np.arange(n) / SR


def lowpass(x, k):
    return np.convolve(x, np.ones(k) / k, mode="same")


# ---------- 악기 ----------
def pad(notes, start, dur, gain):
    n = int((dur + 1.5) * SR)
    t = tvec(n)
    s = np.zeros(n)
    for m in notes:
        for det in (-0.002, 0.002):
            f = hz(m) * (1 + det)
            ph = rng.uniform(0, 6.28)
            s += np.sin(2 * np.pi * f * t + ph) + 0.18 * np.sin(4 * np.pi * f * t + ph)
    s *= np.clip(t / 0.8, 0, 1) * np.clip((dur + 1.5 - t) / 1.5, 0, 1) / (len(notes) * 2)
    add(s, start, gain, -0.2)
    add(s, start + 0.011, gain * 0.9, 0.25)


def pluck(m, start, gain, length=1.6, bright=0.6, pan=0.0):
    f = hz(m)
    p = int(SR / f)
    n = int(length * SR)
    y = np.zeros(n + p + 1)
    k = max(1, int((1 - bright) * 6))
    y[:p] = lowpass(rng.uniform(-1, 1, p), k)
    for b in range(1, (n + p) // p + 1):
        s0, s1 = b * p, min((b + 1) * p, n + p)
        if s0 >= n + p:
            break
        prev = y[s0 - p:s1 - p]
        prev2 = y[s0 - p - 1:s1 - p - 1] if s0 - p - 1 >= 0 else np.concatenate([[0], y[s0 - p:s1 - p - 1]])
        y[s0:s1] = 0.996 * 0.5 * (prev + prev2)
    out = y[p:p + n]
    t = tvec(n)
    out *= np.clip(t / 0.002, 0, 1) * np.clip((length - t) / 0.3, 0, 1)
    add(out / (np.abs(out).max() + 1e-9), start, gain, pan)


def bass(m, start, dur, gain):
    n = int((dur + 0.3) * SR)
    t = tvec(n)
    f = hz(m)
    s = (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)) * np.clip(t / 0.01, 0, 1) * np.clip((dur + 0.3 - t) / 0.3, 0, 1)
    add(s, start, gain, dry=True)


def kick(start, gain):
    n = int(0.35 * SR)
    t = tvec(n)
    f = 45 + 85 * np.exp(-t * 30)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
    add(s, start, gain, dry=True)


def clap(start, gain):
    n = int(0.25 * SR)
    t = tvec(n)
    z = np.diff(rng.normal(0, 1, n + 1))
    e = np.zeros(n)
    for o in (0, 0.011, 0.022):
        e += np.exp(-np.clip(t - o, 0, None) * 60) * (t >= o)
    e += 0.6 * np.exp(-t * 14)
    add(z * e * 0.35, start, gain, 0.05)


def hat(start, gain, pan=0.2):
    n = int(0.06 * SR)
    t = tvec(n)
    z = np.diff(np.diff(rng.normal(0, 1, n + 2)))
    add(z * np.exp(-t * 70) * 0.25, start, gain, pan, dry=True)


def bell(m, start, gain):
    n = int(3.5 * SR)
    t = tvec(n)
    f = hz(m)
    s = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * d) for r, a, d in ((1, 1, 1.2), (2.76, .4, 2.0), (5.4, .2, 3.2), (8.93, .08, 5)))
    add(s * np.clip(t / 0.002, 0, 1), start, gain, 0.1)


def whoosh(end, gain, length=0.5):
    n = int((length + 0.25) * SR)
    t = tvec(n)
    z = rng.normal(0, 1, n)
    rise = np.clip(t / length, 0, 1) ** 2.2
    fall = np.exp(-np.clip(t - length, 0, None) * 18)
    bright = np.diff(np.concatenate([[0], z])) * rise + lowpass(z, 12) * (1 - rise)
    s = bright * rise * fall * 0.5
    add(s, end - length, gain, -0.3, dry=True)
    add(np.roll(s, 300), end - length, gain * 0.8, 0.3, dry=True)


def tick(start, gain, m=93):
    n = int(0.09 * SR)
    t = tvec(n)
    s = np.sin(2 * np.pi * hz(m) * t) * np.exp(-t * 55) + 0.3 * np.sin(2 * np.pi * hz(m + 12) * t) * np.exp(-t * 80)
    add(s, start, gain, 0.15, dry=True)


# ---------- 화성 진행 (2마디 = 4초) ----------
D_ = ([50, 57, 61, 64, 66], [62, 66, 69, 73, 74, 78], 38)
Bm = ([47, 54, 57, 61, 62], [59, 62, 66, 69, 71, 74], 35)
G_ = ([43, 50, 54, 59, 62], [62, 66, 67, 71, 74, 78], 43)
A_ = ([45, 52, 57, 61, 64], [61, 64, 69, 71, 73, 76], 45)
LOOP = [D_, Bm, G_, A_]

ARP = [0, 2, 4, 2, 1, 3, 5, 3]
for bar in range(10):
    st = bar * 4.0
    pn, pl, bs = LOOP[bar % 4] if st < 27.5 else D_
    if st >= 36:
        break
    pad(pn, st, 4.0 if st < 24 else 3.5, 0.22 if st < 7 else 0.10)
    # 뜯는 현 아르페지오
    step = 0.5 if st < 3.5 else 0.25
    k = 0
    tt = st
    while tt < st + 4.0 - 1e-6 and tt < 27.5:
        on_hook = tt < 3.5
        if not on_hook or k % 2 == 0:
            g = 0.20 if tt < 7 else 0.17
            if 24.5 <= tt < 27.5:
                g = 0.14
            pluck(pl[ARP[k % 8] % len(pl)], tt + rng.uniform(0, .006), g * (1.2 if k % 4 == 0 else 1.0), 1.4, 0.6, rng.uniform(-.4, .4))
        k += 1
        tt += step
    # 베이스: 사진 장면(7초)부터
    if 4 <= st < 27.5:
        for b in range(8):
            bt = st + b * BEAT
            if 7 <= bt < 27.5 and not (24.5 <= bt < 27.5 and b % 2):
                bass(bs, bt, 0.42, 0.085 if b % 2 == 0 else 0.055)

# 드럼
t = 0.0
while t < 27.5 - 1e-6:
    beat = round(t / BEAT)
    if t >= 3.5:
        hat(t + 0.25, 0.05 if t < 7 else 0.07, 0.25)
    if 7 <= t < 24.5 or (24.5 <= t < 27.5 and beat % 4 == 0):
        kick(t, 0.30)
    if 10.5 <= t < 24.5 and beat % 2 == 1:
        clap(t, 0.15)
    t += BEAT

# 엔딩: 하행 아르페지오 + 긴 화음
for i, m in enumerate([86, 81, 78, 74, 69, 66, 62]):
    pluck(m, 27.5 + i * 0.12, 0.17, 3.0, 0.65, 0.4 - i * 0.12)
pad([38, 50, 57, 62, 64, 66, 69], 27.5, 4.0, 0.09)
bass(38, 27.5, 2.0, 0.08)
kick(27.5, 0.28)

# 효과음 (index.html 타이밍과 맞춤)
for s_ in (3.5, 7, 10.5, 14, 17.5, 21, 24.5):
    whoosh(s_, 0.11)
whoosh(27.5, 0.15, 0.7)
chips = [10.5 + 1.1, 10.5 + 1.25, 10.5 + 1.4, 14 + 1.1, 14 + 1.25, 17.5 + 1.15, 17.5 + 1.3, 21 + 1.1, 21 + 1.25, 21 + 1.4, 27.5 + 1.4]
for i, s_ in enumerate(chips):
    tick(s_, 0.09, 93 + (i % 3) * 3)
bell(81, 3.5 + 0.5, 0.08)
bell(86, 27.5 + 0.4, 0.07)


# ---------- 리버브 + 마스터 ----------
def reverb(x, seed):
    r = np.random.default_rng(seed)
    n = int(2.0 * SR)
    tt = tvec(n)
    ir = lowpass(r.normal(0, 1, n) * np.exp(-tt * 3.2), 5)
    ir[0] = 0
    ir /= np.sqrt((ir ** 2).sum())
    m = 1 << int(np.ceil(np.log2(len(x) + n)))
    return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[: len(x)]


L = L + 0.35 * reverb(L, 21) + DRY_L
R = R + 0.35 * reverb(R, 22) + DRY_R
tt = tvec(N)
master = np.clip(tt / 0.15, 0, 1) * np.clip((DUR - tt) / 1.5, 0, 1)
L *= master
R *= master
peak = max(np.abs(L).max(), np.abs(R).max())
L, R = np.tanh(L / peak * 1.2) / np.tanh(1.2) * 0.89, np.tanh(R / peak * 1.2) / np.tanh(1.2) * 0.89

data = (np.stack([L, R], axis=1) * 32767).astype(np.int16)
with wave.open(sys.argv[1] if len(sys.argv) > 1 else "music.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(data.tobytes())
