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



class AudioRecorder:
    """Records audio from the default microphone or system audio with live RMS feedback.

    Args:
        on_rms_update: Optional callback called with a float in [0.0, 1.0]
                       on each audio block.
    """

    # --- Dual recording constants ---
    _MIC_WEIGHT: float = 1.0
    _SYS_WEIGHT: float = 0.8

    def __init__(self, on_rms_update: Callable[[float], None] | None = None) -> None:
        self._on_rms_update = on_rms_update
        self._frames: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self._recording = False
        self._current_rms: float = 0.0
        self._source: str = "microphone"  # "microphone" | "system_audio" | "dual"

        # Dual recording state
        self._stream_mic: sd.InputStream | None = None
        self._stream_sys: sd.InputStream | None = None
        self._mic_frames: list[np.ndarray] = []
        self._sys_frames: list[np.ndarray] = []
        self._mic_lock = threading.Lock()
        self._sys_lock = threading.Lock()

        # For parec subprocess
        self._parec_process: subprocess.Popen | None = None
        self._parec_thread: threading.Thread | None = None

    def set_source(self, source: str) -> None:
        """Set audio source: "microphone" (default), "system_audio", or "dual"."""
        if source in ("mic", "microphone"):
            self._source = "microphone"
        elif source in ("system", "system_audio"):
            self._source = "system_audio"
        elif source in ("dual", "both", "mic+system"):
            self._source = "dual"

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
            source: Optional — "mic"/"microphone", "system"/"system_audio", or "dual".
                    If provided, calls set_source() first.
        """
        if self._recording:
            return

        if source is not None:
            self.set_source(source)

        with self._lock:
            self._frames = []
            self._mic_frames = []
            self._sys_frames = []
            self._recording = True

        if self._source == "dual":
            self._start_dual_recording()
        else:
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

    # ------------------------------------------------------------------
    # Dual recording
    # ------------------------------------------------------------------

    def _start_dual_recording(self) -> None:
        """Start simultaneous capture from microphone and system audio."""
        try:
            # Microphone stream — uses the default input device
            self._stream_mic = sd.InputStream(
                device=None,  # Default input
                samplerate=_SAMPLE_RATE,
                channels=_CHANNELS,
                dtype=_DTYPE,
                blocksize=_BLOCK_SIZE,
                callback=self._mic_callback,
            )
            self._stream_mic.start()

            # System audio stream — uses PipeWire / PulseAudio monitor device
            system_device = self._resolve_device_for_system()
            if system_device is None:
                # No native monitor device - use parec fallback
                self._start_parec_recording()
            else:
                self._stream_sys = sd.InputStream(
                    device=system_device,
                    samplerate=_SAMPLE_RATE,
                    channels=_CHANNELS,
                    dtype=_DTYPE,
                    blocksize=_BLOCK_SIZE,
                    callback=self._sys_callback,
                )
                self._stream_sys.start()
        except Exception as exc:
            # Clean up streams and state on failure
            with self._lock:
                self._recording = False
            if self._stream_mic:
                try:
                    self._stream_mic.stop()
                    self._stream_mic.close()
                except Exception:
                    pass
                self._stream_mic = None
            if self._stream_sys:
                try:
                    self._stream_sys.stop()
                    self._stream_sys.close()
                except Exception:
                    pass
                self._stream_sys = None
            if self._parec_process:
                try:
                    self._parec_process.terminate()
                    self._parec_process.wait(timeout=2)
                except Exception:
                    pass
                self._parec_process = None
            if self._parec_thread:
                self._parec_thread = None
            raise RuntimeError(f"Falha ao iniciar streams do Modo Dual: {exc}") from exc

    def _resolve_device_for_system(self) -> int | None:
        """Resolve system audio device index (same logic as _resolve_device for system_audio)."""
        # Step 1: Look for PipeWire/PulseAudio virtual input sources
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

        return None

    def _mic_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time,  # noqa: ANN001
        status: sd.CallbackFlags,
    ) -> None:
        """Callback for the microphone stream in dual mode."""
        if not self._recording:
            return

        chunk = indata.copy()
        with self._mic_lock:
            self._mic_frames.append(chunk)

        # Compute RMS from microphone — this drives the VU meter
        rms = float(np.sqrt(np.mean(chunk**2)))
        self._current_rms = min(rms * 3.0, 1.0)
        if self._on_rms_update:
            self._on_rms_update(self._current_rms)

    def _sys_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time,  # noqa: ANN001
        status: sd.CallbackFlags,
    ) -> None:
        """Callback for the system audio stream in dual mode."""
        if not self._recording:
            return

        chunk = indata.copy()
        with self._sys_lock:
            self._sys_frames.append(chunk)

    # ------------------------------------------------------------------
    # Parec fallback
    # ------------------------------------------------------------------

    def _start_parec_recording(self) -> None:
        """Start system audio capture using parec (PulseAudio)."""
        # Get the default sink name for the monitor
        sink_name = self._get_default_sink_name()
        monitor_name = f"{sink_name}.monitor" if sink_name else "auto"

        try:
            cmd = [
                "parec",
                "-d", monitor_name,
                "--rate", str(_SAMPLE_RATE),
                "--channels", str(_CHANNELS),
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
        bytes_per_frame = _CHANNELS * 2  # 1 channel * 2 bytes/sample (s16le)
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

                if self._source == "dual":
                    # Store in system frames for dual mode
                    with self._sys_lock:
                        self._sys_frames.append(audio_data.astype(np.float32))
                else:
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

    def discard_recording(self) -> None:
        """Stop recording and discard all captured audio. No WAV is saved.

        Unlike stop_recording(), this does NOT write any file to disk.
        Use this when the user cancels a recording.
        """
        if not self._recording:
            return

        self._recording = False

        # Stop dual streams if active
        if self._source == "dual":
            if self._stream_mic:
                self._stream_mic.stop()
                self._stream_mic.close()
                self._stream_mic = None

            if self._stream_sys:
                self._stream_sys.stop()
                self._stream_sys.close()
                self._stream_sys = None

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

            with self._mic_lock:
                self._mic_frames = []
            with self._sys_lock:
                self._sys_frames = []
        else:
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

            # Clear frames without saving
            with self._lock:
                self._frames = []

        # Reset meter to silence
        self._current_rms = 0.0
        if self._on_rms_update:
            self._on_rms_update(0.0)

    def stop_recording(self, save_dir: Path | None = None) -> tuple[Path, Path] | Path:
        """Stop capture and save audio files.

        For dual mode: returns tuple of (mic_path, sys_path)
        For other modes: returns single Path (backward compatible)

        Args:
            save_dir: Optional directory to save the WAV file(s). If None, uses
                      temporary files.

        Returns:
            For dual mode: tuple[Path, Path] — (mic_path, sys_path)
            For other modes: Path to the saved .wav file
        """
        if not self._recording:
            raise RuntimeError("AudioRecorder: not currently recording.")

        self._recording = False

        # Stop dual streams if active
        if self._source == "dual":
            if self._stream_mic:
                self._stream_mic.stop()
                self._stream_mic.close()
                self._stream_mic = None

            if self._stream_sys:
                self._stream_sys.stop()
                self._stream_sys.close()
                self._stream_sys = None

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
        else:
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

        # --- Build audio_data ---
        if self._source == "dual":
            with self._mic_lock:
                mic_frames = list(self._mic_frames)
            with self._sys_lock:
                sys_frames = list(self._sys_frames)

            mic_audio = np.concatenate(mic_frames, axis=0) if mic_frames else np.array([])
            sys_audio = np.concatenate(sys_frames, axis=0) if sys_frames else np.array([])

            if len(mic_audio) == 0 or len(sys_audio) == 0:
                raise RuntimeError("AudioRecorder: no audio captured.")

            import uuid

            session_id = uuid.uuid4().hex[:12]

            if save_dir is not None:
                save_dir.mkdir(parents=True, exist_ok=True)
                mic_path = save_dir / f"session_{session_id}_mic.wav"
                sys_path = save_dir / f"session_{session_id}_sys.wav"
            else:
                tmp_mic = tempfile.NamedTemporaryFile(
                    delete=False, suffix=f"_mic_{session_id}.wav"
                )
                tmp_sys = tempfile.NamedTemporaryFile(
                    delete=False, suffix=f"_sys_{session_id}.wav"
                )
                tmp_mic.close()
                tmp_sys.close()
                mic_path = Path(tmp_mic.name)
                sys_path = Path(tmp_sys.name)

            sf.write(str(mic_path), mic_audio, _SAMPLE_RATE)
            sf.write(str(sys_path), sys_audio, _SAMPLE_RATE)

            return (mic_path, sys_path)
        else:
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
