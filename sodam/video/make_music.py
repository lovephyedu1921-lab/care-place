"""60초 배경음악(music.wav)을 합성한다.

D장조, 60BPM(1박=1초). 장면 전환 시점(4, 9, 14, 20, 32, 40, 45, 53초)에 맞춰
패드 화성, 가야금 느낌의 뜯는 현(Karplus-Strong), 파도 소리, 종소리를 배치한다.
"""
import sys
import wave

import numpy as np

SR = 44100
DUR = 60.0
N = int(SR * DUR)
rng = np.random.default_rng(3)
L = np.zeros(N)
R = np.zeros(N)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def add(sig, start, gain=1.0, pan=0.0):
    i = int(start * SR)
    if i >= N:
        return
    sig = sig[: N - i] * gain
    L[i:i + len(sig)] += sig * np.sqrt(0.5 * (1 - pan))
    R[i:i + len(sig)] += sig * np.sqrt(0.5 * (1 + pan))


def env(n, a, r, total):
    t = np.arange(n) / SR
    e = np.clip(t / a, 0, 1) * np.clip((total - t) / r, 0, 1)
    return e


# ---------- 패드 ----------
def pad(notes, start, dur, gain):
    n = int((dur + 2.0) * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for m in notes:
        f = hz(m)
        for det in (-0.0018, 0.0018):
            ff = f * (1 + det)
            ph = rng.uniform(0, 2 * np.pi)
            s += np.sin(2 * np.pi * ff * t + ph) + 0.22 * np.sin(4 * np.pi * ff * t + ph) + 0.06 * np.sin(6 * np.pi * ff * t)
    s *= env(n, 1.4, 2.0, dur + 2.0) * (1 + 0.08 * np.sin(2 * np.pi * 0.23 * t))
    s /= len(notes) * 2
    add(s, start, gain, pan=-0.15)
    add(s, start + 0.013, gain * 0.9, pan=0.25)


# ---------- 가야금 느낌 뜯는 현 ----------
def pluck(m, start, gain, length=2.6, bright=0.5, pan=0.0):
    f = hz(m)
    p = int(SR / f)
    n = int(length * SR)
    y = np.zeros(n + p + 1)
    burst = rng.uniform(-1, 1, p)
    # 밝기 조절: 초기 노이즈를 살짝 평활화
    k = max(1, int((1 - bright) * 6))
    burst = np.convolve(burst, np.ones(k) / k, mode="same")
    y[:p] = burst
    decay = 0.9965
    for b in range(1, (n + p) // p + 1):
        s0, s1 = b * p, min((b + 1) * p, n + p)
        if s0 >= n + p:
            break
        prev = y[s0 - p:s1 - p]
        prev2 = y[s0 - p - 1:s1 - p - 1] if s0 - p - 1 >= 0 else np.concatenate([[0], y[s0 - p:s1 - p - 1]])
        y[s0:s1] = decay * 0.5 * (prev + prev2)
    out = y[p:p + n]
    # 농현 느낌: 살짝 떨리는 음량
    t = np.arange(n) / SR
    out *= (1 + 0.12 * np.sin(2 * np.pi * 5.2 * t) * np.clip(t - 0.25, 0, 1)) * np.clip((length - t) / 0.4, 0, 1)
    out *= np.clip(t / 0.003, 0, 1)
    add(out / (np.abs(out).max() + 1e-9), start, gain, pan)


# ---------- 피아노 느낌 단음 ----------
def piano(m, start, gain, length=3.0, pan=0.0):
    f = hz(m)
    n = int(length * SR)
    t = np.arange(n) / SR
    s = sum(a * np.sin(2 * np.pi * f * h * t) * np.exp(-t * (1.6 + h * 0.9)) for h, a in ((1, 1), (2, .45), (3, .2), (4, .1), (5, .05)))
    s *= np.clip(t / 0.004, 0, 1) * np.clip((length - t) / 0.5, 0, 1)
    add(s, start, gain, pan)


# ---------- 종소리 ----------
def bell(m, start, gain):
    f = hz(m)
    n = int(4.5 * SR)
    t = np.arange(n) / SR
    s = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * d) for r, a, d in ((1, 1, 1.0), (2.76, .4, 1.8), (5.4, .2, 3.0), (8.93, .1, 4.5)))
    add(s * np.clip(t / 0.002, 0, 1), start, gain, 0.1)


# ---------- 베이스 ----------
def bass(m, start, dur, gain):
    f = hz(m)
    n = int((dur + 1.0) * SR)
    t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * env(n, 0.08, 1.0, dur + 1.0) * np.exp(-t * 0.25)
    add(s, start, gain)


# ---------- 파도 ----------
def waves(start, dur, gain):
    n = int(dur * SR)
    w = np.cumsum(rng.normal(0, 1, n))
    w -= np.convolve(w, np.ones(4410) / 4410, mode="same")
    w /= np.abs(w).max() + 1e-9
    t = np.arange(n) / SR
    am = 0.45 + 0.55 * np.sin(2 * np.pi * t / 4.6 - 1.2) ** 2
    w *= am * np.clip(t / 0.6, 0, 1) * np.clip((dur - t) / 2.5, 0, 1)
    add(w, start, gain, -0.3)
    add(np.roll(w, 9000), start, gain * 0.8, 0.4)


