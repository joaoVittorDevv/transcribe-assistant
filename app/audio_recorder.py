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

import subprocess
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

    def start_recording(self, mode: str = "mic") -> None:
        """Begin capturing audio from the default input device or system monitor."""
        if self._recording:
            return

        with self._lock:
            self._frames = []
            self._recording = True

        self._capture_mode = mode
        
        if mode == "system":
            # PulseAudio/PipeWire fallback for Linux System Audio via 'parec'
            try:
                self._proc = subprocess.Popen(
                    [
                        "parec",
                        "--device=@DEFAULT_SINK@.monitor",
                        "--format=float32le",
                        f"--rate={_SAMPLE_RATE}",
                        f"--channels={_CHANNELS}"
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL
                )
                
                def _parec_reader() -> None:
                    chunk_size = _BLOCK_SIZE * 4 # float32 is 4 bytes per sample
                    while self._recording and hasattr(self, "_proc") and self._proc and self._proc.stdout:
                        try:
                            # Read exactly chunk_size or less if closed
                            data = self._proc.stdout.read(chunk_size)
                            if not data:
                                break
                            
                            # Convert to numpy array shape (samples, channels)
                            samples = len(data) // 4
                            chunk = np.frombuffer(data, dtype=np.float32, count=samples).reshape(-1, 1)
                            
                            self._audio_callback(chunk, samples, None, None)
                        except Exception:
                            break
                            
                self._parec_thread = threading.Thread(target=_parec_reader, daemon=True)
                self._parec_thread.start()
                return
            except FileNotFoundError:
                print("[DEBUG] AudioRecorder: parec não encontrado, system capture pode falhar.")
                # fall down to standard sd.InputStream gracefully but without 'device_id' config logic

        # Se for mic ou fallback, usamos som standard
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

        if hasattr(self, "_capture_mode") and self._capture_mode == "system":
            if hasattr(self, "_proc") and self._proc:
                self._proc.terminate()
                self._proc.wait()
                self._proc = None
        else:
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

        # Compute RMS and convert to decibels (dBFS) for realistic VU-metering
        rms = float(np.sqrt(np.mean(chunk**2)))
        
        if rms < 1e-4:  # Noise floor
            self._current_rms = 0.0
        else:
            db = 20 * np.log10(rms)
            # Map from -50dB (quiet) to 0dB (loud peak) -> 0.0 to 1.0
            min_db = -50.0
            level = (db - min_db) / (0.0 - min_db)
            self._current_rms = max(0.0, min(1.0, float(level)))

        if self._on_rms_update:
            self._on_rms_update(self._current_rms)
