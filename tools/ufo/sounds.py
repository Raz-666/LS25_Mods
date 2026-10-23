# SPDX-License-Identifier: GPL-3.0-or-later
"""Procedural sound set for the UFO 2000 (FS25 ogg samples).

Everything is synthesised with numpy: a wobbly theremin-like hover hum with
three rpm bands, start/stop sweeps and a cute two-tone greeting horn.  Loops
are built so that every partial and every LFO completes an integer number of
cycles inside the loop, i.e. they repeat sample-exactly.
"""

import json
import os

import numpy as np
import soundfile as sf

FS = 44100


def _quantise(freq, dur):
    """Snap a frequency so it completes whole cycles in `dur` seconds."""
    if freq <= 0:
        return 0.0
    return max(1.0, round(freq * dur)) / dur


def _t(dur):
    return np.arange(int(round(dur * FS))) / FS


def hover_tone(dur, f0, harmonics=(1.0, 0.30, 0.12), wobble=1.0, noise=0.035, seed=0,
               bubbles=5, bubble_gain=0.35):
    """Cute hovering hum: soft wub-wub with a slow pitch wobble and little
    bubbles popping out of it (Simpsons / Futurama flying saucer vibes)."""
    t = _t(dur)
    rng = np.random.default_rng(seed)

    # two wobble rates, both snapped to whole cycles so the loop is seamless
    lfo1 = np.sin(2 * np.pi * _quantise(5.1 * wobble, dur) * t)
    lfo2 = np.sin(2 * np.pi * _quantise(11.7 * wobble, dur) * t + 0.7)
    pitch_mod = 0.055 * lfo1 + 0.018 * lfo2
    ph = 2 * np.pi * np.cumsum(f0 * (1.0 + pitch_mod)) / FS

    out = np.zeros_like(t)
    for i, amp in enumerate(harmonics):
        out += amp * np.sin((i + 1) * ph + rng.random() * 0.6)
    out *= 1.0 + 0.10 * lfo1

    # bubbles: short rising blips, evenly spread and loop-safe
    if 0 < bubbles:
        blip_len = min(0.09, dur / bubbles * 0.7)
        for i in range(bubbles):
            start = dur * (i + 0.5) / bubbles
            i0 = int(start * FS)
            n = int(blip_len * FS)
            if i0 + n >= len(t):
                continue
            tt = np.arange(n) / FS
            f = f0 * (2.1 + 0.6 * i % 3) * (1.0 + 2.4 * tt / blip_len)
            env = np.sin(np.pi * tt / blip_len) ** 2
            out[i0:i0 + n] += bubble_gain * env * np.sin(2 * np.pi * np.cumsum(f) / FS)

    # a little air, band limited
    if 0 < noise:
        w = rng.normal(size=len(t))
        k = 61
        kernel = np.hanning(k)
        kernel /= kernel.sum()
        w = np.convolve(np.concatenate([w, w[:k]]), kernel, mode="same")[:len(t)]
        w /= max(np.abs(w).max(), 1e-9)
        out += noise * w * (1.0 + 0.3 * lfo1)

    out /= max(np.abs(out).max(), 1e-9)
    return out * 0.72


def sweep(dur, f_start, f_end, rise=True, seed=1, tail_tone=None, tail_level=0.7):
    """Start / stop whoosh: exponential glide + noise riser (+ optional steady tail)."""
    t = _t(dur)
    rng = np.random.default_rng(seed)
    # exponential glide, integrated phase
    f = f_start * (f_end / f_start) ** (t / dur)
    ph = 2 * np.pi * np.cumsum(f) / FS
    body = (np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.18 * np.sin(3 * ph))
    body *= np.linspace(0.15, 1.0, len(t)) if rise else np.linspace(1.0, 0.05, len(t))
    # noise riser / faller
    w = rng.normal(size=len(t))
    k = 25
    kernel = np.hanning(k)
    kernel /= kernel.sum()
    w = np.convolve(w, kernel, mode="same")
    env = (np.linspace(0, 1, len(t)) ** 2) if rise else (np.linspace(1, 0, len(t)) ** 2)
    out = body + 0.55 * w / max(np.abs(w).max(), 1e-9) * env
    out /= max(np.abs(out).max(), 1e-9)
    out *= 0.8
    # fade so the sample starts / ends cleanly
    fade = int(0.012 * FS)
    out[:fade] *= np.linspace(0, 1, fade) ** 1.5
    out[-fade:] *= np.linspace(1, 0, fade) ** 1.5
    return out


