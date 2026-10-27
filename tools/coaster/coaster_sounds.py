#!/usr/bin/env python3
"""Generate original loop-safe motor and rail-air sounds for Höhensturm.

The OGG samples are procedural syntheses rather than bundled game audio.  The
coaster's inherited FS25 locomotive sound controls select and pitch the loops
from motor RPM while native motorStart/motorStop events play the short sweeps.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import soundfile as sf

FS = 44100


def _time(duration: float) -> np.ndarray:
    return np.arange(int(round(duration * FS)), dtype=np.float64) / FS


def _periodic_noise(duration: float, low_hz: float, high_hz: float,
                    seed: int) -> np.ndarray:
    """Band-shaped random spectrum whose FFT construction loops seamlessly."""
    count = int(round(duration * FS))
    rng = np.random.default_rng(seed)
    frequencies = np.fft.rfftfreq(count, 1.0 / FS)
    spectrum = rng.normal(size=len(frequencies)) + 1j * rng.normal(size=len(frequencies))
    band = (frequencies >= low_hz) & (frequencies <= high_hz)
    shape = np.zeros_like(frequencies)
    shape[band] = 1.0 / np.sqrt(np.maximum(frequencies[band], low_hz))
    shape[band] *= np.exp(-frequencies[band] / (high_hz * 1.35))
    spectrum *= shape
    spectrum[0] = 0.0
    if count % 2 == 0:
        spectrum[-1] = spectrum[-1].real
    audio = np.fft.irfft(spectrum, n=count)
    audio /= max(float(np.max(np.abs(audio))), 1e-9)
    return audio


def motor_loop(duration: float, fundamental: float, seed: int,
               roughness: float = 0.035) -> np.ndarray:
    """A warm electric drive hum with a subtle, seamless RPM flutter."""
    t = _time(duration)
    # The 2 Hz wobble completes a whole number of cycles in a three-second loop.
    phase = 2.0 * np.pi * (
        fundamental * t + 4.5 / (4.0 * np.pi) * (1.0 - np.cos(4.0 * np.pi * t))
    )
    flutter = 0.88 + 0.08 * np.sin(2.0 * np.pi * 3.0 * t)
    tone = (0.48 * np.sin(phase)
            + 0.25 * np.sin(2.0 * phase + 0.17)
            + 0.12 * np.sin(3.0 * phase + 0.53)
            + 0.055 * np.sin(5.0 * phase + 1.2))
    noise = _periodic_noise(duration, 180.0, 4200.0, seed)
    audio = tone * flutter + roughness * noise
    audio /= max(float(np.max(np.abs(audio))), 1e-9)
    return audio * 0.72


def air_rush(duration: float = 3.0, seed: int = 19) -> np.ndarray:
    """A soft, filtered rail/wind wash for the faster RPM band."""
    t = _time(duration)
    noise = _periodic_noise(duration, 280.0, 9000.0, seed)
    swell = 0.66 + 0.20 * np.sin(2.0 * np.pi * 1.0 * t)
    low_whistle = (0.20 * np.sin(2.0 * np.pi * 235.0 * t)
                   + 0.08 * np.sin(2.0 * np.pi * 470.0 * t))
    audio = 0.72 * noise * swell + low_whistle
    audio /= max(float(np.max(np.abs(audio))), 1e-9)
    return audio * 0.58


def start_stop_sweep(duration: float, rising: bool, seed: int) -> np.ndarray:
    """Short, quiet dispatch/stop sweep with clean fades at both ends."""
    t = _time(duration)
    rng = np.random.default_rng(seed)
    f0, f1 = (78.0, 420.0) if rising else (420.0, 72.0)
    frequency = f0 * (f1 / f0) ** (t / duration)
    phase = 2.0 * np.pi * np.cumsum(frequency) / FS
    tone = np.sin(phase) + 0.28 * np.sin(2.0 * phase) + 0.10 * np.sin(3.0 * phase)
    noise = rng.normal(size=len(t))
    # Smooth the noise without adding a SciPy dependency.
    kernel_size = 41
    kernel = np.hanning(kernel_size)
    kernel /= kernel.sum()
    noise = np.convolve(noise, kernel, mode="same")
    progress = t / duration
    if rising:
        envelope = np.sin(0.5 * np.pi * progress) ** 1.25
    else:
        envelope = np.cos(0.5 * np.pi * progress) ** 1.25
    audio = (tone + 0.28 * noise) * envelope
    fade = min(int(0.035 * FS), len(audio) // 4)
    audio[:fade] *= np.linspace(0.0, 1.0, fade)
    audio[-fade:] *= np.linspace(1.0, 0.0, fade)
    audio /= max(float(np.max(np.abs(audio))), 1e-9)
    return audio * 0.52


def _write(path: Path, audio: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio.astype(np.float32), FS, format="OGG", subtype="VORBIS")


def generate(output_dir: str | Path) -> list[Path]:
    output = Path(output_dir)
    sounds = {
        "coasterIdle.ogg": motor_loop(3.0, 66.0, seed=14, roughness=0.025),
        "coasterWhine.ogg": motor_loop(3.0, 112.0, seed=27, roughness=0.045),
        "coasterAirRush.ogg": air_rush(),
        "coasterStart.ogg": start_stop_sweep(1.25, rising=True, seed=31),
        "coasterStop.ogg": start_stop_sweep(1.05, rising=False, seed=32),
    }
    paths = []
    for name, audio in sounds.items():
        path = output / name
        _write(path, audio)
        paths.append(path)
        print("  %-20s %5.2fs %6.1f kB" %
              (name, len(audio) / FS, path.stat().st_size / 1024.0))
    return paths


if __name__ == "__main__":
    generate(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
             / "build" / "rollercoaster" / "FS25_Hoehensturm" / "sounds")
