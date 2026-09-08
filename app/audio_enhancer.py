"""app.audio_enhancer — speech enhancement for the dual transcription pipeline.

Option 1 (light DSP, no torch):
  1. Spectral-gating denoise (noisereduce, non-stationary) — removes steady
     background noise: fan hum, VoIP codec hiss, room tone.
  2. Loudness normalization (pyloudnorm, EBU R128 / ITU-R BS.1770) — brings
     mic and system tracks to the same integrated loudness (LUFS), so Gemini
     receives comparable levels for diarization instead of relying on volume.

Processed COPIES are written to a temp dir; the original WAVs in the Vault
are never modified (they remain the recovery copy). Any failure falls back
to the original paths — enhancement must never block transcription.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

# Targets tuned for 16 kHz mono speech going into ASR.
TARGET_LUFS = -20.0
# Conservative spectral gating: full reduction (1.0) can produce artifacts
# that hurt ASR models trained on noisy audio.
NOISE_PROP_DECREASE = 0.85
# Fragments shorter than this are copied as-is (too short for a reliable
# integrated-loudness measurement).
MIN_DURATION_SEC = 0.5


def enhancement_enabled() -> bool:
    """DB setting gate (default on). Any storage failure keeps it on."""
    try:
        from app import database as db

        return db.get_setting("AUDIO_ENHANCEMENT_ENABLED", "true").strip().lower() != "false"
    except Exception:
        return True


def enhance_speech(wav_path: Path, out_path: Path) -> Path:
    """Denoise + loudness-normalize one speech WAV into ``out_path``.

    Returns ``out_path``. Raises on unrecoverable I/O errors.
    """
    import numpy as np
    import noisereduce as nr
    import pyloudnorm as pyln
    import soundfile as sf

    data, sr = sf.read(str(wav_path), dtype="float32")
    if data.ndim > 1:  # ponytail: pipeline é mono; mixdown defensivo
        data = data.mean(axis=1, dtype="float32")

    if len(data) < int(MIN_DURATION_SEC * sr):
        sf.write(str(out_path), data, sr, subtype="PCM_16")
        return out_path

    reduced = nr.reduce_noise(
        y=data, sr=sr, stationary=False, prop_decrease=NOISE_PROP_DECREASE
    ).astype("float32")

    # Normalize to the shared LUFS target so mic/system tracks are comparable.
    try:
        loudness = pyln.Meter(sr).integrated_loudness(reduced)
        if np.isfinite(loudness) and loudness > -70.0:  # -70 ≈ silence
            gain_db = TARGET_LUFS - loudness
            reduced = reduced * (10.0 ** (gain_db / 20.0))
    except Exception:
        pass  # silent/odd signal — keep denoised, unnormalized

    peak = float(np.max(np.abs(reduced))) if reduced.size else 0.0
    if peak > 1.0:
        reduced = reduced / peak  # avoid clipping after gain

    sf.write(str(out_path), reduced, sr, subtype="PCM_16")
    return out_path


def enhance_dual_files(paths: list[Path]) -> tuple[list[Path], callable]:
    """Process copies of the dual WAVs (mic + system) into a temp dir.

    Returns ``(processed_paths, cleanup)``. On any failure returns the
    original paths and a no-op cleanup, so callers can proceed unenhanced.
    """
    if not enhancement_enabled():
        return paths, lambda: None
    try:
        tmp = tempfile.TemporaryDirectory(prefix="dual_enhanced_")
        processed = []
        for p in paths:
            out = Path(tmp.name) / f"enhanced_{p.name}"
            processed.append(enhance_speech(Path(p), out))
        return processed, tmp.cleanup
    except Exception as exc:
        print(f"[audio_enhancer] falha no pré-processamento, usando originais: {exc}")
        return paths, lambda: None
