"""app.utils.audio_stream_processor — Utility for processing and mixing streaming audio.

Converts NumPy audio arrays into memory-buffered WAV streams for API ingestion.
Supports digital mixing of dual-source audio (microphone + system audio) into a single mono track.
"""

import io
import numpy as np
import soundfile as sf


class AudioStreamProcessor:
    """Utility class to process and mix raw NumPy audio arrays into memory-buffered WAV streams."""

    @staticmethod
    def mix_dual_audio(
        mic_audio: np.ndarray,
        sys_audio: np.ndarray,
        mic_weight: float = 1.0,
        sys_weight: float = 0.8,
    ) -> np.ndarray:
        """Mix microphone and system audio arrays into a single mono channel.

        Aligns lengths by padding the shorter array with zeros, then computes
        a weighted linear mix. Returns a mono float32 numpy array.
        """
        len_mic = len(mic_audio)
        len_sys = len(sys_audio)

        if len_mic == 0:
            return sys_audio
        if len_sys == 0:
            return mic_audio

        # Align lengths (pad the shorter one with zeros)
        if len_mic != len_sys:
            max_len = max(len_mic, len_sys)
            if len_mic < max_len:
                mic_padded = np.zeros(max_len, dtype=mic_audio.dtype)
                mic_padded[:len_mic] = mic_audio
                mic_audio = mic_padded
            else:
                sys_padded = np.zeros(max_len, dtype=sys_audio.dtype)
                sys_padded[:len_sys] = sys_audio
                sys_audio = sys_padded

        # Linear weighted mix
        mixed = (mic_audio * mic_weight + sys_audio * sys_weight) / (
            mic_weight + sys_weight
        )
        return mixed.astype(np.float32)

    @staticmethod
    def to_wav_bytes(audio_data: np.ndarray, sample_rate: int = 16000) -> io.BytesIO:
        """Convert a 1D NumPy float32 audio array to a standard PCM_16 WAV in memory.

        Returns a seeked io.BytesIO buffer containing the raw WAV file bytes.
        """
        wav_buffer = io.BytesIO()
        # Flatten and ensure 1D mono
        if audio_data.ndim > 1:
            audio_data = audio_data.mean(axis=1)

        # Write WAV format with 16-bit PCM subtype (ideal for speech APIs)
        sf.write(wav_buffer, audio_data, sample_rate, format="WAV", subtype="PCM_16")
        wav_buffer.seek(0)
        return wav_buffer
