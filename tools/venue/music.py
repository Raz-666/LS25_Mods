# SPDX-License-Identifier: GPL-3.0-or-later
"""Tiny music synthesizer for the venue mods (Autokino music, Disco tracks).

Everything is built from sine / saw / square partials and noise, so the mods
ship with their own royalty free soundtrack and nobody has to hunt for files.

A "track" is a dict with a bpm, a chord progression and a drum/bass pattern; the
generator renders it to a stereo numpy array which is then written as OGG.
"""

import os

import numpy as np

FS = 44100


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def t_axis(dur):
    return np.arange(int(round(dur * FS))) / FS


NOTE_BASE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6,
             "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def freq(name):
    """'A4' -> 440.0, 'C#3' -> 138.59"""
    name = name.strip()
    octave = int(name[-1])
    semi = NOTE_BASE[name[:-1]]
    return 440.0 * 2.0 ** ((octave - 4) + (semi - 9) / 12.0)


def _saw(ph, n=8):
    out = np.zeros_like(ph)
    for k in range(1, n + 1):
        out += np.sin(k * ph) / k
    return out * (2.0 / np.pi)


def _square(ph, n=6):
    out = np.zeros_like(ph)
    for k in range(1, n * 2, 2):
        out += np.sin(k * ph) / k
    return out * (4.0 / np.pi)


def _tone(f, dur, kind="saw", detune=0.0):
    t = t_axis(dur)
    ph = 2 * np.pi * f * t
    if detune:
        ph2 = 2 * np.pi * f * (1 + detune) * t
        base = (_saw(ph) + _saw(ph2)) * 0.5
    elif kind == "saw":
        base = _saw(ph)
    elif kind == "square":
        base = _square(ph)
    elif kind == "sine":
        base = np.sin(ph)
    elif kind == "tri":
        base = 2.0 / np.pi * np.arcsin(np.sin(ph))
    else:
        base = np.sin(ph)
    return base


def env(dur, attack=0.005, decay=0.06, sustain=0.6, release=0.12):
    t = t_axis(dur)
    a = max(1, int(attack * FS))
    d = max(1, int(decay * FS))
    r = max(1, int(release * FS))
    e = np.ones_like(t) * sustain
    e[:a] = np.linspace(0, 1, a)
    if a + d < len(e):
        e[a:a + d] = np.linspace(1, sustain, d)
    if r < len(e):
        e[-r:] *= np.linspace(1, 0, r)
    return e


def noise(dur, seed=0, smooth=1):
    n = np.random.default_rng(seed).normal(size=int(round(dur * FS)))
    if smooth > 1:
        k = np.hanning(max(3, smooth))
        k = k / max(k.sum(), 1e-9)
        n = np.convolve(n, k, mode="same")
    return n / max(np.abs(n).max(), 1e-9)


# --------------------------------------------------------------------------
# instruments
# --------------------------------------------------------------------------
def kick(dur=0.30, f0=120.0, f1=44.0, click=0.5, seed=0):
    t = t_axis(dur)
    f = f1 + (f0 - f1) * np.exp(-t * 32.0)
    ph = 2 * np.pi * np.cumsum(f) / FS
    body = np.sin(ph) * np.exp(-t * 9.0)
    body += 0.35 * np.sin(2 * ph) * np.exp(-t * 22.0)
    if click:
        body += click * noise(dur, seed) * np.exp(-t * 90.0) * 0.4
    return body / max(np.abs(body).max(), 1e-9)


def snare(dur=0.22, seed=1):
    t = t_axis(dur)
    n = noise(dur, seed, smooth=2)
    body = n * np.exp(-t * 26.0)
    body += 0.5 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 34.0)
    return body / max(np.abs(body).max(), 1e-9)


def hat(dur=0.06, seed=2, open_=False):
    t = t_axis(dur if not open_ else dur * 4)
    n = noise(len(t) / FS, seed, smooth=2)
    # cheap high pass: difference of smoothed noise
    n = np.diff(np.concatenate([[0.0], n]))
    body = n * np.exp(-t * (40.0 if not open_ else 12.0))
    return body / max(np.abs(body).max(), 1e-9)


