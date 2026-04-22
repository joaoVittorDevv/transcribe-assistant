"""app/agents/text_reviewer_agent.py — Groq-powered grammar/punctuation review agent.

This agent receives transcribed text and corrects grammar and punctuation using
the Groq ``llama-3.1-8b-instant`` model.  It also checks each word against a
keyword glossary (if provided) to flag near-matches that may be misspellings of
technical terms.

Approval loop
-------------
If the correction introduces any change, it is submitted for QA review.
If no changes were needed the result is submitted directly for Tech Lead approval.
After every revision cycle the agent posts a status comment back to the issue.

Parameters
----------
transcribed_text : str
    The raw transcription to be reviewed.
keywords : list[str]
    Glossary of known terms.  Near-matches in the corrected text are flagged.
issue_id : str
    Paperclip issue id — used to post review comments.
"""

from __future__ import annotations

import re
import difflib
from dataclasses import dataclass, field

from app.config import GROQ_API_KEY, GROQ_REVIEW_MODEL

try:
    from groq import Groq
except ImportError:  # pragma: no cover — gracefully degrade when groq is absent
    Groq = None  # type: ignore


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Você é um revisor de transcrições especialista em português brasileiro.
Sua tarefa é analisar o texto transcrito e produzir uma versão corrigida com:

1. **Gramática e ortografia** — corrija erros de português;
2. **Pontuação** — adicione vírgulas, pontos, dois-pontos, ponto e vírgula e outros sinais conforme as regras da língua portuguesa;
3. **Formatação** — separe parágrafos quando houver mudança de ideia; use iniciais maiúsculas quando necessário;
4. **Completude** — não omita palavras spoken in the audio; se algo foi dito, inclua-o.
5. **Glossário** — quando termos do glossário forem relevantes para o contexto, use-os corretamente no texto corrigido.

REGRAS IMPORTANTES:
- Preserve fielmente o conteúdo semântico do que foi dito. Não resuma, não generalize.
- Nunca invente ou altere o sentido original.
- Mantenha a grafia de termos técnicos e nomes próprios.
- O texto deve ser devolvido APENAS como texto corrigido, sem comentários, sem aspas, sem marcadores.
- Se o texto original já estiver correto e pontuado, devolva-o idêntico.
- Quando o usuário fornecer diretrizes específicas, respeite-as fielmente na correção.
"""


@dataclass
class ReviewResult:
    corrected_text: str
    has_changes: bool
    near_matches: list[str] = field(default_factory=list)
    diff_lines: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class TextReviewerAgent:
    """Review transcribed text using Groq ``llama-3.1-8b-instant``."""

    MODEL = GROQ_REVIEW_MODEL

    def __init__(self) -> None:
        if Groq is None:
            raise RuntimeError(
                "A biblioteca 'groq' não está instalada. "
                "Execute: uv add groq"
            )
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
        """Correct and punctuate the given transcription.

        Parameters
        ----------
        transcribed_text:
            Raw transcription to review.
        keywords:
            List of known terms (used for near-match flagging).
        prompt_text:
            User-defined system instruction (guidelines/context from DB).

        Returns
        -------
        ReviewResult
            Contains ``corrected_text``, ``has_changes``, ``near_matches``,
            and ``diff_lines``.
        """
        corrected = self._call_llm(transcribed_text, keywords, prompt_text)
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

    def _call_llm(self, text: str, keywords: list[str], prompt_text: str) -> str:
        """Send text to Groq and return the corrected version."""
        user_content_parts = []

        if prompt_text:
            user_content_parts.append(f"DIRETRIZES DO USUÁRIO:\n{prompt_text}")

        user_content_parts.append(
            f"TERMOS DO GLOSSÁRIO: {', '.join(keywords) if keywords else 'Nenhum'}"
        )

        user_content_parts.append(f"TEXTO PARA REVISAR:\n{text}")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "\n\n".join(user_content_parts),
            },
        ]

        response = self._client.chat.completions.create(
            messages=messages,
            model=self.MODEL,
            temperature=0.1,
            max_tokens=4096,
        )

        return response.choices[0].message.content or text  # type: ignore[union-attr]

    @staticmethod
    def _find_near_matches(text: str, glossary: list[str]) -> list[str]:
        """Return glossary terms that are close to a word in ``text``.

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
