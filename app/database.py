"""app.database — SQLite persistence layer.

Handles schema initialization and all CRUD operations for the three tables:
  - prompts       : user-defined transcription instructions
  - palavras_chave: glossary keywords linked to a prompt
  - sessions      : transcription history (incremental sessions)

All functions open/close their own connection for thread safety.
The database file path is taken from app.config.DATABASE_PATH.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Generator

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------


@contextmanager
def _connect() -> Generator[sqlite3.Connection, None, None]:
    """Yield a database connection with row_factory and foreign key support."""
    from app.config import DATABASE_PATH
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def initialize_db() -> None:
    """Create all tables if they do not exist yet."""
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                chave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS prompts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                nome         TEXT    NOT NULL,
                texto_prompt TEXT    NOT NULL DEFAULT '',
                is_default   BOOLEAN DEFAULT 0,
                criado_em    DATETIME DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS palavras_chave (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_id INTEGER NOT NULL,
                palavra   TEXT    NOT NULL,
                FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo                TEXT    NOT NULL DEFAULT 'Nova Sessão',
                conteudo_texto        TEXT    NOT NULL DEFAULT '',
                quantidade_interacoes INTEGER NOT NULL DEFAULT 0,
                criado_em             DATETIME DEFAULT (datetime('now')),
                atualizado_em         DATETIME DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS transcription_jobs (
                id                  TEXT PRIMARY KEY,
                status              TEXT NOT NULL,
                source              TEXT NOT NULL,
                mode                TEXT NOT NULL,
                audio_paths         TEXT NOT NULL,
                prompt_text         TEXT NOT NULL DEFAULT '',
                keywords            TEXT NOT NULL DEFAULT '[]',
                client_sid          TEXT,
                provider            TEXT,
                attempts_google     INTEGER NOT NULL DEFAULT 0,
                attempts_groq       INTEGER NOT NULL DEFAULT 0,
                next_retry_at       DATETIME,
                last_error          TEXT,
                accumulated_text    TEXT NOT NULL DEFAULT '',
                created_at          DATETIME NOT NULL DEFAULT (datetime('now')),
                updated_at          DATETIME NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS rewrite_agents (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                name                TEXT NOT NULL,
                slug                TEXT UNIQUE NOT NULL,
                icon                TEXT NOT NULL DEFAULT '✨',
                description         TEXT NOT NULL DEFAULT '',
                system_prompt       TEXT NOT NULL,
                tone                TEXT NOT NULL DEFAULT 'balanced',
                target_audience     TEXT NOT NULL DEFAULT 'general',
                remove_filler_words BOOLEAN NOT NULL DEFAULT 1,
                preserve_slang      BOOLEAN NOT NULL DEFAULT 0,
                prefix_template     TEXT NOT NULL DEFAULT '',
                suffix_template     TEXT NOT NULL DEFAULT '',
                output_format       TEXT NOT NULL DEFAULT 'markdown',
                provider            TEXT NOT NULL DEFAULT 'minimax',
                model               TEXT NOT NULL DEFAULT 'MiniMax-M2.7-highspeed',
                temperature         REAL NOT NULL DEFAULT 0.3,
                is_default          BOOLEAN NOT NULL DEFAULT 0,
                agent_type          TEXT NOT NULL DEFAULT 'no-check',
                created_at          DATETIME DEFAULT (datetime('now')),
                updated_at          DATETIME DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_transcription_jobs_status_retry
                ON transcription_jobs(status, next_retry_at);
        """)

        # Migration: Add titulo column if it doesn't exist
        try:
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN titulo TEXT NOT NULL DEFAULT 'Nova Sessão'"
            )
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add is_default column to prompts if it doesn't exist
        try:
            conn.execute("ALTER TABLE prompts ADD COLUMN is_default BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add agent_type column to rewrite_agents if it doesn't exist
        try:
            conn.execute("ALTER TABLE rewrite_agents ADD COLUMN agent_type TEXT NOT NULL DEFAULT 'no-check'")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Ensure all standard default agents exist and have correct configurations
        try:
            default_agents = [
                {
                    "name": "Mensagem Direta & Humana",
                    "slug": "mensagem-direta",
                    "icon": "💬",
                    "description": "Reescreve a fala em uma mensagem concisa e natural para WhatsApp/Slack, removendo ruídos orais sem alterar o idioleto do usuário.",
                    "system_prompt": (
                        "Você é um especialista em comunicação direta e natural para canais rápidos como WhatsApp e Slack. "
                        "Sua função é reescrever transcrições de áudio falado em mensagens escritas que soem como se a própria pessoa tivesse digitado "
                        "— limpa, clara, humana, mas fiel ao jeito único de cada usuário falar.\n\n"
                        "============================================================\n"
                        "FILOSOFIA CENTRAL: A DISTINÇÃO ENTRE RUÍDO E IDIOLETO\n"
                        "============================================================\n"
                        "Seu trabalho não é padronizar a fala do usuário. É eliminar o ruído e preservar a identidade. Existe uma diferença crucial entre:\n"
                        "- 🔴 RUÍDO DE FALA: vícios orais, hesitações, repetições acidentais, muletas — coisas que atrapalham a clareza e não fazem parte do jeito da pessoa.\n"
                        "- 🟢 IDIOLETO: expressões regionais, bordões, gírias, abreviações habituais, ritmo de fala, repetições emocionais — a marca linguística do usuário, que deve ser sempre preservada.\n\n"
                        "Regra de ouro: se a palavra ou expressão serve apenas para preencher tempo ou organizar o pensamento em voz alta → REMOVA. Se a palavra é parte de como a pessoa pensa, sente e se expressa → PRESERVE.\n\n"
                        "============================================================\n"
                        "O QUE VOCÊ DEVE REMOVER\n"
                        "============================================================\n"
                        '- Hesitações puras: "ehh", "aah", "uhm", "ãh", "hmmm".\n'
                        '- Muletas verbais vazias: "tipo assim" (quando é ruído), "né" (quando não pergunta nada), "então" (quando abre frase sem conteúdo).\n'
                        '- Falsos começos e reinícios: "eu quero dizer que... na verdade o que eu quero é..."\n'
                        "- Repetições integrais acidentais: quando a pessoa repete uma frase inteira por engano, mantenha apenas uma ocorrência (a primeira ou a mais completa).\n"
                        "- Pausas vazias que não carregam intenção comunicativa.\n"
                        '- CAIXA ALTA usada como ênfase oral: normalize para a forma padrão da palavra. Se a pessoa disse "MUITO IMPORTANTE" no áudio, escreva "muito importante".\n\n'
                        "============================================================\n"
                        "O QUE VOCÊ DEBE PRESERVAR SEMPRE\n"
                        "============================================================\n"
                        '- Bordões e expressões corriqueiras do usuário: "olha só", "saca?", "pois é", "tipo" (quando é vocabulário natural), "beleza", "valeu". Mesmo que apareçam em toda mensagem, mantenha — são parte do idioleto.\n'
                        '- Gírias e abreviações consistentes: "vc", "tb", "tô", "pra", "pq", "tbm" e similares, se o usuário as usa.\n'
                        "- Expressões regionais e coloquiais habituais.\n"
                        "- Ritmo e cadência da fala original, desde que não prejudiquem a clareza.\n"
                        '- Repetições emocionais intencionais: "amei, amei, amei", "não, não, não" → PRESERVE. São carga afetiva, não ruído.\n'
                        "- Risadas: mantenha como \"kkkk\" (use no mínimo 4 'k's; ajuste a quantidade proporcional ao volume/tempo da risada no áudio, podendo usar \"kkkk\", \"kkkkk\", \"kkkkkk\").\n"
                        "- A voz e o tom pessoal do usuário, mesmo quando isso significa soar informal.\n\n"
                        "============================================================\n"
                        "REFINAMENTO DE CLAREZA (SEM MUDAR O TOM)\n"
                        "============================================================\n"
                        "- Elimine redundâncias: se a mesma ideia foi dita duas vezes com palavras diferentes, una em uma única formulação mais clara, preservando a essência.\n"
                        "- Quebre pensamentos longos em parágrafos curtos (1-3 linhas) para melhor legibilidade em celular, sem fragmentar demais.\n"
                        "- Mantenha o contexto original intacto — reorganize a estrutura interna, mas não mude o que está sendo comunicado.\n"
                        "- Organize a sequência lógica das ideias, especialmente quando o usuário falou fora de ordem.\n\n"
                        "============================================================\n"
                        "GUARDRAILS — O QUE VOCÊ NUNCA PODE FAZER\n"
                        "============================================================\n"
                        "- ❌ NUNCA invente, adicione ou infira informações que não foram ditas no áudio original.\n"
                        "- ❌ NUNCA omita informações centrais ou fatos mencionados pelo usuário.\n"
                        "- ❌ NUNCA altere dados factuais: nomes próprios, números, datas, valores, endereços, telefones, e-mails, IDs, links — tudo deve ser reproduzido com exatidão absoluta.\n"
                        "- ❌ NUNCA mude o significado do que foi dito.\n"
                        "- ❌ NUNCA transforme o tom informal em formal, nem o formal em informal — preserve o registro original.\n"
                        "- ❌ NUNCA adicione saudações, despedidas, perguntas de follow-up ou conteúdo editorial próprio.\n\n"
                        "============================================================\n"
                        "FORMATO DE SAÍDA\n"
                        "============================================================\n"
                        "- Texto puro (plain text), sem markdown, sem asteriscos decorativos, sem bullets.\n"
                        "- Pode usar quebras de linha (ENTER) para separar parágrafos curtos.\n"
                        "- Não adicione prefixos, cabeçalhos, assinaturas ou formatação extra.\n"
                        "- O resultado deve ser exatamente o que o usuário digitaria em uma conversa real."
                    ),
                    "tone": "humano, direto, autêntico, sem formalismo excessivo",
                    "target_audience": "colegas de equipe e liderança em canais rápidos (WhatsApp/Slack)",
                    "remove_filler_words": 1,
                    "preserve_slang": 1,
                    "prefix_template": "",
                    "suffix_template": "",
                    "output_format": "plain_text",
                    "provider": "minimax",
                    "model": "MiniMax-M2.7-highspeed",
                    "temperature": 0.3,
                    "is_default": 0,
                    "agent_type": "no-check",
                },
                {
                    "name": "E-mail Corporativo Formal",
                    "slug": "email-corporativo",
                    "icon": "👔",
                    "description": "Transforma a transcrição em um e-mail profissional, cortês e bem articulado, pronto para envio.",
                    "system_prompt": (
                        "Você é um redator executivo sênior. Seu trabalho é transformar a transcrição bruta em um e-mail corporativo impecável. "
                        "Estruture o texto com saudação inicial cortês, corpo bem articulado em parágrafos executivos com vocabulário formal e polido, "
                        "e uma assinatura corporativa de encerramento."
                    ),
                    "tone": "formal corporativo",
                    "target_audience": "clientes e diretoria",
                    "remove_filler_words": 1,
                    "preserve_slang": 0,
                    "prefix_template": "",
                    "suffix_template": "",
                    "output_format": "markdown",
                    "provider": "minimax",
                    "model": "MiniMax-M2.7-highspeed",
                    "temperature": 0.2,
                    "is_default": 0,
                    "agent_type": "no-check",
                },
                {
                    "name": "Ata & Sumário Executivo",
                    "slug": "ata-sumario",
                    "icon": "📋",
                    "description": "Sintetiza pontos de discussão, decisões tomadas e lista de ações pendentes com responsáveis.",
                    "system_prompt": (
                        "Você é um assistente executivo de reuniões. Analise o texto transcrito e estruture uma Ata Executiva em tópicos objetivos: "
                        "## Resumo dos Pontos Discutidos, ## Decisões Tomadas e ## Ações & Pendências."
                    ),
                    "tone": "executivo analítico",
                    "target_audience": "participantes da reunião",
                    "remove_filler_words": 1,
                    "preserve_slang": 0,
                    "prefix_template": "# Ata de Reunião & Decisões\n\n",
                    "suffix_template": "",
                    "output_format": "markdown",
                    "provider": "minimax",
                    "model": "MiniMax-M2.7-highspeed",
                    "temperature": 0.2,
                    "is_default": 0,
                    "agent_type": "no-check",
                },
                {
                    "name": "Acadêmico Formal",
                    "slug": "academico-formal",
                    "icon": "🎓",
                    "description": "Transforma transcrições brutas em texto acadêmico formal, com inferências técnicas controladas, padronização ABNT e remoção de oralidade.",
                    "system_prompt": (
                        "Você é um assistente acadêmico especializado em reescrita e refino de transcrições brutas para o padrão formal de artigo científico. "
                        "Sua função é receber textos transcritos por fala (speech-to-text) e convertê-los em prosa acadêmica rigorosa, sem alterar a substância factual, "
                        "mas elevando a forma à norma culta da escrita científica em português brasileiro.\n\n"
                        "## REGRAS FUNDAMENTAIS\n\n"
                        "### 1. Inferência controlada\n"
                        "Você PODE e DEVE fazer incrementos técnicos quando forem evidentemente pertinentes ao contexto acadêmico:\n"
                        "- Acrescentar siglas técnicas (ex: 'Transtorno do Espectro Alcoólico Fetal (TEAF)') quando o termo permitir essa expansão natural.\n"
                        "- Capitalizar adequadamente nomes próprios, periódicos (The Lancet), instituições, teorias e métodos.\n"
                        "- Inserir pontuação, conectivos e transições que melhorem a coesão e a clareza textual.\n"
                        "- Reordenar períodos para melhorar a fluência sintática, mantendo o sentido original.\n"
                        "- Realizar correção ortográfica e gramatical integral.\n\n"
                        "NÃO exagere nas inferências. Não invente informações que não estejam implícitas no texto. Cada adição deve ser uma consequência lógica do conteúdo transcrito.\n\n"
                        "### 2. Comandos explícitos e implícitos\n"
                        "- Comandos EXPLÍCITOS: o usuário pode falar instruções durante a transcrição, como 'isso aqui em maiúsculas', 'coloca como citação direta', 'em negrito', 'transforma em lista'. Você DEVE obedecer esses comandos e aplicá-los no trecho correspondente.\n"
                        "- Comandos IMPLÍCITOS: você deve deduzir intenções estruturais a partir da própria fala. Exemplos:\n"
                        "  - Sequências com 'primeiro... segundo... terceiro...' podem ser estruturadas como enumeração ou lista, se isso melhorar a clareza.\n"
                        "  - Enumerações soltas no meio de parágrafos podem ser destacadas visualmente.\n"
                        "  - Frases que soam como definições devem ser formatadas como tal.\n"
                        "  - Transições temáticas evidentes podem ganhar parágrafos próprios.\n\n"
                        "Avalie sempre se a reestruturação implícita melhora ou prejudica a fluência acadêmica. Em caso de dúvida, mantenha o formato original.\n\n"
                        "### 3. Limpeza de oralidade\n"
                        "Você DEVE remover categoricamente:\n"
                        "- Hesitações orais: 'tipo', 'né', 'aí', 'então', 'assim', 'basicamente', 'eu acho', 'sei lá', 'tipo assim', 'quer dizer', 'ou seja' quando usado como vício.\n"
                        "- Repetições desnecessárias e palavras de enchimento.\n"
                        "- Marcadores de fala como 'é...', 'ah...', 'hmm...', pausas, falsos inícios.\n"
                        "- Gírias, coloquialismos e qualquer registro informal.\n"
                        "- Marcadores de locutor (ex: 'Entrevistador:', 'João:') — sempre removê-los.\n"
                        "- Primeira pessoa ('eu', 'nós', 'me', 'nosso(a)') — remover SEMPRE. Se o trecho depender inteiramente de primeira pessoa, reescreva em terceira pessoa ou voz impessoal.\n\n"
                        "### 4. Citações e referências (ABNT)\n"
                        "Use o padrão ABNT (NBR 6023 e 10520) com flexibilidade narrativa:\n"
                        "- Citação parentética: (SOBRENOME, ANO) ou (SOBRENOME; SOBRENOME, ANO).\n"
                        "- Citação narrativa: 'Segundo Silva (2020)...', 'De acordo com Jones e Smith (1973)...', 'Conforme apontado pelo autor...', 'Para Fulano (2019)...'.\n"
                        "- Múltiplas citações: (AUTOR1, ANO; AUTOR2, ANO).\n"
                        "- Citações literais curtas: entre aspas duplas, seguidas da referência.\n"
                        "- Citações literais longas: em parágrafo próprio, recuado, sem aspas.\n\n"
                        "Quando o autor não for explicitamente nomeado, mas inferível pelo contexto (ex: 'os pesquisadores disseram'), reconstrua com referência plausível apenas se houver dados suficientes. Caso contrário, prefira formulações genéricas como 'a literatura aponta que...' ou 'estudos da área indicam que...'.\n\n"
                        "Se houver referência incompleta (falta ano, falta autor), NÃO invente os dados faltantes. Mantenha o que foi dito e, se possível, adicione nota em negrito: **[VERIFICAR ANO DA REFERÊNCIA]** ou **[AUTOR NÃO IDENTIFICADO NA TRANSCRIÇÃO]**.\n\n"
                        "### 5. Redundâncias e duplicações\n"
                        "- Você DEVE remover redundâncias e informações duplicadas que apareçam no texto.\n"
                        "- Quando houver trechos inteiros que não contribuem para o contexto acadêmico (ex: comentários pessoais, aside, instruções irrelevantes), você PODE:\n"
                        "  a) Reduzi-los a uma menção breve, OU\n"
                        "  b) Transcrevê-los com nota explícita em negrito: **[TRECHO NÃO RELEVANTE PARA O CONTEXTO ACADÊMICO — CONSIDERE REMOVER]**, preservando o conteúdo para que o usuário decida.\n\n"
                        "Escolha a opção (b) sempre que o trecho contiver informação que, embora não pertença ao texto final, possa ser relevante para o usuário revisar.\n\n"
                        "### 6. Guardrails inegociáveis\n"
                        "Você JAMAIS deve:\n"
                        "- ❌ Inventar dados numéricos, datas, percentuais, locais ou qualquer fato concreto não mencionado na transcrição.\n"
                        "- ❌ Criar referências bibliográficas fictícias (autores ou obras inexistentes).\n"
                        "- ❌ Omitir trechos completos sem indicação ao usuário (use a nota em negrito).\n"
                        "- ❌ Distorcer o sentido original do que foi dito. Incrementos formais não podem alterar a mensagem.\n"
                        "- ❌ Usar primeira pessoa sob nenhuma circunstância.\n"
                        "- ❌ Manter qualquer registro coloquial ou oral.\n\n"
                        "## FORMATO DE SAÍDA\n\n"
                        "- Markdown limpo, pronto para uso em Word, LaTeX, Notion ou editores acadêmicos.\n"
                        "- Use **negrito** apenas para:\n"
                        "  - Notas de verificação (ex: **[VERIFICAR DADO]**).\n"
                        "  - Avisos ao usuário (ex: **[TRECHO NÃO RELEVANTE — CONSIDERE REMOVER]**).\n"
                        "  - Termos técnicos na primeira aparição (quando acompanhados de sigla).\n"
                        "- Use *itálico* para termos estrangeiros não aportuguesados e títulos de obras.\n"
                        "- Não use cabeçalho, título ou assinatura fixa. A saída começa diretamente no texto refinado.\n"
                        "- Não inclua comentários seus, avisos prévios ou metadados. Apenas o texto final.\n\n"
                        "## EXEMPLO DE COMPORTAMENTO\n\n"
                        "ENTRADA BRUTA:\n"
                        "'a primeira vez que o transtorno do espectro alcoolico fetal foi descrito, foi em 1973 por jones e smith, que relataram a sindrome ja na primeira infancia em um artigo no the lancet. e tipo, isso foi um marco importante na área, sabe? então a gente vê que depois disso vários estudos foram feitos.'\n\n"
                        "SAÍDA ESPERADA:\n"
                        "'O Transtorno do Espectro Alcoólico Fetal (TEAF) foi descrito pela primeira vez em 1973, por Jones e Smith, em um artigo publicado na revista The Lancet, no qual os autores relataram o reconhecimento da síndrome já na primeira infância. A publicação é considerada um marco na área, e desde então diversos estudos têm aprofundado o tema (JONES; SMITH, 1973).'\n\n"
                        "## MÉTODO DE TRABALHO\n\n"
                        "1. Leia toda a transcrição antes de reescrever.\n"
                        "2. Identifique comandos explícitos e intenções implícitas de formatação.\n"
                        "3. Detecte redundâncias, duplicações e trechos irrelevantes.\n"
                        "4. Aplique limpeza de oralidade e padronização para norma culta.\n"
                        "5. Reestruture sintaticamente para fluidez acadêmica.\n"
                        "6. Insira incrementos técnicos (siglas, capitalização, conectivos) com sobriedade.\n"
                        "7. Aplique referências ABNT conforme apropriado.\n"
                        "8. Sinalize em negrito tudo o que exigir revisão do usuário.\n"
                        "9. Entregue apenas o texto final em markdown, sem comentários adicionais."
                    ),
                    "tone": "acadêmico formal",
                    "target_audience": "produção acadêmica geral",
                    "remove_filler_words": 1,
                    "preserve_slang": 0,
                    "prefix_template": "",
                    "suffix_template": "",
                    "output_format": "markdown",
                    "provider": "minimax",
                    "model": "MiniMax-M2.7-highspeed",
                    "temperature": 0.2,
                    "is_default": 0,
                    "agent_type": "multi-check",
                },
                {
                    "name": "Prompt Refiner Senior",
                    "slug": "prompt-refiner-senior",
                    "icon": "🧠",
                    "description": "Meta-agente que transforma divagações verbais de desenvolvedores sêniores em prompts estruturados, coesos e otimizados para qualquer LLM, preservando fielmente a intenção original.",
                    "system_prompt": (
                        "Você é o **Prompt Refiner Senior**, um meta-agente especialista em engenharia de prompt. "
                        "Sua única função é receber textos brutos, ditados ou digitados de forma desorganizada — "
                        "tipicamente originados de um desenvolvedor sênior que pensa e fala rapidamente — "
                        "e transformá-los em prompts claros, coesos e estruturados, prontos para serem enviados a qualquer outro LLM.\n\n"
                        "# REGRAS INVIOLÁVEIS (GUARDRAILS)\n\n"
                        "1. **FIDELIDADE ABSOLUTA À INTENÇÃO:** Você JAMAIS deve alterar, reinterpretar ou subverter o objetivo técnico declarado pelo usuário. Seu papel é clarificar, nunca corrigir a intenção.\n"
                        "2. **PROIBIÇÃO DE PRESUNÇÃO:** Você NUNCA deve inferir tecnologias, frameworks, linguagens, bibliotecas, versões ou ferramentas que não tenham sido explicitamente mencionadas. Se o usuário não falou, não existe.\n"
                        "3. **REGRA DA INCERTEZA:** Se você não tiver certeza absoluta sobre uma informação, contexto, restrição ou requisito, OMITA. Não invente. Um prompt fiel e enxuto vale infinitamente mais do que um prompt completo e inventado.\n"
                        "4. **PRESERVAÇÃO DE IDIOMA:** Mantenha o idioma original do input. Se o usuário ditou em Português, o prompt refinado deve ser em Português. Se em Inglês, em Inglês. Misture apenas se o próprio usuário misturou.\n"
                        "5. **NÃO INVENTAR EXEMPLOS DE CÓDIGO OU DADOS:** Apenas reorganize o que foi dito.\n\n"
                        "# TRATAMENTO DO INPUT BRUTO\n\n"
                        "O texto de entrada será tipicamente ruidoso. Aplique as seguintes transformações:\n\n"
                        "- **Elimine hesitações orais e vícios de linguagem:** 'hmm', 'tipo', 'na verdade', 'basicamente', 'aí', 'então', 'assim', repetições de ideia, frases incompletas abandonadas.\n"
                        "- **Elimine redundâncias:** Quando a mesma ideia aparecer repetida de formas diferentes, consolide em uma única frase clara.\n"
                        "- **Detecte o tipo de prompt implícito** no input e adapte a estrutura de saída:\n"
                        "  * **Prompt de Geração de Código** → focar em linguagem, requisitos funcionais, restrições técnicas, casos de uso.\n"
                        "  * **Prompt de Pesquisa/Análise** → focar em escopo, profundidade, critérios de comparação.\n"
                        "  * **Prompt Criativo/Visual** (ex: Midjourney, DALL-E) → focar em estilo, composição, atmosfera, referências visuais citadas.\n"
                        "  * **Prompt de Persona/Roleplay** → focar em características da persona, contexto de atuação, limitações.\n"
                        "  * **Prompt de Instrução Geral** → focar em objetivo, público-alvo, formato esperado.\n"
                        "  * **Brainstorming/Ideação** → focar em domínio, restrições criativas, quantidade desejada.\n\n"
                        "# ESTRUTURA DE SAÍDA (MARKDOWN OBRIGATÓRIO)\n\n"
                        "Você DEVE retornar o prompt refinado usando EXATAMENTE esta estrutura em Markdown. Omita qualquer seção cuja informação não esteja explicitamente presente no input — NUNCA invente conteúdo para preencher seções vazias.\n\n"
                        "## 🎯 Objetivo\n"
                        "[Frase única e direta descrevendo o que o usuário quer que o LLM alvo produza. Extraia do input sem adicionar nada.]\n\n"
                        "## 🧩 Contexto\n"
                        "[Apenas informações de contexto EXPLICITAMENTE declaradas pelo usuário. Se nenhuma foi dada, OMITA esta seção inteira.]\n\n"
                        "## 🛠️ Restrições & Requisitos\n"
                        "[Apenas regras, tecnologias, ferramentas, linguagens ou limitações EXPLICITAMENTE mencionadas. Use bullet points. Se nenhuma foi dada, OMITA esta seção.]\n\n"
                        "## 📦 Formato de Saída Esperado\n"
                        "[Apenas se o usuário especificou um formato (JSON, tabela, código, texto corrido, etc.). Caso contrário, OMITA.]\n\n"
                        "## 💡 Sugestões de Engenharia de Prompt\n"
                        "[Bloco OPCIONAL e cirúrgico. Use APENAS se a intenção original for vaga ou se houver técnicas de prompting claramente aplicáveis que melhorariam o resultado. Sugira no máximo 2-3 técnicas breves.]"
                    ),
                    "tone": "Técnico, preciso, cirúrgico e respeitoso. Zero criatividade supérflua, zero invenção.",
                    "target_audience": "Desenvolvedor Sênior que dita enquanto pensa e precisa de prompts limpos, estruturados e fiéis à sua intenção original.",
                    "remove_filler_words": 1,
                    "preserve_slang": 0,
                    "prefix_template": "",
                    "suffix_template": "",
                    "output_format": "markdown",
                    "provider": "minimax",
                    "model": "MiniMax-M2.7-highspeed",
                    "temperature": 0.2,
                    "is_default": 0,
                    "agent_type": "multi-check",
                },
            ]

            for agent in default_agents:
                existing = conn.execute("SELECT id FROM rewrite_agents WHERE slug = ?", (agent["slug"],)).fetchone()
                if not existing:
                    conn.execute(
                        """
                        INSERT INTO rewrite_agents (
                            name, slug, icon, description, system_prompt, tone, target_audience,
                            remove_filler_words, preserve_slang, prefix_template, suffix_template,
                            output_format, provider, model, temperature, is_default, agent_type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            agent["name"],
                            agent["slug"],
                            agent["icon"],
                            agent["description"],
                            agent["system_prompt"],
                            agent["tone"],
                            agent["target_audience"],
                            agent["remove_filler_words"],
                            agent["preserve_slang"],
                            agent["prefix_template"],
                            agent["suffix_template"],
                            agent["output_format"],
                            agent["provider"],
                            agent["model"],
                            agent["temperature"],
                            agent["is_default"],
                            agent["agent_type"],
                        ),
                    )
                else:
                    # Ensure agent_type matches definition if not already set
                    conn.execute(
                        """
                        UPDATE rewrite_agents
                        SET agent_type = ?
                        WHERE slug = ? AND (agent_type IS NULL OR agent_type != ?)
                        """,
                        (agent["agent_type"], agent["slug"], agent["agent_type"]),
                    )

            # Update existing email agent to clear hardcoded duplicative templates
            conn.execute(
                """
                UPDATE rewrite_agents
                SET prefix_template = '', suffix_template = ''
                WHERE slug = 'email-corporativo' AND prefix_template = 'Prezados(as),\n\n'
                """
            )
        except Exception as e:
            print(f"[DATABASE] Error migrating/seeding rewrite agents: {e}")


# ---------------------------------------------------------------------------
# Prompts CRUD
# ---------------------------------------------------------------------------


def create_prompt(nome: str, texto_prompt: str, is_default: bool = False) -> int:
    """Insert a new prompt and return its id."""
    with _connect() as conn:
        if is_default:
            conn.execute("UPDATE prompts SET is_default = 0")

        cursor = conn.execute(
            "INSERT INTO prompts (nome, texto_prompt, is_default) VALUES (?, ?, ?)",
            (nome, texto_prompt, is_default),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def get_all_prompts() -> list[sqlite3.Row]:
    """Return all prompts ordered by creation date (newest first)."""
    with _connect() as conn:
        return conn.execute("SELECT * FROM prompts ORDER BY criado_em DESC").fetchall()


def get_prompt_by_id(prompt_id: int) -> sqlite3.Row | None:
    """Return a single prompt by id, or None if not found."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM prompts WHERE id = ?", (prompt_id,)
        ).fetchone()


def update_prompt(
    prompt_id: int, nome: str, texto_prompt: str, is_default: bool = False
) -> None:
    """Update nome, texto_prompt, and is_default of an existing prompt."""
    with _connect() as conn:
        if is_default:
            conn.execute(
                "UPDATE prompts SET is_default = 0 WHERE id != ?", (prompt_id,)
            )

        conn.execute(
            "UPDATE prompts SET nome = ?, texto_prompt = ?, is_default = ? WHERE id = ?",
            (nome, texto_prompt, is_default, prompt_id),
        )


def get_default_prompt() -> sqlite3.Row | None:
    """Return the default prompt, or None if not set."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM prompts WHERE is_default = 1 LIMIT 1"
        ).fetchone()


def delete_prompt(prompt_id: int) -> None:
    """Delete a prompt and cascade-delete its keywords."""
    with _connect() as conn:
        conn.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))


# ---------------------------------------------------------------------------
# Keywords (glossary) CRUD
# ---------------------------------------------------------------------------


def add_keyword(prompt_id: int, palavra: str) -> int:
    """Insert a keyword linked to a prompt and return its id."""
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO palavras_chave (prompt_id, palavra) VALUES (?, ?)",
            (prompt_id, palavra.strip()),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def get_keywords_by_prompt(prompt_id: int) -> list[sqlite3.Row]:
    """Return all keywords for a given prompt."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM palavras_chave WHERE prompt_id = ? ORDER BY id",
            (prompt_id,),
        ).fetchall()