# 화성 진행 (시작초, 길이, 패드 음, 뜯는 현 음계, 베이스)
D_ = ([50, 57, 61, 64, 66], [62, 66, 69, 71, 74, 76], 38)
Bm = ([47, 54, 57, 61, 62], [59, 62, 66, 69, 71, 74], 47)
G_ = ([43, 50, 54, 59, 62], [59, 62, 64, 66, 71, 74], 43)
A_ = ([45, 52, 59, 62, 66], [64, 66, 69, 71, 74, 76], 45)
prog = [
    (0, 4, D_), (4, 5, Bm), (9, 4, G_), (13, 4, A_), (17, 4, D_), (21, 4, Bm), (25, 4, G_), (29, 3, A_),
    (32, 4, D_), (36, 4, Bm), (40, 5, G_), (45, 4, D_), (49, 2, G_), (51, 2, A_), (53, 7, D_),
]

waves(0, 7.5, 0.10)
for st, du, (pn, pl, bs) in prog:
    g = 0.09 if st < 4 else 0.06 if st < 9 else 0.075
    pad(pn, st, du, g)
    if st >= 9:
        bass(bs, st, du, 0.07)
        if st >= 45:
            bass(bs, st + du / 2, du / 2, 0.045)

# 인트로: 뜯는 현 두 음
pluck(74, 1.0, 0.18, 3.5, 0.6, 0.2)
pluck(69, 2.5, 0.14, 3.0, 0.6, -0.2)

# 통증 장면: 성긴 피아노 단음 (단조 느낌)
for st, m in ((4.2, 66), (5.7, 62), (7.2, 61), (8.2, 59)):
    piano(m, st, 0.16, 3.0, 0.1)

# 병원 등장: 종소리
bell(81, 9.0, 0.07)

patA = [0, 2, 1, 3, 2, 4, 3, 1]
patB = [0, 2, 4, 2, 1, 3, 5, 3]
for st, du, (pn, pl, bs) in prog:
    if st < 9:
        continue
    if st < 14:
        step, pat, g, br = 1.0, patA, 0.12, 0.45
    elif st < 32:
        step, pat, g, br = 1.0, patA, 0.16, 0.55
    elif st < 45:
        step, pat, g, br = 0.5, patA, 0.13, 0.55
    elif st < 53:
        step, pat, g, br = 0.5, patB, 0.16, 0.7
    else:
        continue
    k = 0
    tt = st
    while tt < st + du - 1e-6:
        if tt >= 9:
            accent = 1.25 if abs(tt - round(tt)) < 1e-6 and round(tt) % 2 == 1 else 1.0
            m = pl[pat[k % len(pat)] % len(pl)]
            pluck(m, tt + rng.uniform(0, 0.012), g * accent, 2.4, br, pan=rng.uniform(-0.4, 0.4))
            if st >= 45 and k % 4 == 0:
                pluck(m + 12, tt + 0.02, g * 0.45, 2.0, 0.7, 0.3)
        k += 1
        tt += step

# 원장 한마디 장면: 피아노 선율 살짝
for st, m in ((40.0, 74), (41.0, 71), (42.0, 69), (43.5, 66)):
    piano(m, st, 0.10, 3.0, -0.1)

# 엔딩: 하행 아르페지오 + 종
for i, m in enumerate([86, 81, 78, 76, 74, 69, 66, 62]):
    pluck(m, 53.0 + i * 0.16, 0.12, 4.5, 0.6, pan=0.5 - i * 0.12)
bell(86, 53.4, 0.06)
pad([38, 50, 57, 61, 64, 66, 69], 53, 7, 0.06)

# ---------- 리버브 ----------
def reverb(x, seed):
    r = np.random.default_rng(seed)
    n = int(2.8 * SR)
    t = np.arange(n) / SR
    ir = r.normal(0, 1, n) * np.exp(-t * 2.4)
    ir = np.convolve(ir, np.ones(6) / 6, mode="same")
    ir[0] = 0
    ir /= np.sqrt((ir ** 2).sum())
    m = 1 << int(np.ceil(np.log2(len(x) + n)))
    y = np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[: len(x)]
    return y


wetL, wetR = reverb(L, 11), reverb(R, 12)
L = L + 0.45 * wetL
R = R + 0.45 * wetR

t = np.arange(N) / SR
master = np.clip(t / 0.8, 0, 1) * np.clip((DUR - t) / 1.6, 0, 1)
L *= master
R *= master
peak = max(np.abs(L).max(), np.abs(R).max())
L, R = L / peak * 0.89, R / peak * 0.89
L, R = np.tanh(L * 1.1) / np.tanh(1.1), np.tanh(R * 1.1) / np.tanh(1.1)
L *= 0.89
R *= 0.89

data = (np.stack([L, R], axis=1) * 32767).astype(np.int16)
with wave.open(sys.argv[1] if len(sys.argv) > 1 else "music.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(data.tobytes())