def greeting(dur=0.85, seed=2):
    """Happy little alien jingle - the honk: bi-bu-ba-doo with vibrato."""
    t = _t(dur)
    out = np.zeros_like(t)
    rng = np.random.default_rng(seed)
    # (start, length, f0, f1) - a rising, bubbly four note phrase
    notes = [(0.00, 0.14, 700.0, 980.0),
             (0.16, 0.12, 980.0, 1180.0),
             (0.30, 0.16, 880.0, 1320.0),
             (0.50, 0.30, 1320.0, 760.0)]
    for start, length, f0, f1 in notes:
        i0 = int(start * FS)
        i1 = min(len(t), i0 + int(length * FS))
        tt = np.arange(i1 - i0) / FS
        f = f0 + (f1 - f0) * (tt / max(tt[-1], 1e-6))
        # fast cartoon vibrato
        f = f * (1.0 + 0.07 * np.sin(2 * np.pi * 13.0 * tt))
        ph = 2 * np.pi * np.cumsum(f) / FS
        env = np.minimum(1.0, tt / 0.012) * np.minimum(1.0, (tt[-1] - tt) / 0.05)
        out[i0:i1] += env * (np.sin(ph) + 0.22 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph))
    out /= max(np.abs(out).max(), 1e-9)
    return out * 0.65


def mode_beep(dur=0.42, seed=31):
    """Two soft round blips when the pilot turns the mode dial."""
    t = _t(dur)
    out = np.zeros_like(t)
    for start, length, f0, f1 in ((0.00, 0.11, 620.0, 880.0), (0.16, 0.18, 980.0, 1240.0)):
        i0 = int(start * FS)
        i1 = min(len(t), i0 + int(length * FS))
        tt = np.arange(i1 - i0) / FS
        f = f0 + (f1 - f0) * (tt / max(tt[-1], 1e-6))
        ph = 2 * np.pi * np.cumsum(f) / FS
        env = np.minimum(1.0, tt / 0.010) * np.minimum(1.0, (tt[-1] - tt) / 0.045)
        out[i0:i1] += env * (np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.10 * np.sin(3 * ph))
    out /= max(np.abs(out).max(), 1e-9)
    return out * 0.55


def beam_hum(dur=2.0, seed=32):
    """Looping working hum under the beam: bubbling energy with a soft grind."""
    t = _t(dur)
    rng = np.random.default_rng(seed)
    ph = 2 * np.pi * np.cumsum(_quantise(118.0, dur) * (1.0 + 0.03 * np.sin(
        2 * np.pi * _quantise(3.4, dur) * t))) / FS
    out = np.sin(ph) + 0.32 * np.sin(2 * ph) + 0.14 * np.sin(3 * ph)
    out *= 0.75 + 0.25 * np.sin(2 * np.pi * _quantise(7.7, dur) * t)
    # grainy sparkling layer, band limited so it loops cleanly
    w = rng.normal(size=len(t))
    k = 9
    kernel = np.hanning(k)
    kernel /= kernel.sum()
    w = np.convolve(w, kernel, mode="same")
    out += 0.22 * w / max(np.abs(w).max(), 1e-9)
    out /= max(np.abs(out).max(), 1e-9)
    return out * 0.7


