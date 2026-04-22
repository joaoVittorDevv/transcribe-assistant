# Audio Chunking para Transcrição — SPEC v2

**Versão:** 2
**Data:** 2026-04-22
**Status:** CONFIRMED
**Feature:** Fatiamento de áudios longos em chunks processáveis sequencialmente

---

## 1. Contexto

O `Transcriber` atual envia áudio integral para a API Groq/Gemini sem proteção contra áudios longos. O Groq tem limite prático de ~25 MB por arquivo. Áudios > 10-15 min podem causar timeout ou falha. O projeto já usa `sounddevice` + `soundfile` + `numpy`.

---

## 2. Requisitos

| ID | Requisito | Critério de aceite |
|----|-----------|-------------------|
| **R1** | Módulo `app/audio_chunker.py` com `@contextmanager split_audio()` | Existe com docstring, exceptions documentadas |
| **R2** | Chunking por duração fixa (default 10 min) | Cada chunk ≤ max_duration_sec |
| **R3** | Chunk final < 5s → merge com anterior | Nenhum chunk final órfão |
| **R4** | Validação 25 MB **por chunk** após fatiamento | Se chunk > 25MB, aborta com `AudioChunkingError` |
| **R5** | Cleanup automático via context manager | Arquivos temp removidos em sucesso ou erro |
| **R6** | Integração fail-fast no Transcriber | Chunk que falha = aborta tudo, não tenta próximo |
| **R7** | UI progress via `_ui_queue` | Status label mostra "Transcribing chunk K/N..." |

---

## 3. API Pública

```python
@contextmanager
def split_audio(
    audio_path: Path,
    max_duration_sec: float = 600.0,
    min_chunk_sec: float = 5.0,
) -> Generator[list[tuple[Path, float]], None, None]:
    """Yield list of (chunk_path, duration_sec) tuples.

    Params:
        audio_path: Path to WAV file to split.
        max_duration_sec: Maximum duration per chunk (default 600s = 10 min).
        min_chunk_sec: Minimum chunk duration; shorter final chunks are merged
            with the previous chunk (default 5s).

    Yields:
        List of (chunk_path, duration_sec) tuples in chronological order.

    Raises:
        AudioChunkingError: if audio is unreadable or any chunk exceeds 25 MB.

    Cleanup:
        All temporary chunk files are removed when the context exits —
        both on success and on exception.
    """
```

---

## 4. Classe de Exceção

```python
class AudioChunkingError(Exception):
    """Raised when audio chunking fails (unreadable file, chunk > 25MB, etc.)."""
```

---

## 5. Fluxo dentro de `_transcribe_groq` / `_transcribe_gemini`

```
1. Calcular duração total do áudio (via soundfile.info)
2. Calcular tamanho em MB do arquivo original

3. SE (tamanho > 25MB) OU (duração > max_duration_sec):
   → with split_audio(audio_path, max_duration_sec) as chunks:
   → para cada chunk (k, (path, dur)):
       → SE path.stat().st_size > 25MB: raise AudioChunkingError
       → chamar API de transcrição (Groq ou Gemini)
       → acumular texto
       → _ui_queue.put(("transcription_progress", f"Transcribing chunk {k}/{len(chunks)}..."))
   → resultado = "\n\n".join(textos_dos_chunks)

4. SENÃO (áudio <= 25MB E duração <= max_duration_sec):
   → transcrição normal (sem chunking)
```

---

## 6. Concatenação

- Processamento **sequencial** — garante ordem temporal
- Textos concatenados com `\n\n` entre chunks
- **Fail-fast**: qualquer exceção em qualquer chunk aborta a transcrição inteira

---

## 7. Validações

| Validação | Comportamento |
|-----------|---------------|
| Áudio < max_duration | Retorna lista com 1 chunk (sem chunking) |
| Último chunk < min_chunk_sec | Faz merge com chunk anterior |
| Chunk > 25 MB após fatiar | `AudioChunkingError` com mensagem clara |
| WAV ilegível/malformado | `AudioChunkingError` |
| Erro em qualquer chunk | `TranscriptionError` (fail-fast) |

---

## 8. Dependências

- `soundfile` (já no projeto)
- `numpy` (já no projeto)
- `contextlib` (stdlib)
- `tempfile` (stdlib)
- `uuid` (stdlib)

---

## 9. Arquivos a criar/modificar

| Arquivo | Ação |
|---------|------|
| `app/audio_chunker.py` | **Criar** — módulo com `split_audio` e `AudioChunkingError` |
| `app/transcriber.py` | **Modificar** — `_transcribe_groq` e `_transcribe_gemini` chamam chunking |
| `app/ui/main_window.py` | **Modificar** — tratar evento `transcription_progress` no `_poll_ui_queue()` |

---

## 10. Fora do Escopo

- Detecção de silêncio para pontos de corte inteligentes
- Processamento paralelo de chunks
- Suporte a formatos não-WAV
- Cancelamento de chunking em progresso
