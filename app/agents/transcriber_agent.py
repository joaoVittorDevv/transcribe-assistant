"""app.agents.transcriber_agent — Agente Agno para transcrição de áudio.

Encapsula a lógica de transcrição via Gemini dentro de um Agente Agno,
possibilitando futura expansão com ferramentas (sumarização, tradução, etc).

O upload do áudio para a Files API do Google é feito externamente (pré-processamento).
O Agente recebe a referência do arquivo já enviado e retorna o stream de transcrição.

Usage (async streaming):
    agent = create_transcription_agent(prompt_text, keywords)
    async for event in await agent.arun("Transcreva o audio", stream=True, files=[...]):
        if event.event == "RunContent":
            print(event.content)
"""

import asyncio
from pathlib import Path
from typing import AsyncIterator

from agno.agent import Agent, RunOutputEvent
from agno.media import File as AgnoFile
from agno.models.google.gemini import Gemini

from app.config import GEMINI_MODEL, GOOGLE_API_KEY, GEMINI_TIMEOUT


def _build_system_instruction(prompt_text: str, keywords: list[str]) -> str:
    """Combine prompt text and glossary into a Gemini system instruction."""
    parts = []
    if prompt_text:
        parts.append(prompt_text)
    if keywords:
        glossary_line = (
            "Glossario de termos especificos que podem aparecer na transcricao "
            f"(use a grafia correta): {', '.join(keywords)}."
        )
        parts.append(glossary_line)
    parts.append("Produza apenas o texto transcrito, sem comentarios adicionais.")
    return "\n\n".join(parts)


def create_transcription_agent(
    prompt_text: str = "",
    keywords: list[str] | None = None,
) -> Agent:
    """Factory: cria um agente Agno configurado para transcrição.

    Args:
        prompt_text: Instrução do prompt ativo (System Instruction).
        keywords: Glossário de termos para precisão ortográfica.

    Returns:
        Um agente Agno pronto para receber áudio via .arun().
    """
    system_instruction = _build_system_instruction(prompt_text, keywords or [])

    model = Gemini(
        id=GEMINI_MODEL,
        api_key=GOOGLE_API_KEY,
        timeout=GEMINI_TIMEOUT,
    )

    agent = Agent(
        name="TranscriberAgent",
        model=model,
        description="Especialista em processamento de linguagem falada.",
        instructions=[system_instruction],
        markdown=False,
    )

    return agent


async def upload_audio_async(audio_path: Path) -> "google.genai.types.File":
    """Upload assíncrono do áudio para a Gemini Files API.

    Executa o upload síncrono do google-genai dentro de asyncio.to_thread
    para não bloquear o event loop do Flet.

    Args:
        audio_path: Caminho para o arquivo WAV.

    Returns:
        A referência do arquivo no servidor (para usar em generate_content).
    """
    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=GOOGLE_API_KEY,
        http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT * 1000.0),
    )

    uploaded = await asyncio.to_thread(
        client.files.upload, file=str(audio_path)
    )
    return uploaded


async def delete_uploaded_file(uploaded_file) -> None:
    """Remove o arquivo temporário do Gemini Files API sem bloquear."""
    try:
        from google import genai

        client = genai.Client(api_key=GOOGLE_API_KEY)
        await asyncio.to_thread(client.files.delete, name=uploaded_file.name)
    except Exception:
        pass


async def transcribe_stream(
    agent: Agent,
    uploaded_file,
) -> AsyncIterator[str]:
    """Executa a transcrição via Agente em stream e yields texto puro.

    Args:
        agent: O agente Agno criado por create_transcription_agent().
        uploaded_file: Referência do arquivo na Gemini Files API (google.genai.types.File).

    Yields:
        Fragmentos de texto transcrito conforme chegam da LLM.
    """
    from agno.media import File as AgnoFile

    # Usa o campo `external` para passar o GeminiFile diretamente.
    # O Agno Gemini model reconhece esse objeto e chama Part.from_uri()
    # com o URI e mime_type corretos (linhas 1079-1081 do gemini.py).
    audio_ref = AgnoFile(external=uploaded_file)

    stream = agent.arun(
        input="Transcreva o audio acima com precisao.",
        stream=True,
        files=[audio_ref],
    )

    async for event in stream:
        if hasattr(event, "event") and event.event == "RunContent":
            if hasattr(event, "content") and event.content:
                yield str(event.content)
