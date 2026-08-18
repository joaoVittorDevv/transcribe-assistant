"""Durable audio capture tests — crash recovery and atomic finalization."""

from pathlib import Path

import numpy as np
import soundfile as sf

from app.audio_recorder import AudioRecorder


def test_pcm_part_recovered_after_crash(tmp_path: Path):
    samples = np.linspace(-0.5, 0.5, 32000, dtype=np.float32)
    part = tmp_path / "crashed_single.pcm.part"
    part.write_bytes(samples.tobytes())

    recovered = AudioRecorder.recover_pcm_parts(tmp_path)

    wav = tmp_path / "crashed_single.wav"
    assert recovered == [wav]
    assert wav.exists()
    assert not part.exists()
    audio, rate = sf.read(str(wav), dtype="float32")
    assert rate == 16000
    assert len(audio) == len(samples)
    assert np.allclose(audio, samples, atol=4e-5)


def test_empty_crash_part_is_removed(tmp_path: Path):
    part = tmp_path / "empty.pcm.part"
    part.write_bytes(b"")

    assert AudioRecorder.recover_pcm_parts(tmp_path) == []
    assert not part.exists()


def test_existing_recovery_wav_wins_idempotently(tmp_path: Path):
    part = tmp_path / "same.pcm.part"
    part.write_bytes(np.ones(16000, dtype=np.float32).tobytes())
    wav = tmp_path / "same.wav"
    sf.write(str(wav), np.zeros(16000, dtype=np.float32), 16000)

    assert AudioRecorder.recover_pcm_parts(tmp_path) == []
    assert wav.exists()
    assert not part.exists()
