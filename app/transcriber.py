"""app.transcriber — AI transcription router (Gemini ↔ Groq).

Routes audio transcription requests between:
  - Google Gemini (cloud): uploads audio via Files API + System Instruction,
    streaming word-by-word via generate_content_stream.
  - Groq Whisper (cloud): fast, cost-effective for short audio (< 10 min).
    Transcribed text is automatically reviewed by TranscriptionReviewAgent
    for grammar/punctuation correction.

Audio files longer than 10 minutes are automatically routed to Google Gemini
regardless of selected mode — Groq has a 25 MB file limit and client-side
chunking degrades transcription quality.

Modes:
  "auto"   — Try Groq + review; fall back to Gemini silently.
  "gemini" — Force Gemini only; raises TranscriptionError if offline.
  "groq"   — Force Groq only; raises TranscriptionError if offline.
             Audio > 10 min is automatically redirected to Gemini.

Usage:
    transcriber = Transcriber(network_monitor)
    text = transcriber.transcribe(
        audio_path=wav_path,
        prompt_text="Aja como desenvolvedor...",
        keywords=["Reqflow", "faster-whisper"],
        mode="auto",
        on_chunk=callback,
    )
"""

from pathlib import Path
from typing import Literal

from app.config import (
    GEMINI_MODEL,
    GEMINI_TIMEOUT,
    GOOGLE_API_KEY,
    GROQ_API_KEY,
    GROQ_REVIEW_MODEL,
)

TranscriptionMode = Literal["auto", "gemini", "groq"]

# ---------------------------------------------------------------------------
# Output filter — strips chat-like prefixes/suffixes from LLM responses
# ---------------------------------------------------------------------------
import re as _re  # noqa: E402

_CONVERSATIONAL_PREFIXES = [
    r"^Aqui está (?:a|o) (?:texto )?(?:corrigid[ao]|revisad[ao]|transcri[cç][aã]o)[:]\s*",
    r"^Segue (?:abaixo )?(?:a|o) (?:texto )?(?:corrigid[ao]|revisad[ao]|transcri[cç][aã]o)[:]\s*",
    r"^Claro[!,.]?\s*(?:aqui está)?[:]?\s*",
    r"^Com certeza[!,.]?\s*[:]?\s*",
    r"^Transcri[cç][aã]o(?: corrigida| revisada)?[:]\s*",
    r"^Texto (?:corrigido|revisado)[:]\s*",
    r"^O texto (?:corrigido|revisado) (?:ficou|ficaria|é)[:]\s*",
    r"^O resultado (?:da revisão|final) (?:é|ficou)[:]\s*",
    r"^Corre[cç][aã]o[:]\s*",
    r"^Revis[aã]o[:]\s*",
    r"^Resposta[:]\s*",
    r"^Here is the (?:corrected|reviewed) (?:text|transcription)[:]\s*",
    r"^Sure[!,.]?\s*(?:here(?:'s| you go))?[:]?\s*",
    r"^Of course[!,.]?\s*[:]?\s*",
    r"^The (?:corrected|reviewed) (?:text|transcription)(?: is)?[:]\s*",
]


def _filter_transcription_output(text: str) -> str:
    """Strip conversational prefixes from LLM transcription output.

    Safety net — the system prompt should prevent these, but if the model
    still responds conversationally, strip it here.
    """
    if not text:
        return text
    cleaned = text.strip()
    for pattern in _CONVERSATIONAL_PREFIXES:
        cleaned = _re.sub(pattern, "", cleaned, count=1, flags=_re.IGNORECASE).strip()
    return cleaned