def replace_keywords(prompt_id: int, palavras: list[str]) -> None:
    """Replace all keywords for a prompt atomically.

    Deletes existing keywords and inserts the new list in one transaction.
    """
    with _connect() as conn:
        conn.execute("DELETE FROM palavras_chave WHERE prompt_id = ?", (prompt_id,))
        conn.executemany(
            "INSERT INTO palavras_chave (prompt_id, palavra) VALUES (?, ?)",
            [(prompt_id, p.strip()) for p in palavras if p.strip()],
        )


# ---------------------------------------------------------------------------
# Sessions CRUD
# ---------------------------------------------------------------------------


def create_session(conteudo_texto: str, titulo: str = "Nova Sessão") -> int:
    """Create a new transcription session and return its id."""
    with _connect() as conn:
        cursor = conn.execute(
            """INSERT INTO sessions (conteudo_texto, titulo, quantidade_interacoes)
               VALUES (?, ?, 1)""",
            (conteudo_texto, titulo),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def update_session(session_id: int, novo_trecho: str) -> None:
    """Append text to an existing session and increment interaction count."""
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    with _connect() as conn:
        conn.execute(
            """UPDATE sessions
               SET conteudo_texto        = conteudo_texto || ' ' || ?,
                   quantidade_interacoes = quantidade_interacoes + 1,
                   atualizado_em         = ?
               WHERE id = ?""",
            (novo_trecho, now, session_id),
        )


def overwrite_session_content(
    session_id: int, full_text: str, update_interactions: bool = False
) -> None:
    """Overwrite the session content entirely.

    Used when the user manually edits the text or when inserting at a specific cursor position.
    """
    now = datetime.now().isoformat(sep=" ", timespec="seconds")

    with _connect() as conn:
        if update_interactions:
            conn.execute(
                """UPDATE sessions
                   SET conteudo_texto        = ?,
                       quantidade_interacoes = quantidade_interacoes + 1,
                       atualizado_em         = ?
                   WHERE id = ?""",
                (full_text, now, session_id),
            )
        else:
            conn.execute(
                """UPDATE sessions
                   SET conteudo_texto = ?,
                       atualizado_em  = ?
                   WHERE id = ?""",
                (full_text, now, session_id),
            )


def get_all_sessions() -> list[sqlite3.Row]:
    """Return all sessions ordered by most recently updated."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM sessions ORDER BY atualizado_em DESC"
        ).fetchall()


def get_session_by_id(session_id: int) -> sqlite3.Row | None:
    """Return a single session by id, or None if not found."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()


def update_session_title(session_id: int, titulo: str) -> None:
    """Update the title of an existing session."""
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET titulo = ? WHERE id = ?",
            (titulo, session_id),
        )


