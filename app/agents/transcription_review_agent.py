"""app/agents/transcription_review_agent.py - Direct Groq API transcription review agent.

Transcription review using direct Groq Chat Completions API (no Agno middleware).
Corrects grammar, applies punctuation, and formats technical terms preserving
100% of spoken content.

Bug fix (Phase 2): Replaced Agno Agent framework with direct Groq API call
to prevent conversational context injection. Added output filter to strip
any remaining chat-like prefixes/suffixes.
"""

from __future__ import annotations

import re
import difflib
from dataclasses import dataclass, field

from groq import Groq

from app.config import GROQ_API_KEY, GROQ_REVIEW_MODEL


# ---------------------------------------------------------------------------
# System prompt - FIXED, NEVER from DB
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "Voce e um Motor de Revisao Textual e Transcricao. "
    "Seu trabalho e APENAS corrigir gramatica e pontuacao de transcricoes de audio.\n\n"
    "REGRAS DE OURO - SIGA TODAS SEM EXCECAO:\n\n"
    "1. SAIDA EXCLUSIVA: Voce DEVE retornar APENAS e SOMENTE o texto corrigido. "
    "NADA mais. Sem prefixos, sem sufixos, sem notas, sem comentarios, sem titulos, "
    "sem listas, sem bullet points, sem separadores, sem aspas decorativas. "
    "O texto de saida deve ser texto plano puro - sem formatacao alguma.\n\n"
    "2. PRESERVACAO TOTAL: O texto de saida DEVE conter TODAS as palavras do texto de entrada. "
    "Nao remova NENHUMA palavra, nem interjeicoes ('ah', 'oh', 'hmm'), nem repeticoes, "
    "nem palavras incompletas. Se o texto de entrada diz 'ah ah teste teste', "
    "a saida deve ter 'ah ah teste teste'.\n\n"
    "3. GLOSSARIO - USO CONDICIONAL E RESTRITIVO: O glossario serve apenas para desfazer "
    "ambiguedades genuinas em palavras ininteligiveis. REGRAS RIGOROSAS:\n"
    "   a) NUNCA substitua uma palavra que ja faz sentido perfeito no contexto - "
    "mesmo que seja foneticamente semelhante a um termo do glossario.\n"
    "   b) 'rato' em um trava-lingua e OBVIOUSMENTE 'rato', nao 'Reqflow'. "
    "Deixe como 'rato'.\n"
    "   c) Apenas substitua quando: (i) a palavra original e genuinamente incompreensivel E "
    "(ii) o termo do glossario faz sentido contextual PERFEITO E "
    "(iii) a substituicao resultaria em uma frase coerente.\n"
    "   d) Se houver qualquer duvida se a substituicao faz sentido, NAO substitua.\n\n"
    "4. PONTUACAO: Apenas adicione pontuacao. "
    "Nao reformule frases, nao mude ordem de palavras, nao altere o sentido.\n\n"
    "5. CONVERSAO TIPOGRAFICA: Comandos verbais de pontuacao DEVEM virar simbolos: "
    "'underline'->'_', 'ponto'->'.', 'virgula'->',', 'hifen'->'-', "
    "'traco'->'-', 'barra'->'/', 'aspas'->'\"'"
)

# ---------------------------------------------------------------------------
# Output filter — strips chat-like prefixes/suffixes from LLM responses
# ---------------------------------------------------------------------------

# Patterns that match conversational prefixes the LLM may prepend
_CONVERSATIONAL_PREFIXES = [
    # Portuguese
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
    # English (model may respond in English despite Portuguese prompt)
    r"^Here is the (?:corrected|reviewed) (?:text|transcription)[:]\s*",
    r"^Sure[!,.]?\s*(?:here(?:'s| you go))?[:]?\s*",
    r"^Of course[!,.]?\s*[:]?\s*",
    r"^The (?:corrected|reviewed) (?:text|transcription)(?: is)?[:]\s*",
]

# Patterns for conversational suffixes
_CONVERSATIONAL_SUFFIXES = [
    r"\n*(?:Espero que|I hope).*(?:ajude|help).*[.!]?\s*$",
    r"\n*Let me know if.*$",
    r"\n*(?:Qualquer|Any|Se).*(?:d[uú]vida|question|precisar).*$",
]

# Boundary markers the LLM may wrap the text in
_STRIP_MARKERS = [
    ('"', '"'),
    ("'", "'"),
    ("'''", "'''"),
    ('"""', '"""'),
    ("```", "```"),
]