GEMINI_SYSTEM_AUDIO_INSTRUCTION = (
    "Voce e um motor de transcricao de audio do sistema. "
    "O audio que voce recebe e a captura do som que esta sendo reproduzido "
    "no computador do usuario — como uma reuniao, video, podcast ou chamada. "
    "Seu trabalho e transcrever esse audio com precisao.\n\n"
    "REGRAS DE OURO -- SIGA TODAS SEM EXCECAO:\n\n"
    "1. SAIDA EXCLUSIVA: Retorne APENAS e SOMENTE o texto transcrito do audio. "
    "NADA mais. Sem prefixos, sem sufixos, sem notas, sem comentarios.\n\n"
    "2. FIDELIDADE TOTAL: Transcreva exatamente o que foi falado. "
    "Preserve interjeicoes ('ah', 'oh', 'hmm'), repeticoes, "
    "e palavras incompletas tal como foram pronunciadas.\n\n"
    "3. IDENTIFICACAO DE INTERLOCUTORES (DIARIZACAO): "
    "O audio pode conter MULTIPLAS PESSOAS falando. Voce DEVE:\n"
    "   a) Identificar mudancas de interlocutor e marcar com '---' (tres hifens) "
    "em uma linha separada antes da fala do novo interlocutor.\n"
    "   b) Quando possivel, identificar os interlocutores por nome ou papel "
    "usando o prefixo '@Nome:' antes da fala (ex: '@Joao: Bom dia').\n"
    "   c) Quando nao for possivel identificar o nome, use '@Interlocutor 1:', "
    "'@Interlocutor 2:', etc., mantendo consistencia ao longo da transcricao "
    "(o mesmo numero para a mesma pessoa).\n"
    "   d) Quando o mesmo interlocutor voltar a falar apos uma pausa ou apos "
    "outra pessoa falar, reutilize o mesmo identificador ja atribuido a ele.\n"
    "   e) Para falas muito curtas ou sobrepostas sem clareza de quem falou, "
    "apenas transcreva sem atribuir interlocutor.\n\n"
    "4. GLOSSARIO -- USO CONDICIONAL E RESTRITIVO: "
    "O glossario serve apenas para desfazer ambiguidades genuinas "
    "em trechos ininteligiveis do audio. REGRAS RIGOROSAS:\n"
    "   a) NUNCA substitua uma palavra que ja faz sentido no contexto -- "
    "mesmo que seja foneticamente semelhante a um termo do glossario.\n"
    "   b) Apenas substitua quando: (i) o audio e genuinamente ininteligivel E "
    "(ii) o termo do glossario faz sentido contextual PERFEITO.\n"
    "   c) Se houver qualquer duvida, NAO substitua. Mantenha o que foi ouvido.\n\n"
    "5. PONTUACAO: Adicione pontuacao natural baseada nas pausas "
    "e entonacao do audio. Nao reformule frases, nao mude ordem de palavras.\n\n"
    "6. PROIBIDO: Jamais responda com frases como 'Aqui esta a transcricao', "
    "'Claro', 'Segue abaixo', ou qualquer texto que nao seja a transcricao. "
    "A sua unica saida possivel e o texto do audio. Nada mais."
)

GEMINI_SYSTEM_INSTRUCTION = (
    "Voce e um motor de transcricao de audio. "
    "Seu trabalho e APENAS transcrever o audio recebido palavra por palavra.\n\n"
    "REGRAS DE OURO -- SIGA TODAS SEM EXCECAO:\n\n"
    "1. SAIDA EXCLUSIVA: Retorne APENAS e SOMENTE o texto transcrito do audio. "
    "NADA mais. Sem prefixos, sem sufixos, sem notas, sem comentarios.\n\n"
    "2. FIDELIDADE TOTAL: Transcreva exatamente o que foi falado. "
    "Preserve interjeicoes ('ah', 'oh', 'hmm'), repeticoes, "
    "e palavras incompletas tal como foram pronunciadas.\n\n"
    "3. GLOSSARIO -- USO CONDICIONAL E RESTRITIVO: "
    "O glossario serve apenas para desfazer ambiguidades genuinas "
    "em trechos ininteligiveis do audio. REGRAS RIGOROSAS:\n"
    "   a) NUNCA substitua uma palavra que ja faz sentido no contexto -- "
    "mesmo que seja foneticamente semelhante a um termo do glossario.\n"
    "   b) Apenas substitua quando: (i) o audio e genuinamente ininteligivel E "
    "(ii) o termo do glossario faz sentido contextual PERFEITO.\n"
    "   c) Se houver qualquer duvida, NAO substitua. Mantenha o que foi ouvido.\n\n"
    "4. PONTUACAO: Adicione pontuacao natural baseada nas pausas "
    "e entonacao do audio. Nao reformule frases, nao mude ordem de palavras.\n\n"
    "5. PROIBIDO: Jamais responda com frases como 'Aqui esta a transcricao', "
    "'Claro', 'Segue abaixo', ou qualquer texto que nao seja a transcricao. "
    "A sua unica saida possivel e o texto do audio. Nada mais."
)