def clap(dur=0.20, seed=3):
    t = t_axis(dur)
    out = np.zeros_like(t)
    for k, off in enumerate((0.0, 0.011, 0.021, 0.033)):
        i = int(off * FS)
        seg = slice(i, min(len(t), i + int(0.035 * FS)))
        tt = np.arange(seg.stop - seg.start) / FS
        out[seg] += noise(seg.stop / FS, seed + k, smooth=2)[seg] * np.exp(-tt * 90.0)
    out += 0.4 * noise(dur, seed + 9, smooth=2) * np.exp(-t * 18.0)
    return out / max(np.abs(out).max(), 1e-9)


def bass_note(f, dur, kind="saw", bright=0.5):
    x = _tone(f, dur, kind)
    x *= env(dur, 0.004, 0.08, 0.7, 0.05)
    x += 0.25 * np.sin(2 * np.pi * f * 0.5 * t_axis(dur))
    return x * (0.6 + bright)


def pluck(f, dur, kind="saw", bright=1.0):
    x = _tone(f, dur, kind)
    x *= env(dur, 0.003, 0.10, 0.25, 0.08)
    return x * bright


def pad_chord(freqs, dur, gain=0.25):
    out = np.zeros(int(round(dur * FS)))
    for f in freqs:
        x = _tone(f, dur, "tri") * 0.6 + _tone(f, dur, "saw") * 0.4
        out += x
    out /= max(len(freqs), 1)
    out *= env(dur, 0.25, 0.2, 0.85, 0.35)
    return out * gain


# --------------------------------------------------------------------------
# arrangement
# --------------------------------------------------------------------------
class Song:
    """A little step sequencer: 16th steps, tracks rendered sample-accurately."""

    def __init__(self, bpm=120.0, bars=8, seed=0):
        self.bpm = float(bpm)
        self.step = 60.0 / self.bpm / 4.0
        self.bars = bars
        self.steps = bars * 16
        self.length = self.steps * self.step
        self.buf = np.zeros((int(round(self.length * FS)) + FS, 2))
        self.seed = seed

    def add(self, sig, at_step, gain=1.0, pan=0.0):
        i = int(round(at_step * self.step * FS))
        if i < 0:
            sig = sig[-i:]
            i = 0
        j = min(len(self.buf), i + len(sig))
        n = j - i
        if n <= 0:
            return
        left = gain * (1.0 - max(pan, 0.0) * 0.6)
        right = gain * (1.0 + min(pan, 0.0) * 0.6)
        self.buf[i:j, 0] += sig[:n] * left
        self.buf[i:j, 1] += sig[:n] * right

    def render(self, fade=0.25):
        out = self.buf[:int(round(self.length * FS))]
        # soft knee limiter, then normalise
        peak = np.abs(out).max()
        if peak > 1e-6:
            out = out / peak
            out = np.tanh(out * 1.25) / np.tanh(1.25)
        f = int(fade * FS)
        if f > 0:
            out[:f] *= np.linspace(0, 1, f)[:, None]
            out[-f:] *= np.linspace(1, 0, f)[:, None]
        return out * 0.92


def _prog(root, degrees):
    """Turn ('C', 'm') + [0, 5, 7] style offsets into note names."""
    out = []
    names = list(NOTE_BASE)
    for d in degrees:
        idx = NOTE_BASE[root[0]] + d
        octave = root[1] + idx // 12
        out.append(names[idx % 12] + str(octave))
    return out


