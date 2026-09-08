"""Self-check for app.audio_enhancer — denoise + LUFS normalization on synthetic speech-like audio."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

from app.audio_enhancer import TARGET_LUFS, enhance_dual_files, enhance_speech


def _make_wav(path: Path, loudness_db: float, seconds: float = 3.0, sr: int = 16000) -> None:
    t = np.arange(int(seconds * sr)) / sr
    # "speech": amplitude-modulated tone + steady noise
    voice = 0.6 * np.sin(2 * np.pi * 220 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))
    noise = 0.05 * np.random.default_rng(42).standard_normal(len(t))
    sig = (voice + noise) * (10.0 ** (loudness_db / 20.0))
    sf.write(str(path), sig.astype("float32"), sr, subtype="PCM_16")


def test_enhance_speech_normalizes_loudness(tmp_path: Path) -> None:
    loud = tmp_path / "loud.wav"
    quiet = tmp_path / "quiet.wav"
    _make_wav(loud, -6.0)   # ~14 dB above target
    _make_wav(quiet, -34.0)  # ~14 dB below target

    out_loud = tmp_path / "out_loud.wav"
    out_quiet = tmp_path / "out_quiet.wav"
    enhance_speech(loud, out_loud)
    enhance_speech(quiet, out_quiet)

    meter = pyln.Meter(16000)
    for out in (out_loud, out_quiet):
        data, sr = sf.read(str(out))
        assert sr == 16000
        lufs = meter.integrated_loudness(data)
        assert abs(lufs - TARGET_LUFS) < 1.5, f"{out.name}: {lufs:.1f} LUFS, esperado {TARGET_LUFS}"
        assert float(np.max(np.abs(data))) <= 1.0, "clipping no output"


def test_enhance_dual_files_fallback_on_missing(tmp_path: Path) -> None:
    missing = [tmp_path / "nao_existe.wav"]
    processed, cleanup = enhance_dual_files(missing)
    assert processed == missing  # fallback: originais intactos
    cleanup()  # no-op, não deve explodir


def test_enhance_dual_files_processes_copies(tmp_path: Path) -> None:
    srcs = []
    for name, lvl in (("mic", -8.0), ("system", -32.0)):
        p = tmp_path / f"session_x_{name}.wav"
        _make_wav(p, lvl)
        srcs.append(p)

    processed, cleanup = enhance_dual_files(srcs)
    try:
        assert processed != srcs
        for orig, new in zip(srcs, processed):
            assert new.exists() and orig.exists()  # original preservado
            assert new.read_bytes() != orig.read_bytes()
    finally:
        cleanup()
        assert not processed[0].exists()  # temporários removidos


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        for fn in (test_enhance_speech_normalizes_loudness,
                   test_enhance_dual_files_fallback_on_missing,
                   test_enhance_dual_files_processes_copies):
            fn(Path(d))
            print(f"ok: {fn.__name__}")
    print("todos os checks passaram")
