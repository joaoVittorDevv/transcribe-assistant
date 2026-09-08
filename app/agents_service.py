"""app.agents_service — Interactive Conversational Meta-Agent & Rewrite Engine for MiniMax.

Features:
  1. Ephemeral Multi-Step Conversational Meta-Agent (Discovery interview -> Guardrails -> Pydantic Schema).
  2. Multi-turn Session Memory (stored per session_id and cleanly purged on close/reset).
  3. Real-Time Token & Reasoning Streaming for text rewrites with dynamic MiniMax models.
  4. Robust Pydantic Schemas for deterministic output validation.
"""

import json
import logging
import re
import threading
import urllib.request
from typing import Any, Dict, Generator, List, Optional
from pydantic import BaseModel, Field

import app.config as config
import app.database as db

logger = logging.getLogger("transcribe.agents_service")

# ---------------------------------------------------------------------------
# Structured Pydantic Schemas
# ---------------------------------------------------------------------------


class RewriteAgentSchema(BaseModel):
    """Deterministic Pydantic specification for a Rewrite Agent."""
    name: str = Field(..., description="Nome amigável e expressivo do agente (ex: 'Revisor Acadêmico Rigoroso')")
    slug: str = Field(..., description="Identificador único kebab-case (ex: 'revisor-academico-rigoroso')")
    icon: str = Field("✨", description="Emoji representativo único (ex: 🎓, 💬, 👔, 📋, ⚡, 📝, 🎯)")
    description: str = Field(..., description="Explicação sucinta do propósito e cenário de uso")
    system_prompt: str = Field(..., description="Instruções profundas de engenharia de prompt, guardrails e regras de reescrita")
    tone: str = Field("formal e acadêmico", description="Tom de comunicação (ex: acadêmico rigoroso, formal corporativo, humano e direto)")
    target_audience: str = Field("comunidade acadêmica", description="Público-alvo pretendido para as mensagens")
    remove_filler_words: bool = Field(True, description="Expurgar estritamente vícios de fala, hesitações e repetições orais")
    preserve_slang: bool = Field(False, description="Preservar gírias e coloquialismos")
    prefix_template: str = Field("", description="Saudação inicial fixa ou cabeçalho padrão, se houver")
    suffix_template: str = Field("", description="Assinatura corporativa ou despedida padrão, se houver")
    output_format: str = Field("markdown", description="Formato de saída: markdown, plain_text, email_blocks, action_items")
    provider: str = Field("minimax", description="Provedor LLM")
    model: str = Field("MiniMax-M2.7-highspeed", description="Modelo MiniMax ideal para a tarefa")
    temperature: float = Field(0.2, description="Temperatura de amostragem (0.1 a 0.5)")
    agent_type: str = Field(
        "no-check",
        description="Tipo de execução do agente: 'multi-check' (exige aprovação e loop iterativo de feedback antes de alterar o texto) ou 'no-check' (substituição direta do texto sem aprovação prévia)"
    )


# ---------------------------------------------------------------------------
# Meta-Architect Agent System Instructions
# ---------------------------------------------------------------------------