def make_track(kind="disco", bars=8, seed=0):
    """One of the stock tunes. Everything is deterministic (same seed)."""
    if kind == "disco":
        s = Song(118, bars, seed)
        chords = [["C3", "E3", "G3", "B3"], ["A2", "C3", "E3", "G3"],
                  ["F2", "A2", "C3", "E3"], ["G2", "B2", "D3", "F3"]]
        bass = [[36, 36, 43, 36], [33, 33, 40, 33], [29, 29, 36, 29], [31, 31, 38, 31]]
        for bar in range(bars):
            c = chords[bar % 4]
            b = bass[bar % 4]
            for k in range(4):                      # four on the floor
                s.add(kick(), bar * 16 + k * 4, 0.95)
            for k in (1, 3):                        # back beat
                s.add(snare(seed=seed + k), bar * 16 + k * 4 + 2, 0.45, 0.05)
            for k in range(8):
                s.add(hat(open_=(k % 4 == 3), seed=seed + k), bar * 16 + k * 2, 0.20, -0.25)
            for k, semis in enumerate(b):
                f = 440.0 * 2 ** ((semis - 69) / 12.0)
                s.add(bass_note(f, s.step * 3.4), bar * 16 + k * 4, 0.42)
            s.add(pad_chord([freq(n) for n in c], s.step * 6.0, 0.16), bar * 16 + 2, 0.9)
    elif kind == "techno":
        s = Song(132, bars, seed)
        chords = [["A2", "C3", "E3"], ["F2", "A2", "C3"],
                  ["D3", "F3", "A3"], ["E3", "G3", "B3"]]
        for bar in range(bars):
            c = chords[bar % 4]
            for k in range(4):
                s.add(kick(f0=140, f1=48), bar * 16 + k * 4, 0.95)
            for k in range(16):
                if k % 4 == 2:
                    s.add(hat(seed=seed + k), bar * 16 + k, 0.16, 0.3)
                elif k % 2 == 0:
                    s.add(hat(dur=0.03, seed=seed + k), bar * 16 + k, 0.09, -0.3)
            for k, semis in enumerate((33, 33, 33, 33, 36, 36, 31, 31)):
                f = 440.0 * 2 ** ((semis - 69) / 12.0)
                s.add(bass_note(f, s.step * 1.6, "square", 0.9),
                      bar * 16 + k * 2, 0.36)
            # bleepy arpeggio in the second half
            if bar >= bars // 2:
                for k in range(8):
                    n = c[k % len(c)]
                    f = freq(n) * 2
                    s.add(pluck(f, s.step * 1.2, "square"), bar * 16 + k * 2, 0.16,
                          0.35 if k % 2 else -0.35)
            s.add(pad_chord([freq(n) for n in c], s.step * 8.0, 0.10),
                  bar * 16, 0.6)
    elif kind in CLUB_TRACKS:
        return club_track(kind, bars=bars, seed=seed)
    elif kind == "chill":
        s = Song(92, bars, seed)
        chords = [["F2", "A2", "C3", "E3"], ["C3", "E3", "G3", "B3"],
                  ["D3", "F3", "A3", "C4"], ["G2", "B2", "D3", "F3"]]
        for bar in range(bars):
            c = chords[bar % 4]
            s.add(kick(f0=100, f1=42, click=0.2), bar * 16, 0.7)
            s.add(kick(f0=100, f1=42, click=0.2), bar * 16 + 10, 0.55)
            s.add(snare(seed=seed + bar), bar * 16 + 8, 0.28)
            for k in range(4):
                s.add(hat(seed=seed + k), bar * 16 + k * 4 + 1, 0.10, -0.4)
            s.add(pad_chord([freq(n) for n in c], s.step * 14.0, 0.30), bar * 16, 0.0)
            for k in (0, 6, 10):                    # lazy arpeggio
                f = freq(c[(k // 4) % len(c)]) * 2
                s.add(pluck(f, s.step * 2.4, "tri"), bar * 16 + k, 0.24,
                      0.3 if k % 3 else -0.3)
            f = freq(c[0]) / 2
            s.add(bass_note(f, s.step * 6.0, "sine", 0.2), bar * 16, 0.35)
            s.add(bass_note(f, s.step * 4.0, "sine", 0.2), bar * 16 + 8, 0.28)
    elif kind == "country":
        s = Song(104, bars, seed)
        chords = [["G2", "B2", "D3"], ["C3", "E3", "G3"],
                  ["D3", "F#3", "A3"], ["G2", "B2", "D3"]]
        for bar in range(bars):
            c = chords[bar % 4]
            for k in (0, 8):
                s.add(kick(f0=95, f1=58, click=0.15), bar * 16 + k, 0.55)
            for k in (4, 12):
                s.add(snare(seed=seed + k), bar * 16 + k, 0.30)
            for k in range(8):
                s.add(hat(dur=0.04, seed=seed + k), bar * 16 + k * 2, 0.10, 0.2)
            # boom-chick bass + strummed chords
            f0 = freq(c[0])
            for k in (0, 6, 8, 14):
                s.add(bass_note(f0, s.step * 2.5, "tri", 0.3), bar * 16 + k, 0.40)
            for k in (2, 10):
                for j, n in enumerate(c):
                    s.add(pluck(freq(n), s.step * 3.0, "saw", 0.8),
                          bar * 16 + k, 0.16, -0.2 + 0.2 * j)
            # simple melody on the high strings
            melody = [c[2], c[1], c[0], c[1]]
            s.add(pluck(freq(melody[bar % 4]) * 2, s.step * 4.0, "sine"),
                  bar * 16 + 6, 0.22, 0.4)
    elif kind == "spooky":
        s = Song(88, bars, seed)
        chords = [["A2", "C3", "E3"], ["F2", "A2", "C3"],
                  ["D3", "F3", "A3"], ["E3", "G#3", "B3"]]
        for bar in range(bars):
            c = chords[bar % 4]
            s.add(pad_chord([freq(n) for n in c], s.step * 15.0, 0.32), bar * 16, 0.0)
            s.add(kick(f0=80, f1=38, click=0.0, dur=0.6), bar * 16, 0.5)
            for k in (3, 11):
                s.add(clap(seed=seed + k), bar * 16 + k, 0.22, 0.4)
            f = freq(c[0]) / 2
            s.add(bass_note(f, s.step * 5.0, "sine", 0.1), bar * 16 + 6, 0.35)
            # music box melody
            for k, semis in enumerate((12, 15, 19, 15, 12, 8)):
                if (bar + k) % 5 == 0:
                    continue
                s.add(pluck(freq(c[0]) * 2 ** (semis / 12.0), s.step * 2.2, "tri"),
                      bar * 16 + 4 + k * 2, 0.14, -0.3 + 0.12 * k)
    elif kind == "western":
        s = Song(96, bars, seed)
        chords = [["D3", "F#3", "A3"], ["G3", "B3", "D4"],
                  ["A3", "C#4", "E4"], ["D3", "F#3", "A3"]]
        for bar in range(bars):
            c = chords[bar % 4]
            for k in (0, 6, 8):
                s.add(kick(f0=90, f1=55, click=0.1), bar * 16 + k, 0.45)
            for k in (4, 12):
                s.add(snare(seed=seed + k), bar * 16 + k, 0.26)
            for k in (2, 10, 14):
                s.add(hat(dur=0.05, seed=seed + k), bar * 16 + k, 0.10, -0.3)
            for k in (0, 4, 8, 12):
                s.add(pluck(freq(c[k // 4 % len(c)]), s.step * 3.0, "saw", 0.7),
                      bar * 16 + k, 0.18, 0.3)
            s.add(bass_note(freq(c[0]) / 2, s.step * 8.0, "tri", 0.3), bar * 16, 0.35)
            # whistled tune
            for k, semis in enumerate((7, 9, 7, 4, 2)):
                s.add(pluck(freq(c[0]) * 2 ** (semis / 12.0), s.step * 2.0, "sine"),
                      bar * 16 + 4 + k * 2, 0.20, 0.0)
    else:
        raise ValueError(kind)
    return s.render()


# --------------------------------------------------------------------------
# club tracks for FS25_Distillery
# --------------------------------------------------------------------------
CLUB_TRACKS = {
    # kind:      (bpm,  chords,                                feel)
    "anthem":     (132, [["A2", "C3", "E3", "A3"], ["F2", "A2", "C3", "F3"],
                         ["G2", "B2", "D3", "G3"], ["E3", "G#3", "B3", "E4"]]),
    "afterdark":  (126, [["D3", "F3", "A3"], ["A2", "C3", "E3"],
                         ["B2", "D3", "F3"], ["G2", "A#2", "D3"]]),
    "kohle":      (138, [["E2", "G2", "B2"], ["C3", "E3", "G3"],
                         ["D3", "F3", "A3"], ["B2", "D3", "F#3"]]),
    "rohrwerk":   (124, [["A2", "E3"], ["F2", "C3"], ["G2", "D3"], ["A2", "E3"]]),
    "untergrund": (140, [["C3", "D#3", "G3"], ["G#2", "C3", "D#3"],
                         ["A#2", "D3", "F3"], ["G2", "A#2", "D3"]]),
    "letzteRunde": (118, [["F2", "A2", "C3", "E3"], ["D3", "F3", "A3", "C4"],
                         ["A#2", "D3", "F3", "A3"], ["C3", "E3", "G3", "B3"]]),
}
CLUB_TRACKS_LIST = tuple(CLUB_TRACKS)


def club_track(kind, bars=16, seed=0):
    """Techno / house tracks for the Distillery. 16 bars, so a track runs ~30 s."""
    bpm, chords = CLUB_TRACKS[kind]
    s = Song(bpm, bars, seed)
    for bar in range(bars):
        c = chords[bar % len(chords)]
        intro = bar < 2
        break_ = bar in (bars // 2, bars // 2 + 1)
        if kind == "anthem":
            if not break_:
                for k in range(4):
                    s.add(kick(f0=130, f1=46), bar * 16 + k * 4, 0.95)
            for k in range(8):
                s.add(hat(open_=(k % 4 == 3), seed=seed + k), bar * 16 + k * 2, 0.14,
                      -0.3 if k % 2 else 0.3)
            if not intro:
                for k in (4, 12):
                    s.add(clap(seed=seed + k), bar * 16 + k, 0.30)
                for k, semis in enumerate((0, 0, 12, 0, 7, 0, 12, 10)):
                    f = freq(c[0]) / 2 * 2 ** (semis / 12.0)
                    s.add(bass_note(f, s.step * 1.7, "saw", 0.7), bar * 16 + k * 2, 0.30)
            s.add(pad_chord([freq(n) for n in c], s.step * 7.5, 0.16), bar * 16, 0.55)
            if bar % 4 == 3:
                for k, semis in enumerate((0, 12, 19, 24)):
                    s.add(pluck(freq(c[0]) * 2 ** (semis / 12.0), s.step * 2.0, "saw"),
                          bar * 16 + 12 + k, 0.14, 0.4 if k % 2 else -0.4)
        elif kind == "afterdark":
            for k in (0, 4, 8, 12):
                s.add(kick(f0=110, f1=40, click=0.2), bar * 16 + k, 0.85)
            for k in (2, 6, 10, 14):
                s.add(hat(open_=True, seed=seed + k), bar * 16 + k, 0.16, 0.35)
            s.add(pad_chord([freq(n) for n in c], s.step * 12.0, 0.22), bar * 16, 0.0)
            for k, semis in enumerate((0, 7, 10, 7)):
                f = freq(c[0]) / 2 * 2 ** (semis / 12.0)
                s.add(bass_note(f, s.step * 3.4, "sine", 0.2), bar * 16 + k * 4, 0.42)
            if bar % 2 == 1:
                s.add(pluck(freq(c[-1]) * 2, s.step * 3.0, "tri"), bar * 16 + 12, 0.16, -0.3)
        elif kind == "kohle":
            for k in range(4):
                s.add(kick(f0=150, f1=52, click=0.8), bar * 16 + k * 4, 0.98)
            for k in range(16):
                if k % 2 == 0:
                    s.add(hat(dur=0.03, seed=seed + k), bar * 16 + k, 0.10, -0.35)
                else:
                    s.add(hat(seed=seed + k), bar * 16 + k, 0.12, 0.35)
            for k in (4, 12):
                s.add(snare(seed=seed + k), bar * 16 + k, 0.34)
            if not intro:
                for k in range(8):
                    f = freq(c[0]) * (2 ** (12 / 12.0) if k == 5 else 1.0)
                    s.add(bass_note(f, s.step * 1.3, "square", 0.95),
                          bar * 16 + k * 2, 0.30)
                s.add(pad_chord([freq(n) for n in c], s.step * 6.0, 0.12), bar * 16, 0.0)
        elif kind == "rohrwerk":
            s.add(kick(f0=100, f1=38, click=0.1, dur=0.45), bar * 16, 0.85)
            s.add(kick(f0=100, f1=38, click=0.1, dur=0.35), bar * 16 + 10, 0.55)
            for k in (3, 6, 11, 14):
                s.add(hat(dur=0.04, seed=seed + k), bar * 16 + k, 0.09, 0.4)
            if bar % 4 in (1, 3):
                s.add(clap(seed=seed + bar), bar * 16 + 12, 0.18, -0.2)
            s.add(bass_note(freq(c[0]) / 2, s.step * 14.0, "sine", 0.15), bar * 16, 0.34)
            if not intro:
                for k, semis in enumerate((0, 3, 7, 3)):
                    s.add(pluck(freq(c[1]) * 2 ** (semis / 12.0), s.step * 1.4, "tri"),
                          bar * 16 + 4 + k * 3, 0.11, -0.4 + 0.2 * k)
        elif kind == "untergrund":
            for k in range(4):
                s.add(kick(f0=140, f1=48), bar * 16 + k * 4, 0.95)
            for k in range(8):
                s.add(hat(open_=(k % 4 == 3), seed=seed + k), bar * 16 + k * 2, 0.13,
                      0.3 if k % 2 else -0.3)
            if not intro:
                line = (0, 0, 12, 0, 3, 0, 10, 0, 0, 0, 12, 15, 0, 3, 0, 7)
                for k, semis in enumerate(line):
                    if k % 2 and semis == 0 and k % 4:
                        continue
                    f = freq(c[0]) * 2 ** (semis / 12.0)
                    s.add(bass_note(f, s.step * 1.6, "square", 0.9),
                          bar * 16 + k, 0.24)
            if bar % 4 == 2:
                for k, semis in enumerate((12, 15, 19, 22)):
                    s.add(pluck(freq(c[0]) * 2 ** (semis / 12.0), s.step * 1.8, "saw"),
                          bar * 16 + 8 + k * 2, 0.13, 0.4)
        elif kind == "letzteRunde":
            if bar >= 4 and not break_:
                s.add(kick(f0=95, f1=40, click=0.0, dur=0.5), bar * 16, 0.55)
                s.add(kick(f0=95, f1=40, click=0.0, dur=0.5), bar * 16 + 10, 0.35)
            s.add(pad_chord([freq(n) for n in c], s.step * 15.5, 0.34), bar * 16, 0.0)
            for k in range(4):
                s.add(pluck(freq(c[k % len(c)]) * 2, s.step * 4.0, "sine"),
                      bar * 16 + k * 4, 0.16, -0.35 + 0.23 * k)
            s.add(bass_note(freq(c[0]) / 2, s.step * 12.0, "sine", 0.1), bar * 16, 0.28)
    return s.render(fade=0.6)

TRACKS = ("disco", "techno", "chill", "country", "spooky", "western")


def write_ogg(path, stereo, rate=FS):
    """Write OGG Vorbis in blocks - libsndfile's one-shot writer can run out of
    steam on multi-minute buffers."""
    import soundfile as sf
    peak = np.abs(stereo).max()
    if peak > 0.98:
        stereo = stereo / peak * 0.98
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = np.ascontiguousarray(stereo, dtype=np.float32)
    block = 262144
    with sf.SoundFile(path, "w", rate, 2, format="OGG", subtype="VORBIS") as fh:
        for i in range(0, len(data), block):
            fh.write(data[i:i + block])
    return os.path.getsize(path)


def generate(out_dir, kinds=TRACKS, bars=8, prefix="", verbose=True):
    """Render a set of tracks into out_dir and return {kind: filename}."""
    os.makedirs(out_dir, exist_ok=True)
    out = {}
    for i, kind in enumerate(kinds):
        y = make_track(kind, bars=bars, seed=17 + i)
        name = "%s%s.ogg" % (prefix, kind)
        size = write_ogg(os.path.join(out_dir, name), y)
        out[kind] = name
        if verbose:
            print("  %-22s %5.1fs  %6.1f kB" % (name, len(y) / float(FS), size / 1024.0))
    return out