def suction_hum(dur=2.0, seed=33, rising=True):
    """Looping hiss for the suction / pouring beam."""
    t = _t(dur)
    rng = np.random.default_rng(seed)
    w = rng.normal(size=len(t))
    k = 7
    kernel = np.hanning(k)
    kernel /= kernel.sum()
    w = np.convolve(w, kernel, mode="same")
    w /= max(np.abs(w).max(), 1e-9)
    tone = np.sin(2 * np.pi * _quantise(240.0 if rising else 180.0, dur) * t)
    swirl = 0.5 + 0.5 * np.sin(2 * np.pi * _quantise(4.3, dur) * t)
    out = 0.55 * w * swirl + 0.30 * tone * (0.4 + 0.6 * swirl)
    out /= max(np.abs(out).max(), 1e-9)
    return out * 0.65


SOUNDS = {
    # name: (generator, kind, meta)
    "hoverIdle": (lambda: hover_tone(3.0, 96.0, wobble=0.45, seed=11, bubbles=4), "loop",
                  {"native_rpm": 800, "load": 0}),
    "hoverMid": (lambda: hover_tone(2.5, 132.0, wobble=0.8, seed=12, bubbles=5), "loop",
                 {"native_rpm": 1600, "load": 0}),
    "hoverHigh": (lambda: hover_tone(2.0, 176.0, wobble=1.1, seed=13, bubbles=6), "loop",
                  {"native_rpm": 2400, "load": 0}),
    "hoverLoad": (lambda: hover_tone(2.0, 150.0, harmonics=(1.0, 0.42, 0.2, 0.1),
                                     wobble=1.0, noise=0.09, seed=14, bubbles=3,
                                     bubble_gain=0.22), "loop",
                  {"native_rpm": 2000, "load": 1}),
    "hoverStart": (lambda: sweep(1.35, 150.0, 780.0, True, seed=21), "once",
                   {"duration": 1.35}),
    "hoverStop": (lambda: sweep(1.1, 760.0, 120.0, False, seed=22), "once",
                  {"duration": 1.1}),
    "greeting": (greeting, "once", {"duration": 0.85}),
    # v7: one beep per mode change plus a loop for every working beam
    "modeSwitch": (mode_beep, "once", {"duration": 0.42}),
    "beamLoop": (beam_hum, "loop", {}),
    "loadLoop": (lambda: suction_hum(2.0, seed=33, rising=True), "loop", {}),
    "unloadLoop": (lambda: suction_hum(2.0, seed=34, rising=False), "loop", {}),
}


def _to_ogg(path, mono):
    # gentle limiter + tiny fade to avoid clicks in the engine's mixer
    peak = np.abs(mono).max()
    if peak > 0.98:
        mono = mono / peak * 0.98
    data = np.stack([mono, mono], axis=1).astype(np.float32)
    sf.write(path, data, FS, format="OGG", subtype="VORBIS")


def generate(out_dir, demo_path=None):
    os.makedirs(out_dir, exist_ok=True)
    meta = {"sample_rate": FS, "files": {}}
    rendered = {}
    for name, (fn, kind, info) in SOUNDS.items():
        y = fn()
        rendered[name] = y
        path = os.path.join(out_dir, name + ".ogg")
        _to_ogg(path, y)
        entry = {"type": kind, "file": name + ".ogg", "duration_s": round(len(y) / FS, 4),
                 "peak_dbfs": round(float(20 * np.log10(max(np.abs(y).max(), 1e-9))), 2)}
        entry.update(info)
        meta["files"][name] = entry
        print("  %-14s %-5s %5.2fs %6.1f kB" % (name + ".ogg", kind, len(y) / FS,
                                                os.path.getsize(path) / 1024.0))
    with open(os.path.join(out_dir, "sounds.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
        fh.write("\n")
    if demo_path:
        parts = [rendered["hoverStart"], rendered["hoverIdle"], rendered["hoverMid"],
                 rendered["hoverHigh"], rendered["greeting"], rendered["hoverStop"]]
        demo = np.concatenate(parts)
        _to_ogg(demo_path, demo)
        print("  demo ->", demo_path)
    return meta


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(here))
    generate(os.path.join(repo, "FS25_UFO2000", "sounds"),
             os.path.join(repo, "docs", "sound_demo.ogg"))