META_ARCHITECT_INSTRUCTIONS = """Você é o Arquiteto Sênior de Agentes de Inteligência Artificial do Transcribe Assistant.
Sua missão é entrevistar o usuário em etapas consultivas para entender a fundo o que ele precisa e projetar a melhor configuração de um Agente de Reescrita de Áudio/Texto.

COMO CONDUZIR A CONVERSA:
1. Seja acolhedor, profissional, analítico e direto. Comunique-se estritamente em Português.
2. Não faça todas as perguntas de uma vez só! Faça 1 ou no máximo 2 perguntas estratégicas por turno para não sobrecarregar o usuário.
3. Investigue 5 pilares essenciais:
   - Pilar 1: Cenário & Destinatário (Acadêmico/Artigo, WhatsApp/Slack rápido, E-mail corporativo, Ata de reunião, Documentação técnica).
   - Pilar 2: Tipo de Execução (MANDATÓRIO): Você DEVE perguntar especificamente se o agente será 'multi-check' ou 'no-check':
     * multi-check: O agente apresenta o texto reestruturado para revisão do usuário e permite solicitar ajustes iterativos quantas vezes forem necessárias antes de substituir definitivamente o texto no editor (ou rejeitar mantendo o original intacto). Indicado para tarefas complexas como acadêmico, relatórios e textos críticos.
     * no-check: O agente reestrutura e insere diretamente no editor sem necessidade de aprovação prévia. Indicado para mensagens do dia a dia.
   - Pilar 3: Tratamento de Fala & Formatação (Remover hesitações orais? Detectar comandos implícitos de formatação/pontuação? Adequar citações/siglas?).
   - Pilar 4: Tom, Guardrails & Restrições (O que o agente NUNCA pode fazer? Ex: não alterar o conteúdo factual, não omitir dados, manter fidelidade ao áudio).
   - Pilar 5: Formato de Saída & Templates (Markdown, Plain Text, se precisa de cabeçalho ou assinatura fixa).

QUANDO FINALIZAR:
Assim que você tiver respostas suficientes para esses pilares (ou quando o usuário der uma especificação completa, disser que já está bom, pedir para gerar ou disser 'pode gerar'):
1. Apresente um resumo cordial e elegante das diretrizes acordadas (destacando se é Multi-Check ou No-Check).
2. Emita NO FINAL DA RESPOSTA um bloco de código JSON obrigatório marcado com ```json ... ``` contendo a especificação completa e rigorosamente compatível com o schema abaixo:

```json
{
  "name": "Nome amigável",
  "slug": "identificador-kebab-case",
  "icon": "Emoji",
  "description": "Descrição sucinta",
  "system_prompt": "Prompt mestre ultra-completo, profundo e detalhado ensinando as regras de sintaxe, tom, conversão de citações/siglas e guardrails.",
  "tone": "tom principal",
  "target_audience": "público principal",
  "remove_filler_words": true,
  "preserve_slang": false,
  "prefix_template": "",
  "suffix_template": "",
  "output_format": "markdown",
  "provider": "minimax",
  "model": "MiniMax-M2.7-highspeed",
  "temperature": 0.2,
  "agent_type": "multi-check"
}
```

IMPORTANTE: O `system_prompt` que você gerar dentro do JSON deve ser uma obra-prima de engenharia de prompt, garantindo que o agente filho saiba exatamente como reestruturar o texto, interpretar comandos implícitos de formatação e manter fidelidade absoluta aos fatos falados.
"""

# ---------------------------------------------------------------------------
# Ephemeral Builder Session Manager (Thread-Safe & Pure Native)
# ---------------------------------------------------------------------------

_BUILDER_SESSIONS: Dict[str, List[Dict[str, str]]] = {}
_SESSIONS_LOCK = threading.Lock()