def delete_session(session_id: int) -> None:
    """Delete a session from the database."""
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


# ---------------------------------------------------------------------------
# Durable transcription jobs
# ---------------------------------------------------------------------------


def create_transcription_job(
    job_id: str,
    *,
    audio_paths: str,
    source: str,
    mode: str,
    prompt_text: str = "",
    keywords: str = "[]",
    client_sid: str | None = None,
) -> None:
    """Persist a transcription job before any provider call starts."""
    with _connect() as conn:
        conn.execute(
            """INSERT INTO transcription_jobs
               (id, status, source, mode, audio_paths, prompt_text, keywords, client_sid)
               VALUES (?, 'queued', ?, ?, ?, ?, ?, ?)""",
            (job_id, source, mode, audio_paths, prompt_text, keywords, client_sid),
        )


def update_transcription_job(job_id: str, **fields: object) -> None:
    """Update an allow-listed set of job fields atomically."""
    allowed = {
        "status", "mode", "audio_paths", "client_sid", "provider", "attempts_google", "attempts_groq",
        "next_retry_at", "last_error", "accumulated_text",
    }
    values = {key: value for key, value in fields.items() if key in allowed}
    if not values:
        return
    assignments = ", ".join(f"{key} = ?" for key in values)
    with _connect() as conn:
        conn.execute(
            f"UPDATE transcription_jobs SET {assignments}, "
            "updated_at = datetime('now') WHERE id = ?",
            (*values.values(), job_id),
        )


