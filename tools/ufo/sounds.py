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


def hover_tone(dur, f0, harmonics=(1.0, 0.45, 0.22, 0.12, 0.07), wobble=1.0, noise=0.06, seed=0):
    """Steady hover hum: detuned harmonic stack + slow wobble + airy noise."""
    t = _t(dur)
    out = np.zeros_like(t)
    rng = np.random.default_rng(seed)
    for i, amp in enumerate(harmonics):
        ratio = 1.0 + i * 0.0035 * (1 if i % 2 == 0 else -1)     # slight detune
        f = _quantise(f0 * (i + 1) * ratio, dur)
        phase = rng.random() * 2 * np.pi
        out += amp * np.sin(2 * np.pi * f * t + phase)
    # slow amplitude / pitch wobble, periodic in the loop
    lfo_f = _quantise(4.6 * wobble, dur)
    lfo = np.sin(2 * np.pi * lfo_f * t)
    out *= 1.0 + 0.12 * lfo
    # airy band-limited noise (smoothed white noise), periodic by mirroring
    if noise > 0:
        w = rng.normal(size=len(t))
        k = 41
        kernel = np.hanning(k)
        kernel /= kernel.sum()
        w = np.convolve(np.concatenate([w, w[:k]]), kernel, mode="same")[:len(t)]
        w /= max(np.abs(w).max(), 1e-9)
        out += noise * w * (1.0 + 0.3 * lfo)
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


def greeting(dur=0.62, seed=2):
    """Cute two-tone 'bii-buup' - the honk."""
    t = _t(dur)
    out = np.zeros_like(t)
    rng = np.random.default_rng(seed)
    notes = [(0.0, 0.22, 620.0, 900.0), (0.24, 0.38, 980.0, 640.0)]
    for start, length, f0, f1 in notes:
        i0 = int(start * FS)
        i1 = min(len(t), i0 + int(length * FS))
        tt = np.arange(i1 - i0) / FS
        f = f0 + (f1 - f0) * (tt / max(tt[-1], 1e-6))
        # vibrato makes it sound "alien"
        f = f * (1.0 + 0.05 * np.sin(2 * np.pi * 7.0 * tt))
        ph = 2 * np.pi * np.cumsum(f) / FS
        env = np.minimum(1.0, tt / 0.02) * np.minimum(1.0, (tt[-1] - tt) / 0.06)
        out[i0:i1] += env * (np.sin(ph) + 0.3 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph))
    out /= max(np.abs(out).max(), 1e-9)
    return out * 0.7


SOUNDS = {
    # name: (generator, kind, meta)
    "hoverIdle": (lambda: hover_tone(3.0, 42.0, wobble=0.6, seed=11), "loop",
                  {"native_rpm": 800, "load": 0}),
    "hoverMid": (lambda: hover_tone(2.5, 68.0, wobble=1.0, seed=12), "loop",
                 {"native_rpm": 1600, "load": 0}),
    "hoverHigh": (lambda: hover_tone(2.0, 96.0, wobble=1.4, seed=13), "loop",
                  {"native_rpm": 2400, "load": 0}),
    "hoverLoad": (lambda: hover_tone(2.0, 84.0, harmonics=(1.0, 0.55, 0.3, 0.2, 0.12),
                                     wobble=1.2, noise=0.10, seed=14), "loop",
                  {"native_rpm": 2000, "load": 1}),
    "hoverStart": (lambda: sweep(1.35, 150.0, 780.0, True, seed=21), "once",
                   {"duration": 1.35}),
    "hoverStop": (lambda: sweep(1.1, 760.0, 120.0, False, seed=22), "once",
                  {"duration": 1.1}),
    "greeting": (greeting, "once", {"duration": 0.62}),
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
