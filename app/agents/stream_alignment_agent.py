"""app.agents.stream_alignment_agent — Groq Llama agent for streaming transcription text alignment.

Aligns sequential overlapping audio transcription chunks, removes duplication,
and performs dynamic contextual re-punctuation ("Look-Ahead").
"""

from groq import Groq
from app.config import GROQ_API_KEY, GROQ_REVIEW_MODEL


SYSTEM_PROMPT = (
    "Você é um motor de alinhamento e re-pontuação para transcrição de áudio em tempo real (Streaming ASR).\n"
    "Seu trabalho é fundir uma transcrição bruta recente com o histórico de texto já consolidado, "
    "eliminando duplicações e sobreposições causadas pela janela deslizante do áudio, "
    "e ajustar a pontuação dinamicamente (Look-Ahead).\n\n"
    "REGRAS CRÍTICAS E ABSOLUTAS:\n"
    "1. PRESERVAÇÃO DO CONTEÚDO: Mantenha todas as palavras ditas. Não tente embelezar, "
    "resumir ou remover termos, exceto repetições exatas geradas por sobreposição acústica.\n"
    "2. ALINHAMENTO DE OVERLAP: A transcrição recente contém palavras que já estão no final do histórico. "
    "Identifique a sobreposição fonética, elimine-a e anexe apenas as palavras novas.\n"
    "3. RE-PONTUAÇÃO DINÂMICA (LOOK-AHEAD): Se o histórico consolidado termina com uma pontuação provisória "
    "(como ponto final ou vírgula) e a nova transcrição mostra que a frase continua, "
    "remova a pontuação antiga para unificar a frase logicamente.\n"
    "4. FORMATO DE SAÍDA: Retorne APENAS o texto fundido final. "
    "Sem comentários, sem notas explicativas, sem marcações markdown de chat. Saída limpa de texto plano."
)

FEW_SHOT_EXAMPLES = (
    "Exemplo 1:\n"
    "Histórico consolidado: \"eu gostaria de agradecer a presença\"\n"
    "Novo chunk bruto: \"agradecer a presença de todos vocês nessa tarde\"\n"
    "Saída esperada: \"eu gostaria de agradecer a presença de todos vocês nessa tarde\"\n\n"
    "Exemplo 2:\n"
    "Histórico consolidado: \"vamos iniciar o projeto. Hoje vamos\"\n"
    "Novo chunk bruto: \"projeto hoje vamos analisar o código-fonte\"\n"
    "Saída esperada: \"vamos iniciar o projeto hoje vamos analisar o código-fonte\"\n"
)


class StreamAlignmentAgent:
    """Agent that aligns overlapping streaming ASR chunks and applies dynamic look-ahead re-punctuation."""

    def __init__(self) -> None:
        self._client = Groq(api_key=GROQ_API_KEY)

    def align(self, consolidated_history: str, new_chunk_text: str) -> str:
        """Align overlapping chunk text with the history and return the merged text.

        If consolidated_history is empty, returns new_chunk_text.
        If API fails, falls back to simple concatenation to guarantee service continuity.
        """
        consolidated = (consolidated_history or "").strip()
        new_chunk = (new_chunk_text or "").strip()

        if not consolidated:
            return new_chunk
        if not new_chunk:
            return consolidated

        user_message = (
            f"{FEW_SHOT_EXAMPLES}\n"
            f"--- TAREFA REAL ---\n"
            f"Histórico consolidado: \"{consolidated}\"\n"
            f"Novo chunk bruto: \"{new_chunk}\"\n"
            f"Saída esperada:"
        )

        try:
            response = self._client.chat.completions.create(
                model=GROQ_REVIEW_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,
            )
            aligned_text = response.choices[0].message.content or ""
            aligned_text = aligned_text.strip()
            
            # Remove quotes if the LLM wrapped the output in them
            if aligned_text.startswith('"') and aligned_text.endswith('"'):
                aligned_text = aligned_text[1:-1].strip()

            if not aligned_text:
                return f"{consolidated} {new_chunk}"
                
            return aligned_text

        except Exception as exc:
            import sys
            print(
                f"[DEBUG] StreamAlignmentAgent failed ({exc}), falling back to simple concatenation.",
                file=sys.stderr,
            )
            # Simple word-level overlap elimination fallback if LLM is offline/slow
            return self._fallback_align(consolidated, new_chunk)

    @staticmethod
    def _fallback_align(history: str, chunk: str) -> str:
        """Simple deterministic fallback for overlap alignment when LLM is unavailable."""
        history_words = history.split()
        chunk_words = chunk.split()

        if not history_words:
            return chunk
        if not chunk_words:
            return history

        # Try to find a matching suffix/prefix overlap sequence of words
        max_overlap = min(len(history_words), len(chunk_words))
        for overlap_size in range(max_overlap, 0, -1):
            suffix = history_words[-overlap_size:]
            prefix = chunk_words[:overlap_size]
            if [w.lower().strip(".,?!") for w in suffix] == [w.lower().strip(".,?!") for w in prefix]:
                # Found overlap, merge them using chunk's casing and punctuation
                merged = history_words[:-overlap_size] + chunk_words
                return " ".join(merged)

        # No overlap found, concatenate with a space
        return f"{history} {chunk}"
