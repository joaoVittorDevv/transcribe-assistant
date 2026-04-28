"""app/agents/transcription_review_agent.py - Agno-powered transcription review agent.

Transcription review agent using the Agno framework with Groq model.
Corrects grammar, applies punctuation, and formats technical terms preserving
100% of spoken content.
"""

from __future__ import annotations

import re
import difflib
from dataclasses import dataclass, field

from agno.agent import Agent
from agno.models.groq import Groq

from app.config import GROQ_API_KEY, GROQ_REVIEW_MODEL
from app.database import get_keywords_by_prompt


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

EXPECTED_OUTPUT = (
    "Retorne APENAS o texto corrigido - texto plano, sem aspas, sem comentarios, "
    "sem notas, sem titulos, sem separadores. Exatamente como este exemplo:\n\n"
    "Alo, alo, testando, o audio esta funcionando corretamente.\n\n"
    "Nada mais alem do texto corrigido."
)


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
    """Agno-based transcription review agent using Groq."""

    def __init__(self) -> None:
        self._agent = Agent(
            model=Groq(id=GROQ_REVIEW_MODEL, api_key=GROQ_API_KEY),
            instructions=SYSTEM_PROMPT,
            expected_output=EXPECTED_OUTPUT,
            markdown=False,
            add_datetime_to_context=False,
        )

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
            Ignored - system prompt is fixed (never from DB).
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
            "GLOSSARIO DE TERMOS: " + glossary_str + "\n\n"
            "TEXTO BRUTO PARA REVISAR:\n" + transcribed_text
        )

        # Run agent and get response
        try:
            response = self._agent.run(user_message)
            corrected = response.content if response.content else transcribed_text
        except Exception as exc:
            # Graceful degradation: if review fails, return raw transcription
            import sys
            print(f"[DEBUG] TranscriptionReviewAgent failed ({exc}), usando texto bruto.", file=sys.stderr)
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