class TranscriptionError(Exception):
    """Raised when all available transcription backends fail."""


class Transcriber:
    """Routes transcription to Gemini or Groq based on mode and connectivity.

    Args:
        is_online_fn: Callable that returns True if internet is available.
                      Typically ``network_monitor.is_online``.
    """

    def __init__(self, is_online_fn: callable) -> None:  # type: ignore[valid-type]
        self._is_online_fn = is_online_fn

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def _is_long_audio(audio_path: Path, max_duration_sec: float = 600.0) -> bool:
        """Check if audio file exceeds max_duration_sec (default 10 minutes).

        Returns False if the file cannot be read — lets the backend handle errors.
        """
        try:
            import soundfile as sf

            info = sf.info(str(audio_path))
            return info.duration > max_duration_sec
        except Exception:
            return False

    def transcribe(
        self,
        audio_path: Path,
        prompt_text: str,
        keywords: list[str],
        mode: TranscriptionMode = "auto",
        on_chunk: callable = None,
        source: str = "mic",
    ) -> str:
        """Transcribe an audio file and return the resulting text.

        Args:
            audio_path:  Path to the WAV file to transcribe.
            prompt_text: The active prompt's instruction text (used by Gemini).
            keywords:    Glossary words (used by both backends differently).
            mode:        Transcription mode — "auto" | "gemini" | "groq".
            on_chunk:    Optional callback(chunk_text) for SSE streaming.

        Returns:
            Transcribed text string.

        Raises:
            TranscriptionError: If the selected backend fails and no fallback exists.
        """
        # Audio files longer than 10 minutes are always sent to Gemini,
        # regardless of the selected mode — Groq has a 25 MB file limit
        # and client-side chunking degrades quality.
        if self._is_long_audio(audio_path):
            print(
                f"[DEBUG] Transcriber: áudio longo (>10 min), redirecionando "
                f"para Gemini (modo={mode})"
            )
            if on_chunk:
                on_chunk(
                    "\n--- Transcrição via Google Gemini (áudio longo) ---\n\n"
                )
            return self._transcribe_gemini(audio_path, prompt_text, keywords, on_chunk, source)

        online = self._is_online_fn()
        if not online:
            raise TranscriptionError(
                "Nenhuma engine disponível (Offline). "
                "Tente novamente quando houver internet."
            )

        print(f"[INFO] Transcriber: solicitacao recebida | modo={mode} | source={source} | online={online}")

        if mode == "groq":
            print(f"[INFO] PROVEDOR SELECIONADO: Groq Whisper | source={source}")
            return self._transcribe_groq(audio_path, keywords, prompt_text, on_chunk)

        if mode == "gemini":
            print(f"[INFO] PROVEDOR SELECIONADO: Google Gemini | source={source}")
            return self._transcribe_gemini(audio_path, prompt_text, keywords, on_chunk, source)

        # mode == "auto" — Google é o provedor padrao, Groq é fallback
        print(f"[INFO] MODO AUTO: usando Google Gemini como padrao...")
        try:
            print(f"[INFO] PROVEDOR CHAMADO: Google Gemini | source={source}")
            return self._transcribe_gemini(audio_path, prompt_text, keywords, on_chunk, source)
        except TranscriptionError as exc:
            print(f"[WARN] Google Gemini falhou ({exc}), fallback para Groq Whisper")

        print(f"[INFO] PROVEDOR CHAMADO: Groq Whisper (fallback) | source={source}")
        return self._transcribe_groq(audio_path, keywords, prompt_text, on_chunk)

    # ------------------------------------------------------------------
    # Gemini backend
    # ------------------------------------------------------------------

    def _transcribe_gemini(
        self,
        audio_path: Path,
        prompt_text: str,
        keywords: list[str],
        on_chunk: callable = None,
        source: str = "mic",
    ) -> str:
        """Upload audio to Gemini Files API and request transcription.

        Uses generate_content_stream for word-by-word streaming via on_chunk.
        """
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise TranscriptionError(
                "google-genai nao instalado. Execute: uv add google-genai"
            ) from exc

        client = genai.Client(
            api_key=GOOGLE_API_KEY,
            http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT * 1000.0),
        )

        # Build system instruction combining prompt text and glossary
        system_instruction = self._build_system_instruction(prompt_text, keywords, source)

        # Upload the audio file to Files API (SDK >= 1.0 uses file=, not path=)
        print(f"[DEBUG] Gemini: iniciando upload do arquivo {audio_path.name}")
        try:
            uploaded_file = client.files.upload(file=str(audio_path))
            print(f"[DEBUG] Gemini: upload concluido -> {uploaded_file.name}")
        except Exception as exc:
            raise TranscriptionError(
                f"Falha ao fazer upload do audio: {exc}"
            ) from exc

        try:
            response_stream = client.models.generate_content_stream(
                model=GEMINI_MODEL,
                contents=[uploaded_file, "Audio transcription:"],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                ),
            )

            full_text_chunks = []
            for chunk in response_stream:
                if chunk and hasattr(chunk, "text") and chunk.text:
                    full_text_chunks.append(chunk.text)
                    if on_chunk:
                        on_chunk(chunk.text)

            final_text = "".join(full_text_chunks).strip()
            # Apply output filter to strip any chat-like artifacts
            final_text = _filter_transcription_output(final_text)
            print(
                f"[DEBUG] Gemini: transcricao concluida ({len(final_text)} chars)"
            )
            print(f"[INFO] Gemini: provedor finalizado com sucesso")
            return final_text

        except Exception as exc:
            from google.api_core.exceptions import DeadlineExceeded

            if isinstance(exc, DeadlineExceeded) or "504" in str(exc):
                raise TranscriptionError(
                    "A conexao expirou (504: DEADLINE_EXCEEDED)."
                ) from exc

            raise TranscriptionError(
                f"Erro na requisicao ao Gemini: {exc}"
            ) from exc
        finally:
            # Best-effort cleanup of the uploaded file
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception:
                pass

    @staticmethod
    def _build_system_instruction(prompt_text: str, keywords: list[str], source: str = "mic") -> str:
        """Combine hardcoded audio transcription prompt with optional DB context and glossary.

        Args:
            prompt_text: DB prompt text (used as domain context only).
            keywords: Glossary keywords for conditional correction.
            source: "mic" for microphone, "system" for system audio capture.
        """
        base = (
            GEMINI_SYSTEM_AUDIO_INSTRUCTION
            if source == "system"
            else GEMINI_SYSTEM_INSTRUCTION
        )
        parts = [base]

        if prompt_text:
            parts.append(
                "CONTEXTO ADICIONAL (apenas informacao de dominio -- "
                "as regras de transcricao acima sao absolutas):\n"
                f"{prompt_text}"
            )

        if keywords:
            parts.append(
                "GLOSSARIO (use APENAS conforme regra condicional 3 acima): "
                f"{', '.join(keywords)}."
            )

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Groq backend
    # ------------------------------------------------------------------

    def _transcribe_groq(
        self,
        audio_path: Path,
        keywords: list[str],
        prompt_text: str,
        on_chunk: callable = None,
    ) -> str:
        """Transcribe using Groq Whisper + review agent.

        Only called for files <= 10 minutes (longer audio is redirected to
        Gemini at the transcribe() routing layer). Groq returns full text
        in a single API call (non-streaming) — the result is delivered
        as a single chunk via on_chunk.
        """
        result = self._transcribe_groq_single(audio_path, keywords, prompt_text)
        if on_chunk:
            on_chunk(result)
        return result

    def _transcribe_groq_single(
        self,
        audio_path: Path,
        keywords: list[str],
        prompt_text: str,
    ) -> str:
        """Transcribe a single audio file with Groq Whisper (no chunking)."""
        print(f"[DEBUG] Groq: iniciando transcricao de {audio_path.name}")
        try:
            from groq import Groq
        except ImportError as exc:
            raise TranscriptionError(
                "groq nao instalado. Execute: uv add groq"
            ) from exc

        # Validate size for single chunk (should already be ≤25MB from routing)
        file_size_mb = audio_path.stat().st_size / (1024 * 1024)
        print(f"[DEBUG] Groq: tamanho do arquivo: {file_size_mb:.2f} MB")
        if audio_path.stat().st_size > 25 * 1024 * 1024:
            raise TranscriptionError(
                "Chunk muito grande para a API do Groq (> 25MB)."
            )

        client = Groq(api_key=GROQ_API_KEY)
        initial_prompt = ", ".join(keywords) if keywords else ""

        try:
            print(f"[DEBUG] Groq: chamando API Whisper-large-v3-turbo...")
            with open(audio_path, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=file,
                    model="whisper-large-v3-turbo",
                    prompt=initial_prompt,
                    response_format="text",
                    language="pt",
                    temperature=0.0,
                )
            raw_text = str(transcription).strip()
            print(f"[DEBUG] Groq: transcricao bruta obtida ({len(raw_text)} chars)")
        except Exception as exc:
            raise TranscriptionError(
                f"Erro na transcricao com Groq: {exc}"
            ) from exc

        # --- Review step: grammar / punctuation correction ---
        print("[DEBUG] Groq: chamando TranscriptionReviewAgent...")
        try:
            from app.agents import TranscriptionReviewAgent

            reviewer = TranscriptionReviewAgent()
            review_result = reviewer.review(
                transcribed_text=raw_text,
                keywords=keywords,
                prompt_text=prompt_text,
            )

            print(
                f"[DEBUG] Groq review: changes={review_result.has_changes}, "
                f"near_matches={review_result.near_matches}"
            )
            if review_result.diff_lines:
                print(
                    "[DEBUG] Groq diff:\n"
                    + "\n".join(review_result.diff_lines)
                )

            print(f"[INFO] Groq: provedor finalizado com sucesso ({len(review_result.corrected_text)} chars)")
            return review_result.corrected_text
        except Exception as exc:
            # Graceful degradation: if review fails, return raw transcription
            print(
                f"[DEBUG] Groq review failed ({exc}), usando texto bruto."
            )
            print(f"[INFO] Groq: provedor finalizado com sucesso (sem revisao, {len(raw_text)} chars)")
            return raw_text

    # ------------------------------------------------------------------
    # Title Generation
    # ------------------------------------------------------------------

    def generate_title(self, text: str) -> str:
        """Generate a short title (max 5 words) for a given text using Gemini."""
        if not self._is_online_fn():
            return "Nova Sessão"

        try:
            from google import genai
            from google.genai import types
        except ImportError:
            return "Nova Sessão"

        client = genai.Client(api_key=GOOGLE_API_KEY)

        system_instruction = (
            "Você é um assistente especialista em sumarização. "
            "Crie um título descritivo para este texto usando no máximo "
            "5 palavras. Produza apenas o título e nada mais. Não use aspas."
        )

        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[text],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                ),
            )
            return response.text.strip()
        except Exception as exc:
            print(f"[DEBUG] Gemini title generation failed: {exc}")
            return "Nova Sessão"