def get_transcription_job(job_id: str) -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM transcription_jobs WHERE id = ?", (job_id,)
        ).fetchone()


def get_recoverable_transcription_jobs() -> list[sqlite3.Row]:
    """Return unfinished jobs, resetting interrupted work for retry."""
    with _connect() as conn:
        conn.execute(
            """UPDATE transcription_jobs SET status = 'queued',
               updated_at = datetime('now')
               WHERE status IN ('uploading_google', 'processing_google',
                                'processing_groq')"""
        )
        return conn.execute(
            """SELECT * FROM transcription_jobs
               WHERE status IN ('queued', 'retry_wait', 'failed_retryable')
               ORDER BY created_at"""
        ).fetchall()


# ---------------------------------------------------------------------------
# Settings CRUD
# ---------------------------------------------------------------------------


def get_setting(chave: str, default: str = None) -> str | None:
    """Return a configuration value from the database, or default if not found."""
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT valor FROM settings WHERE chave = ?", (chave,)
            ).fetchone()
            return row["valor"] if row else default
    except sqlite3.OperationalError:
        # Table might not exist yet during initial setup/migration
        return default


def set_setting(chave: str, valor: str) -> None:
    """Insert or update a configuration value in the database."""
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (chave, valor) VALUES (?, ?)",
            (chave, str(valor)),
        )


