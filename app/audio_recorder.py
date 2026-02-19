"""app.audio_recorder — Audio capture with real-time RMS metering.

Captures audio from the system's default microphone via sounddevice,
saves the result to a temporary WAV file via soundfile, and computes
RMS (Root Mean Square) values via numpy for the VU meter widget.

Usage:
    recorder = AudioRecorder(on_rms_update=my_callback)
    recorder.start_recording()
    # ... user speaks ...
    wav_path = recorder.stop_recording()
"""

import tempfile
import threading
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd
import soundfile as sf

# Audio capture settings
_SAMPLE_RATE = 16_000  # 16 kHz — ideal for speech / Whisper
_CHANNELS = 1  # Mono
_DTYPE = "float32"  # sounddevice native float range [-1.0, 1.0]
_BLOCK_SIZE = 1024  # Frames per callback — controls RMS update rate


class AudioRecorder:
    """Records audio from the default microphone with live RMS feedback.

    Args:
        on_rms_update: Optional callback called with a float in [0.0, 1.0]
                       on each audio block. Safe to update UI labels from it
                       if routed through root.after().
    """

    def __init__(self, on_rms_update: Callable[[float], None] | None = None) -> None:
        self._on_rms_update = on_rms_update
        self._frames: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self._recording = False
        self._current_rms: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def current_rms(self) -> float:
        """Last computed RMS value in the range [0.0, 1.0]."""
        return self._current_rms

    def start_recording(self) -> None:
        """Begin capturing audio from the default input device."""
        if self._recording:
            return

        with self._lock:
            self._frames = []
            self._recording = True

        self._stream = sd.InputStream(
            samplerate=_SAMPLE_RATE,
            channels=_CHANNELS,
            dtype=_DTYPE,
            blocksize=_BLOCK_SIZE,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop_recording(self) -> Path:
        """Stop capture and save audio to a temporary WAV file.

        Returns:
            Path to the saved .wav file (caller is responsible for cleanup).
        """
        if not self._recording:
            raise RuntimeError("AudioRecorder: not currently recording.")

        self._recording = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        # Reset meter to silence
        self._current_rms = 0.0
        if self._on_rms_update:
            self._on_rms_update(0.0)

        with self._lock:
            frames = list(self._frames)

        if not frames:
            raise RuntimeError("AudioRecorder: no audio captured.")

        audio_data = np.concatenate(frames, axis=0)

        tmp = tempfile.NamedTemporaryFile(
            suffix=".wav", delete=False, prefix="transcribe_"
        )
        tmp.close()
        wav_path = Path(tmp.name)

        sf.write(str(wav_path), audio_data, _SAMPLE_RATE)
        return wav_path

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time,  # noqa: ANN001
        status: sd.CallbackFlags,
    ) -> None:
        """Called by sounddevice on each audio block."""
        if not self._recording:
            return

        chunk = indata.copy()

        with self._lock:
            self._frames.append(chunk)

        # Compute RMS and normalize to [0.0, 1.0]
        rms = float(np.sqrt(np.mean(chunk**2)))
        # float32 PCM peaks near 1.0, so clamp to that range
        self._current_rms = min(rms * 3.0, 1.0)  # slight boost for visual feel

        if self._on_rms_update:
            self._on_rms_update(self._current_rms)
