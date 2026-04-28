"""app.audio_recorder — Audio capture with real-time RMS metering.

Captures audio from the system's default microphone via sounddevice,
OR system audio via PipeWire/PulseAudio monitor devices or parec fallback.
Saves the result to a WAV file via soundfile, and computes
RMS (Root Mean Square) values via numpy for the VU meter widget.

Usage:
    recorder = AudioRecorder(on_rms_update=my_callback)
    recorder.set_source("system_audio")
    recorder.start_recording()
    # ... system audio is captured ...
    wav_path = recorder.stop_recording(save_dir=Path("Vault"))
"""

import struct
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

# parec settings
_PAREC_SAMPLE_RATE = 44100  # parec outputs at the sink's sample rate
_PAREC_CHANNELS = 2  # parec outputs stereo by default


class AudioRecorder:
    """Records audio from the default microphone or system audio with live RMS feedback.

    Args:
        on_rms_update: Optional callback called with a float in [0.0, 1.0]
                       on each audio block.
    """

    def __init__(self, on_rms_update: Callable[[float], None] | None = None) -> None:
        self._on_rms_update = on_rms_update
        self._frames: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self._recording = False
        self._current_rms: float = 0.0
        self._source: str = "microphone"  # "microphone" | "system_audio"
        # For parec subprocess
        self._parec_process: subprocess.Popen | None = None
        self._parec_thread: threading.Thread | None = None

    def set_source(self, source: str) -> None:
        """Set audio source: "microphone" (default) or "system_audio"."""
        if source in ("mic", "microphone"):
            self._source = "microphone"
        elif source in ("system", "system_audio"):
            self._source = "system_audio"

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

    def start_recording(self, source: str | None = None) -> None:
        """Begin capturing audio from the configured source.

        Args:
            source: Optional — "mic"/"microphone" or "system"/"system_audio".
                    If provided, calls set_source() first.
        """
        if self._recording:
            return

        if source is not None:
            self.set_source(source)

        with self._lock:
            self._frames = []
            self._recording = True

        device = self._resolve_device()

        if self._source == "system_audio" and device is None:
            # No native monitor device - use parec
            self._start_parec_recording()
        else:
            # Use sounddevice
            self._stream = sd.InputStream(
                device=device,
                samplerate=_SAMPLE_RATE,
                channels=_CHANNELS,
                dtype=_DTYPE,
                blocksize=_BLOCK_SIZE,
                callback=self._audio_callback,
            )
            self._stream.start()

    def _start_parec_recording(self) -> None:
        """Start system audio capture using parec (PulseAudio)."""
        # Get the default sink name for the monitor
        sink_name = self._get_default_sink_name()
        monitor_name = f"{sink_name}.monitor" if sink_name else "auto"

        try:
            cmd = [
                "parec",
                "-d", monitor_name,
                "--rate", str(_PAREC_SAMPLE_RATE),
                "--channels", str(_PAREC_CHANNELS),
                "--format", "s16le",
            ]

            self._parec_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Start thread to read parec output
            self._parec_thread = threading.Thread(
                target=self._parec_reader,
                daemon=True,
                name="ParecReader",
            )
            self._parec_thread.start()

        except FileNotFoundError:
            self._recording = False
            raise RuntimeError(
                "parec not found. Install pulseaudio-utils package."
            )
        except Exception:
            self._recording = False
            raise

    def _parec_reader(self) -> None:
        """Read audio data from parec subprocess in a background thread."""
        bytes_per_frame = _PAREC_CHANNELS * 2  # 2 bytes per sample (s16le)
        target_bytes = _BLOCK_SIZE * bytes_per_frame

        try:
            while (
                self._recording
                and self._parec_process
                and self._parec_process.poll() is None
            ):
                # Read raw bytes from parec
                raw = self._parec_process.stdout.read(target_bytes)
                if not raw:
                    break

                # Convert s16le to float32 numpy array
                samples = struct.unpack(f"<{len(raw)//2}h", raw)

                # Convert to numpy array
                audio_data = np.array(samples, dtype=np.float32) / 32768.0

                # If stereo, mix down to mono (average channels)
                if _PAREC_CHANNELS == 2:
                    audio_data = audio_data.reshape(-1, 2)
                    audio_data = np.mean(audio_data, axis=1)

                # Resample from _PAREC_SAMPLE_RATE to _SAMPLE_RATE
                if _PAREC_SAMPLE_RATE != _SAMPLE_RATE:
                    audio_data = self._resample(
                        audio_data, _PAREC_SAMPLE_RATE, _SAMPLE_RATE
                    )

                # Compute RMS for VU meter
                rms = float(np.sqrt(np.mean(audio_data**2)))
                self._current_rms = min(rms * 3.0, 1.0)
                if self._on_rms_update:
                    self._on_rms_update(self._current_rms)

                # Store frame
                with self._lock:
                    self._frames.append(audio_data.astype(np.float32))

        except Exception:
            pass

    def _resample(self, data: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
        """Simple linear resampling."""
        if from_rate == to_rate:
            return data

        ratio = to_rate / from_rate
        new_length = int(len(data) * ratio)
        indices = np.linspace(0, len(data) - 1, new_length)
        resampled = np.interp(indices, np.arange(len(data)), data)
        return resampled.astype(np.float32)

    def _get_default_sink_name(self) -> str | None:
        """Get the default sink name using pactl."""
        try:
            result = subprocess.run(
                ["pactl", "get-default-sink"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _resolve_device(self) -> int | None:
        """Resolve self._source to a sounddevice device index.

        "microphone" → default input device (None)
        "system_audio" → On Linux with PipeWire/PulseAudio, system audio capture
            is done via loopback monitor devices. On PipeWire these appear as
            PLAYBACK devices (max_output_channels > 0) with names like
            "Monitor of <device>". We first try to find input-type virtual
            sources (pipewire/pulse/default), then fall back to scanning ALL
            devices (including playback) for "Monitor of" names or traditional
            ALSA monitor/mix device names. Returns None if no suitable device
            is found (which triggers parec fallback).
        """
        if self._source == "system_audio":
            # Step 1: Look for PipeWire/PulseAudio virtual input sources
            # Skip sink/source duplex devices (max_in > 0 AND max_out > 0)
            for idx, info in enumerate(sd.query_devices()):
                name = info.get("name", "").lower()
                max_in = info.get("max_input_channels", 0)
                max_out = info.get("max_output_channels", 0)
                if max_in > 0 and max_out > 0:
                    continue
                if name in ("pipewire", "pulse", "default"):
                    return idx

            # Step 2: Scan ALL devices for "Monitor of" names
            for idx, info in enumerate(sd.query_devices()):
                name = info.get("name", "").lower()
                if "monitor of" in name or "monitorof" in name.replace(" ", ""):
                    return idx

            # Step 3: Fall back to ALSA monitor/mix device names
            for idx, info in enumerate(sd.query_devices()):
                name = info.get("name", "").lower()
                if "monitor" in name or "mix" in name:
                    return idx

            # No native monitor found - will use parec fallback
        return None

    def stop_recording(self, save_dir: Path | None = None) -> Path:
        """Stop capture and save audio to a WAV file.

        Args:
            save_dir: Optional directory to save the WAV file. If None, uses a
                      temporary directory.

        Returns:
            Path to the saved .wav file (caller is responsible for cleanup).
        """
        if not self._recording:
            raise RuntimeError("AudioRecorder: not currently recording.")

        self._recording = False

        # Stop sounddevice stream if active
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        # Stop parec process if active
        if self._parec_process:
            self._parec_process.terminate()
            try:
                self._parec_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._parec_process.kill()
            self._parec_process = None

        if self._parec_thread:
            self._parec_thread.join(timeout=2)
            self._parec_thread = None

        # Reset meter to silence
        self._current_rms = 0.0
        if self._on_rms_update:
            self._on_rms_update(0.0)

        with self._lock:
            frames = list(self._frames)

        if not frames:
            raise RuntimeError("AudioRecorder: no audio captured.")

        audio_data = np.concatenate(frames, axis=0)

        if save_dir is not None:
            save_dir.mkdir(parents=True, exist_ok=True)
            import uuid

            wav_name = f"transcribe_{uuid.uuid4().hex[:12]}.wav"
            wav_path = save_dir / wav_name
        else:
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
        self._current_rms = min(rms * 3.0, 1.0)

        if self._on_rms_update:
            self._on_rms_update(self._current_rms)