def _filter_output(text: str) -> str:
    """Strip conversational prefixes, suffixes, and wrapping from LLM output.

    This is a safety net — the system prompt should prevent these, but if
    the model still responds conversationally, we strip it here rather than
    showing chat text to the user.
    """
    if not text:
        return text

    cleaned = text.strip()

    # Strip known conversational prefixes (most specific first)
    for pattern in _CONVERSATIONAL_PREFIXES:
        cleaned = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE).strip()

    # Strip known conversational suffixes
    for pattern in _CONVERSATIONAL_SUFFIXES:
        cleaned = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE).strip()

    # Strip wrapping quotes/code fences
    for open_marker, close_marker in _STRIP_MARKERS:
        if cleaned.startswith(open_marker) and cleaned.endswith(close_marker):
            inner = cleaned[len(open_marker):-len(close_marker) or None].strip()
            # Only strip if inner text is non-empty and the markers are real wrappers
            if inner and open_marker not in inner and close_marker not in inner:
                cleaned = inner

    return cleaned


# ---------------------------------------------------------------------------
# Result dataclass - same interface as legacy for compatibility
# ---------------------------------------------------------------------------


@dataclass
class ReviewResult:
    corrected_text: str
    has_changes: bool
    near_matches: list[str] = field(default_factory=list)
    diff_lines: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class TranscriptionReviewAgent:
    """Transcription review using direct Groq Chat Completions API.

    Uses direct API call (no Agno framework) to prevent conversational
    context injection. Includes output filter as safety net.
    """

    def __init__(self) -> None:
        self._client = Groq(api_key=GROQ_API_KEY)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def review(
        self,
        transcribed_text: str,
        keywords: list[str],
        prompt_text: str = "",
    ) -> ReviewResult:
        """Review and correct a transcribed text.

        Parameters
        ----------
        transcribed_text:
            Raw transcription to review.
        keywords:
            List of known terms (used for near-match flagging).
        prompt_text:
            Accepted but ignored. System prompt is fixed and hardcoded.

        Returns
        -------
        ReviewResult
            Contains corrected_text, has_changes, near_matches, and diff_lines.
        """
        # Build user message with glossary
        glossary_str = ", ".join(keywords) if keywords else "Nenhum"
        user_message = (
            "GLOSSARIO DE TERMOS: "
            + glossary_str
            + "\n\n"
            "TEXTO BRUTO PARA REVISAR:\n"
            + transcribed_text
        )

        # Run via direct Groq Chat Completions API (no Agno middleware)
        try:
            response = self._client.chat.completions.create(
                model=GROQ_REVIEW_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,
            )
            raw_output = response.choices[0].message.content or ""
            # Apply output filter to strip any chat-like artifacts
            corrected = _filter_output(raw_output)
            if not corrected:
                corrected = transcribed_text
        except Exception as exc:
            # Graceful degradation: if review fails, return raw transcription
            import sys

            print(
                f"[DEBUG] TranscriptionReviewAgent failed ({exc}), usando texto bruto.",
                file=sys.stderr,
            )
            corrected = transcribed_text

        # Compute near-matches and diff
        near_matches = self._find_near_matches(corrected, keywords)
        diff_lines = self._build_diff(transcribed_text, corrected)
        has_changes = corrected.strip() != transcribed_text.strip()

        return ReviewResult(
            corrected_text=corrected,
            has_changes=has_changes,
            near_matches=near_matches,
            diff_lines=diff_lines,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _find_near_matches(text: str, glossary: list[str]) -> list[str]:
        """Return glossary terms that are close to a word in text.

        Flags terms that appear as a near-miss (ratio >= 0.8) so the reviewer
        can manually check whether the correct term was used.
        """
        if not glossary:
            return []

        words_in_text = set(re.findall(r"\b\w+\b", text.lower()))
        flagged: list[str] = []

        for term in glossary:
            term_lower = term.lower()
            for word in words_in_text:
                if (
                    word != term_lower
                    and difflib.SequenceMatcher(None, word, term_lower).ratio() >= 0.8
                ):
                    flagged.append(term)
                    break

        return flagged

    @staticmethod
    def _build_diff(original: str, corrected: str) -> list[str]:
        """Return a human-readable unified-diff showing what changed."""
        original_lines = original.splitlines(keepends=True)
        corrected_lines = corrected.splitlines(keepends=True)
        diff = difflib.unified_diff(
            original_lines,
            corrected_lines,
            fromfile="Original",
            tofile="Corrigido",
            lineterm="",
        )
        return list(diff)
