# stem_separator.py

import os
import subprocess
import sys
import numpy as np
import librosa
import scipy.signal
from pathlib import Path

STEM_NAMES_6 = ["drums", "bass", "guitar", "piano", "vocals", "other"]

# Frequency bands (Hz) for drum hit isolation
DRUM_BANDS = {
    "kick":   (40,   200),
    "snare":  (150,  800),
    "hihat":  (6000, 18000),
    "toms":   (200,  2000),
    "cymbal": (3000, 18000),
}

# Onset detection tuning per drum type
DRUM_ONSET_PARAMS = {
    "kick":   dict(pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.06, wait=8),
    "snare":  dict(pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.06, wait=6),
    "hihat":  dict(pre_max=2, post_max=2, pre_avg=2, post_avg=3, delta=0.05, wait=4),
    "toms":   dict(pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.07, wait=8),
    "cymbal": dict(pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.06, wait=6),
}


def separate_stems(audio_path, output_dir=None, model="htdemucs_6s"):
    """
    Run Demucs on audio_path and return dict of stem_name -> wav_path.
    Skips separation if stems already exist.
    """
    audio_path = Path(audio_path)
    if output_dir is None:
        output_dir = audio_path.parent / "stems"
    output_dir = Path(output_dir)

    track_name = audio_path.stem
    stem_dir = output_dir / model / track_name
    expected = {stem: stem_dir / f"{stem}.wav" for stem in STEM_NAMES_6}

    if all(p.exists() for p in expected.values()):
        print(f"Using cached stems: {stem_dir}")
        return {k: str(v) for k, v in expected.items()}

    print(f"Separating stems with Demucs model '{model}'...")
    result = subprocess.run(
        [sys.executable, "-m", "demucs", "-n", model, "-o", str(output_dir), str(audio_path)],
        capture_output=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError(f"Demucs failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")

    missing = [k for k, v in expected.items() if not v.exists()]
    if missing:
        raise RuntimeError(f"Demucs finished but missing stems: {missing}")

    print(f"Stems written to: {stem_dir}")
    return {k: str(v) for k, v in expected.items()}


def _butter_bandpass(y, sr, low_hz, high_hz):
    nyq = sr / 2.0
    lo = max(low_hz / nyq, 0.001)
    hi = min(high_hz / nyq, 0.999)
    b, a = scipy.signal.butter(4, [lo, hi], btype="band")
    return scipy.signal.filtfilt(b, a, y)


def _butter_highpass(y, sr, cutoff_hz):
    nyq = sr / 2.0
    norm = min(cutoff_hz / nyq, 0.999)
    b, a = scipy.signal.butter(4, norm, btype="high")
    return scipy.signal.filtfilt(b, a, y)


def extract_drum_onsets(drum_wav_path):
    """
    Split drum stem by frequency band and detect onsets per drum type.
    Returns dict: kick/snare/hihat/toms/cymbal -> list[int] ms
    """
    y, sr = librosa.load(drum_wav_path, sr=None, mono=True)
    results = {}

    for name, (lo, hi) in DRUM_BANDS.items():
        if hi <= sr / 2 * 0.999:
            filtered = _butter_bandpass(y, sr, lo, hi)
        else:
            filtered = _butter_highpass(y, sr, lo)

        filtered = np.nan_to_num(filtered, nan=0.0, posinf=0.0, neginf=0.0)

        params = DRUM_ONSET_PARAMS[name]
        onset_times = librosa.onset.onset_detect(y=filtered, sr=sr, units='time', **params)
        results[name] = [int(t * 1000) for t in onset_times]
        print(f"  {name}: {len(results[name])} hits")

    return results


def get_stem_onsets(stem_wav_path, stem_name):
    """Generic onset detection for melodic stems. Returns list[int] ms."""
    y, sr = librosa.load(stem_wav_path, sr=None, mono=True)
    onset_times = librosa.onset.onset_detect(y=y, sr=sr, units='time')
    ms_list = [int(t * 1000) for t in onset_times]
    print(f"  {stem_name}: {len(ms_list)} onsets")
    return ms_list