def _call_minimax_chat(
    messages: List[Dict[str, str]],
    model_name: str = "",
    temperature: float = 0.3,
    timeout_secs: int = 90,
) -> str:
    """Execute a chat completion with MiniMax API and return content."""
    config.load_all_settings()
    active_key = config.MINIMAX_API_KEY
    active_url = config.MINIMAX_BASE_URL or "https://api.minimax.io/v1"
    active_model = model_name or config.MINIMAX_MODEL or "MiniMax-M2.7-highspeed"

    if not active_key:
        raise ValueError("Chave de API MiniMax não configurada nas Configurações.")

    url = f"{active_url.rstrip('/')}/chat/completions"
    payload = {
        "model": active_model,
        "messages": messages,
        "temperature": temperature,
        "reasoning_split": True,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {active_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_secs) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            choices = res_json.get("choices", [])
            if not choices:
                raise ValueError("MiniMax retornou uma resposta vazia.")
            return choices[0].get("message", {}).get("content", "").strip()
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        logger.error("MiniMax HTTP Error %s: %s", e.code, err_msg)
        raise ValueError(f"Erro na API MiniMax ({e.code}): {err_msg}")
    except Exception as e:
        logger.error("Error communicating with MiniMax: %s", e)
        raise ValueError(f"Falha na comunicação com o Arquiteto MiniMax: {e}")


def start_builder_session(
    session_id: str,
    model_name: str = "",
    initial_agent: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Start or reset an ephemeral builder session and return initial greeting."""
    if initial_agent:
        system_instructions = (
            f"{META_ARCHITECT_INSTRUCTIONS}\n\n"
            "CONTEXTO DE EDIÇÃO/APERFEIÇOAMENTO:\n"
            "O usuário está solicitando a edição/refinamento de um agente existente.\n"
            f"Nome: {initial_agent.get('name', '')}\n"
            f"Ícone: {initial_agent.get('icon', '✨')}\n"
            f"Slug: {initial_agent.get('slug', '')}\n"
            f"Descrição: {initial_agent.get('description', '')}\n"
            f"Tipo: {initial_agent.get('agent_type', 'no-check')} (multi-check ou no-check)\n"
            f"Tom: {initial_agent.get('tone', '')}\n"
            f"Público: {initial_agent.get('target_audience', '')}\n"
            f"Limpeza de Fala: {initial_agent.get('remove_filler_words')}\n"
            f"Preservar Gírias: {initial_agent.get('preserve_slang')}\n"
            f"Formato: {initial_agent.get('output_format', 'markdown')}\n"
            f"Modelo: {initial_agent.get('model', 'MiniMax-M2.7-highspeed')}\n"
            f"Temperatura: {initial_agent.get('temperature', 0.2)}\n"
            f"System Prompt Atual:\n```\n{initial_agent.get('system_prompt', '')}\n```\n"
        )

        prompt_init = (
            f"Analise detalhadamente o agente '{initial_agent.get('name')}' com as especificações acima.\n"
            "1. Cumprimente o usuário amigavelmente e informe que carregou as diretrizes do agente para edição.\n"
            "2. Apresente um resumo claro e conciso das configurações atuais dele (destacando modo multi-check/no-check, tom e público).\n"
            "3. Sugira 2 a 3 melhorias pontuais ou oportunidades de refinamento técnico no prompt e nas regras.\n"
            "4. Pergunte abertamente o que o usuário deseja alterar, ajustar ou aprimorar."
        )

        initial_messages = [
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": prompt_init},
        ]

        greeting = _call_minimax_chat(initial_messages, model_name=model_name, temperature=0.3)

        with _SESSIONS_LOCK:
            _BUILDER_SESSIONS[session_id] = [
                {"role": "system", "content": system_instructions},
                {"role": "assistant", "content": greeting},
            ]
    else:
        greeting = (
            "Olá! Sou seu **Arquiteto de Agentes**. Estou aqui para criar com você um assistente sob medida "
            "para transformar e polir suas gravações e transcrições de voz.\n\n"
            "Para começarmos: **qual é o principal objetivo ou cenário de uso deste agente?**\n"
            "*(Exemplos: formatação acadêmica com citações/siglas, mensagens rápidas no Slack/WhatsApp, e-mails corporativos, atas de reuniões...)*"
        )

        with _SESSIONS_LOCK:
            _BUILDER_SESSIONS[session_id] = [
                {"role": "system", "content": META_ARCHITECT_INSTRUCTIONS},
                {"role": "assistant", "content": greeting},
            ]

    return {
        "session_id": session_id,
        "message": greeting,
        "is_complete": False,
        "agent_spec": None,
    }


def chat_builder_session(
    session_id: str,
    user_message: str,
    model_name: str = "",
) -> Dict[str, Any]:
    """Process a turn in the builder conversation with memory and check for completion."""
    with _SESSIONS_LOCK:
        history = _BUILDER_SESSIONS.get(session_id)
        if not history:
            history = [
                {"role": "system", "content": META_ARCHITECT_INSTRUCTIONS},
            ]
            _BUILDER_SESSIONS[session_id] = history

        # Append user turn
        history.append({"role": "user", "content": user_message})

    # Call MiniMax with full conversation history
    reply_content = _call_minimax_chat(history, model_name=model_name, temperature=0.3)

    with _SESSIONS_LOCK:
        history.append({"role": "assistant", "content": reply_content})

    # Check if a JSON block was emitted by the agent
    clean_reply = reply_content.strip()
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", clean_reply)

    agent_spec: Optional[Dict[str, Any]] = None
    is_complete = False

    if match:
        json_raw = match.group(1).strip()
        try:
            parsed_data = json.loads(json_raw)
            # Validate with Pydantic
            validated = RewriteAgentSchema.model_validate(parsed_data)
            agent_spec = validated.model_dump()
            is_complete = True

            # Clean conversational reply to remove the raw JSON block for a prettier chat UI
            reply_without_json = clean_reply[:match.start()].strip()
            if not reply_without_json:
                reply_without_json = "Perfeito! Compilei todas as diretrizes e gerei a especificação completa do seu agente abaixo para revisão."
            clean_reply = reply_without_json
        except Exception as err:
            logger.warn("JSON block found but failed validation: %s", err)

    return {
        "session_id": session_id,
        "reply": clean_reply,
        "is_complete": is_complete,
        "agent_spec": agent_spec,
    }


def reset_builder_session(session_id: str) -> None:
    """Completely purge session memory and drop the builder history."""
    with _SESSIONS_LOCK:
        if session_id in _BUILDER_SESSIONS:
            del _BUILDER_SESSIONS[session_id]
            logger.info("Builder session '%s' memory purged successfully.", session_id)


# ---------------------------------------------------------------------------
# Rewrite Execution Engine with Real-Time Reasoning & Token Streaming
# ---------------------------------------------------------------------------


def execute_rewrite_stream_agno(
    agent_id: int,
    text: str,
    model_override: str = "",
) -> Generator[Dict[str, Any], None, None]:
    """Execute text rewriting streaming typed events (reasoning, content, status) via SSE."""
    agent_row = db.get_rewrite_agent(agent_id)
    if not agent_row:
        raise ValueError(f"Agente ID {agent_id} não encontrado.")

    agent_db = dict(agent_row)
    config.load_all_settings()

    clean_text = text.strip()
    if not clean_text:
        return

    active_key = config.MINIMAX_API_KEY
    active_url = config.MINIMAX_BASE_URL or "https://api.minimax.io/v1"
    active_model = model_override or agent_db.get("model") or config.MINIMAX_MODEL or "MiniMax-M2.7-highspeed"

    if not active_key:
        raise ValueError("Chave de API MiniMax não configurada nas Configurações.")

    yield {"type": "status", "stage": "Analisando transcrição e mapeando tom...", "step": 1}

    # Build clear rules
    speech_rules = []
    if agent_db.get("remove_filler_words"):
        speech_rules.append(
            "- Remova estritamente vícios de linguagem orais, hesitações ('ehhh', 'ahhh', 'tipo assim', 'né', 'sabe', 'então', repetições) e gaguejos."
        )
    if not agent_db.get("preserve_slang"):
        speech_rules.append(
            "- Substitua gírias e expressões excessivamente informais por termos neutros e claros condizentes com o tom solicitado."
        )
    speech_rules.append(f"- Tom desejado: {agent_db.get('tone', 'equilibrado e claro')}.")
    speech_rules.append(f"- Público-alvo: {agent_db.get('target_audience', 'geral')}.")
    output_fmt = agent_db.get('output_format', 'markdown')
    speech_rules.append(f"- Formato de saída: {output_fmt}.")
    if output_fmt == 'markdown':
        speech_rules.append(
            "- Estruture a resposta com formatação Markdown limpa e legível: use títulos (ex: ## Seção), listas (com marcadores '-' ou numéricas '1.') e quebras de linha duplas (duplo ENTER) entre parágrafos e tópicos distintos."
        )
    else:
        speech_rules.append("- Use quebras de linha duplas para separar parágrafos distintos.")

    system_content = (
        f"{agent_db.get('system_prompt', '')}\n\n"
        "DIRETRIZES DE REGRAS E ESTILO:\n" + "\n".join(speech_rules) + "\n\n"
        "REGRAS MANDATÓRIAS DE SAÍDA:\n"
        "1. Inicie sua resposta DIRETAMENTE na primeira linha com a primeira palavra do texto reescrito.\n"
        "2. PROIBIDO qualquer introdução como 'Aqui está o seu texto:' ou conclusões meta.\n"
        "3. PROIBIDO expor pensamentos, monólogos ou rascunhos internos no corpo do texto.\n"
        "4. Retorne APENAS o texto polido e formatado pronto para uso."
    )

    url = f"{active_url.rstrip('/')}/chat/completions"
    payload = {
        "model": active_model,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"Texto original da transcrição para reestruturar:\n\n{clean_text}"},
        ],
        "temperature": float(agent_db.get("temperature", 0.3)),
        "stream": True,
        "reasoning_split": True,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {active_key}",
        },
        method="POST",
    )

    yield {"type": "status", "stage": "Raciocinando estrutura e sintetizando texto...", "step": 2}

    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            for line in response:
                decoded = line.decode("utf-8").strip()
                if not decoded or not decoded.startswith("data:"):
                    continue
                data_str = decoded[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk_json = json.loads(data_str)
                    choices = chunk_json.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})

                        # 1. Yield reasoning delta if emitted
                        reasoning_chunk = delta.get("reasoning_content", "")
                        if reasoning_chunk:
                            yield {"type": "reasoning", "chunk": reasoning_chunk}

                        # 2. Yield main content chunk
                        content_chunk = delta.get("content", "")
                        if content_chunk:
                            yield {"type": "content", "chunk": content_chunk}
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.error("Error during MiniMax reasoning stream: %s", e)
        yield {"type": "error", "error": str(e)}


def execute_rewrite_agno(
    agent_id: int,
    text: str,
    model_override: str = "",
) -> Dict[str, Any]:
    """Execute complete rewrite without streaming and apply templates."""
    agent_row = db.get_rewrite_agent(agent_id)
    if not agent_row:
        raise ValueError(f"Agente ID {agent_id} não encontrado.")

    agent_db = dict(agent_row)
    content_chunks = []
    reasoning_chunks = []

    for ev in execute_rewrite_stream_agno(agent_id, text, model_override):
        if ev.get("type") == "content":
            content_chunks.append(ev.get("chunk", ""))
        elif ev.get("type") == "reasoning":
            reasoning_chunks.append(ev.get("chunk", ""))

    rewritten_text = "".join(content_chunks).strip()
    reasoning_text = "".join(reasoning_chunks).strip()

    # Apply templates if configured and not already present
    prefix = (agent_db.get("prefix_template") or "").strip()
    suffix = (agent_db.get("suffix_template") or "").strip()

    if prefix and not rewritten_text.lower().startswith(prefix.lower()):
        rewritten_text = f"{prefix}\n\n{rewritten_text}"

    if suffix and not rewritten_text.lower().endswith(suffix.lower()):
        rewritten_text = f"{rewritten_text}\n\n{suffix}"

    return {
        "rewritten_text": rewritten_text,
        "reasoning": reasoning_text,
        "original_text": text.strip(),
        "agent_name": agent_db["name"],
        "agent_icon": agent_db.get("icon", "✨"),
    }


def execute_rewrite_feedback_stream(
    agent_id: int,
    original_text: str,
    current_draft: str,
    feedback: str,
    model_override: str = "",
) -> Generator[Dict[str, Any], None, None]:
    """Execute text refinement based on user feedback on a previous draft via SSE."""
    agent_row = db.get_rewrite_agent(agent_id)
    if not agent_row:
        raise ValueError(f"Agente ID {agent_id} não encontrado.")

    agent_db = dict(agent_row)
    config.load_all_settings()

    active_key = config.MINIMAX_API_KEY
    active_url = config.MINIMAX_BASE_URL or "https://api.minimax.io/v1"
    active_model = model_override or agent_db.get("model") or config.MINIMAX_MODEL or "MiniMax-M2.7-highspeed"

    if not active_key:
        raise ValueError("Chave de API MiniMax não configurada nas Configurações.")

    yield {"type": "status", "stage": "Analisando seu feedback e ajustando o texto...", "step": 1}

    speech_rules = []
    if agent_db.get("remove_filler_words"):
        speech_rules.append("- Remova estritamente vícios de linguagem orais, hesitações e repetições.")
    if not agent_db.get("preserve_slang"):
        speech_rules.append("- Mantenha tom neutro e adequado ao público pretendido.")
    speech_rules.append(f"- Tom: {agent_db.get('tone', 'equilibrado')}.")
    output_fmt = agent_db.get('output_format', 'markdown')
    speech_rules.append(f"- Formato: {output_fmt}.")
    if output_fmt == 'markdown':
        speech_rules.append(
            "- Estruture a resposta com formatação Markdown limpa e legível: use títulos (ex: ## Seção), listas (com marcadores '-' ou numéricas '1.') e quebras de linha duplas entre parágrafos e tópicos distintos."
        )
    else:
        speech_rules.append("- Use quebras de linha duplas para separar parágrafos distintos.")

    system_content = (
        f"{agent_db.get('system_prompt', '')}\n\n"
        "DIRETRIZES DE REGRAS E ESTILO:\n" + "\n".join(speech_rules) + "\n\n"
        "REGRAS DE ITERAÇÃO E FEEDBACK:\n"
        "1. Você receberá o texto original da fala, o rascunho anterior e os pedidos de ajuste do usuário.\n"
        "2. Aplique estritamente as correções e preferências solicitadas pelo usuário sobre o rascunho anterior.\n"
        "3. Não invente fatos fora do texto original, a menos que expressamente solicitado no feedback do usuário.\n"
        "4. Inicie sua resposta DIRETAMENTE na primeira linha com a primeira palavra do texto reescrito.\n"
        "5. Retorne APENAS o texto polido pronto para uso, sem comentários introdutórios."
    )

    user_content = (
        f"--- TEXTO ORIGINAL DA TRANSCRIÇÃO ---\n{original_text.strip()}\n\n"
        f"--- RASCUNHO GERADO ANTERIORMENTE ---\n{current_draft.strip()}\n\n"
        f"--- AJUSTES SOLICITADOS PELO USUÁRIO (FEEDBACK) ---\n{feedback.strip()}\n\n"
        "Por favor, refine o texto aplicando os ajustes acima:"
    )

    url = f"{active_url.rstrip('/')}/chat/completions"
    payload = {
        "model": active_model,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        "temperature": float(agent_db.get("temperature", 0.2)),
        "stream": True,
        "reasoning_split": True,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {active_key}",
        },
        method="POST",
    )

    yield {"type": "status", "stage": "Sintetizando nova versão revisada...", "step": 2}

    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            for line in response:
                decoded = line.decode("utf-8").strip()
                if not decoded or not decoded.startswith("data:"):
                    continue
                data_str = decoded[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk_json = json.loads(data_str)
                    choices = chunk_json.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})

                        reasoning_chunk = delta.get("reasoning_content", "")
                        if reasoning_chunk:
                            yield {"type": "reasoning", "chunk": reasoning_chunk}

                        content_chunk = delta.get("content", "")
                        if content_chunk:
                            yield {"type": "content", "chunk": content_chunk}
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.error("Error during rewrite feedback stream: %s", e)
        yield {"type": "error", "error": str(e)}