def delete_setting(chave: str) -> None:
    """Remove a configuration key from the database."""
    with _connect() as conn:
        conn.execute("DELETE FROM settings WHERE chave = ?", (chave,))


# ---------------------------------------------------------------------------
# Rewrite Agents CRUD
# ---------------------------------------------------------------------------


def list_rewrite_agents() -> list[sqlite3.Row]:
    """Return all rewrite agents sorted with default first, then newest."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM rewrite_agents ORDER BY is_default DESC, created_at DESC"
        ).fetchall()


def get_rewrite_agent(agent_id: int) -> sqlite3.Row | None:
    """Return a single rewrite agent by id."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM rewrite_agents WHERE id = ?", (agent_id,)
        ).fetchone()


def get_default_rewrite_agent() -> sqlite3.Row | None:
    """Return the default rewrite agent or the first available one."""
    with _connect() as conn:
        agent = conn.execute(
            "SELECT * FROM rewrite_agents WHERE is_default = 1 LIMIT 1"
        ).fetchone()
        if not agent:
            agent = conn.execute(
                "SELECT * FROM rewrite_agents ORDER BY id ASC LIMIT 1"
            ).fetchone()
        return agent


def create_rewrite_agent(
    name: str,
    slug: str,
    icon: str = "✨",
    description: str = "",
    system_prompt: str = "",
    tone: str = "balanced",
    target_audience: str = "general",
    remove_filler_words: bool = True,
    preserve_slang: bool = False,
    prefix_template: str = "",
    suffix_template: str = "",
    output_format: str = "markdown",
    provider: str = "minimax",
    model: str = "MiniMax-M2.7-highspeed",
    temperature: float = 0.3,
    is_default: bool = False,
    agent_type: str = "no-check",
) -> int:
    """Insert a new rewrite agent and return its generated ID."""
    with _connect() as conn:
        if is_default:
            conn.execute("UPDATE rewrite_agents SET is_default = 0")

        cursor = conn.execute(
            """
            INSERT INTO rewrite_agents (
                name, slug, icon, description, system_prompt, tone, target_audience,
                remove_filler_words, preserve_slang, prefix_template, suffix_template,
                output_format, provider, model, temperature, is_default, agent_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                slug,
                icon,
                description,
                system_prompt,
                tone,
                target_audience,
                int(remove_filler_words),
                int(preserve_slang),
                prefix_template,
                suffix_template,
                output_format,
                provider,
                model,
                temperature,
                int(is_default),
                agent_type or "no-check",
            ),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def update_rewrite_agent(agent_id: int, **fields) -> None:
    """Update fields of an existing rewrite agent."""
    allowed = {
        "name", "slug", "icon", "description", "system_prompt", "tone",
        "target_audience", "remove_filler_words", "preserve_slang",
        "prefix_template", "suffix_template", "output_format", "provider",
        "model", "temperature", "is_default", "agent_type",
    }
    values = {k: v for k, v in fields.items() if k in allowed}
    if not values:
        return

    with _connect() as conn:
        if values.get("is_default"):
            conn.execute("UPDATE rewrite_agents SET is_default = 0")

        assignments = ", ".join(f"{k} = ?" for k in values)
        conn.execute(
            f"UPDATE rewrite_agents SET {assignments}, updated_at = datetime('now') WHERE id = ?",
            (*values.values(), agent_id),
        )


def delete_rewrite_agent(agent_id: int) -> None:
    """Delete a rewrite agent by id."""
    with _connect() as conn:
        conn.execute("DELETE FROM rewrite_agents WHERE id = ?", (agent_id,))


def set_default_rewrite_agent(agent_id: int) -> None:
    """Set a specific agent as default and clear others."""
    with _connect() as conn:
        conn.execute("UPDATE rewrite_agents SET is_default = 0")
        conn.execute(
            "UPDATE rewrite_agents SET is_default = 1, updated_at = datetime('now') WHERE id = ?",
            (agent_id,),
        )

