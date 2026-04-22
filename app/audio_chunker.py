"""app.audio_chunker — Split long audio files into processable chunks.

This module provides a context manager that splits WAV audio files into
fixed-duration chunks suitable for transcription APIs with file-size or
duration limits (e.g., Groq's 25 MB limit).

Features:
  - Fixed-duration chunking (default 10 min, configurable via max_duration_sec)
  - Small trailing chunk merge: if last chunk < min_chunk_sec, it is merged
    with the previous chunk to avoid orphaned micro-chunks
  - Per-chunk 25 MB validation: raises AudioChunkingError if any chunk
    exceeds 25 MB after writing
  - Automatic cleanup: all temporary chunk files are removed when the
    context exits — both on success and on exception

Usage:
    with split_audio(audio_path, max_duration_sec=600.0) as chunks:
        for chunk_path, duration_sec in chunks:
            # process chunk
            ...

    # chunks is a list of (Path, duration_sec) tuples, already cleaned up
"""

from __future__ import annotations

import math
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import numpy
import soundfile as sf

# Groq free-tier limit
_MAX_CHUNK_BYTES = 25 * 1024 * 1024  # 25 MB


class AudioChunkingError(Exception):
    """Raised when audio chunking fails (unreadable file, chunk > 25MB, etc.)."""


@contextmanager
def split_audio(
    audio_path: Path,
    max_duration_sec: float = 600.0,
    min_chunk_sec: float = 5.0,
) -> Generator[list[tuple[Path, float]], None, None]:
    """Split a WAV file into chunks not exceeding max_duration_sec.

    Params:
        audio_path: Path to the WAV file to split.
        max_duration_sec: Maximum duration per chunk in seconds (default 600s = 10 min).
        min_chunk_sec: Minimum chunk duration; a shorter final chunk is merged
            with the previous chunk (default 5s).

    Yields:
        List of (chunk_path, duration_sec) tuples in chronological order.

    Raises:
        AudioChunkingError: if the audio is unreadable or any chunk exceeds 25 MB.

    Cleanup:
        All temporary chunk files are removed when the context exits —
        both on success and on exception.
    """
    temp_dir = tempfile.mkdtemp(prefix="audio_chunk_")
    chunk_paths: list[Path] = []
    chunk_durations: list[float] = []

    try:
        # Read audio metadata first to validate the file
        try:
            info = sf.info(str(audio_path))
            sample_rate = info.samplerate
            total_duration = info.duration
        except Exception as exc:
            raise AudioChunkingError(
                f"Unable to read audio file: {audio_path}. "
                f"The file may be malformed or not a valid WAV. Details: {exc}"
            ) from exc

        # Read the full audio data
        try:
            data, _ = sf.read(str(audio_path))
        except Exception as exc:
            raise AudioChunkingError(
                f"Unable to read audio data from: {audio_path}. Details: {exc}"
            ) from exc

        # Calculate how many samples per chunk
        samples_per_chunk = int(max_duration_sec * sample_rate)
        total_samples = data.shape[0]
        num_chunks = math.ceil(total_samples / samples_per_chunk)

        if num_chunks == 1:
            # No chunking needed — single short file, just validate size
            if audio_path.stat().st_size > _MAX_CHUNK_BYTES:
                raise AudioChunkingError(
                    f"Audio file exceeds 25 MB limit ({audio_path.stat().st_size / 1024 / 1024:.1f} MB). "
                    "Use a shorter audio file or split it manually."
                )
            # Yield single chunk pointing to original file (no temp file created)
            result = [(audio_path, total_duration)]
            try:
                yield result
            finally:
                pass  # No temp files to clean for single-chunk case
            return

        # Split into multiple chunks
        for i in range(num_chunks):
            start_sample = i * samples_per_chunk
            end_sample = min((i + 1) * samples_per_chunk, total_samples)
            chunk_data = data[start_sample:end_sample]

            chunk_duration = (end_sample - start_sample) / sample_rate

            # Write temporary chunk file
            chunk_filename = f"chunk_{uuid.uuid4().hex}_{i:04d}.wav"
            chunk_path = Path(temp_dir) / chunk_filename
            sf.write(chunk_path, chunk_data, sample_rate)

            chunk_paths.append(chunk_path)
            chunk_durations.append(chunk_duration)

        # Merge small trailing chunk with previous if needed
        if (
            len(chunk_durations) >= 2
            and chunk_durations[-1] < min_chunk_sec
        ):
            last_idx = len(chunk_durations) - 1
            prev_idx = last_idx - 1

            prev_path = chunk_paths[prev_idx]
            last_path = chunk_paths[last_idx]

            # Read both chunks and merge using numpy concatenation
            prev_data, prev_sr = sf.read(str(prev_path))
            last_data, _ = sf.read(str(last_path))
            merged_data = numpy.concatenate([prev_data, last_data])

            # Overwrite previous chunk with merged data
            sf.write(prev_path, merged_data, prev_sr)

            # Update duration
            chunk_durations[prev_idx] = (
                chunk_durations[prev_idx] + chunk_durations[last_idx]
            )

            # Remove last chunk path from lists
            chunk_paths.pop()
            chunk_durations.pop()

        # Validate 25 MB per chunk after writing
        for chunk_path in chunk_paths:
            if chunk_path.stat().st_size > _MAX_CHUNK_BYTES:
                raise AudioChunkingError(
                    f"Chunk {chunk_path.name} exceeds 25 MB limit "
                    f"({chunk_path.stat().st_size / 1024 / 1024:.1f} MB) after chunking. "
                    "Please use a shorter max_duration_sec or a lower sample rate."
                )

        result = list(zip(chunk_paths, chunk_durations))
        yield result

    finally:
        # Cleanup: remove all temporary chunk files
        import shutil

        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass
