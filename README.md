<p align="center">
  <img src="assets/assist_transcribe_1x1.png" alt="Assistente de Transcrição Logo" width="120" />
</p>

<h1 align="center">Assistente de Transcrição</h1>

O **Assistente de Transcrição** é uma aplicação desktop desenvolvida em Python (Flet) projetada para otimizar fluxos de anotação de áudio. Ela utiliza um roteador híbrido e inteligente de transcrição que combina as capacidades de nuvem da API do Google Gemini com o fallback veloz da API Groq (Whisper-large-v3-turbo), eliminando a necessidade de GPU local para transcrição offline.

## ✨ Principais Funcionalidades

- **Roteamento Híbrido e Resiliente:** Alternância automática ou manual entre Google Gemini e Groq (Whisper cloud), com fallback inteligente em caso de falha.
- **Interface Múltiplas Abas (Tabs):** Gerencie de forma organizada inúmeras sessões de gravação e transcrição de áudio simultaneamente.
- **Internacionalização (i18n):** Suporte integrado a múltiplos idiomas nativos abrangendo toda a interface da aplicação.
- **Controle de Gravação:** Flexibilidade total, com opção acessível de cancelar (abortar) facilmente qualquer gravação em andamento.

## 🚀 Arquitetura e Roteamento Híbrido

O sistema possui 3 modos de transcrição:
1. **Modo Automático ("auto"):** Executa um _ping_ no host configurado (`NETWORK_PING_HOST`) via `network_monitor.py`. Se houver internet, envia o áudio via `Files API` para o Google Gemini. Se falhar, faz fallback para a API Groq (`whisper-large-v3-turbo`).
2. **Forçar Cloud ("gemini"):** Usa exclusivamente o Google Gemini via Agno Agent, garantindo máxima precisão utilizando o modelo configurado no seu `.env` (ex: `gemini-2.0-flash`).
3. **Forçar Groq ("groq"):** Usa exclusivamente a API Groq com o modelo `whisper-large-v3-turbo`. Veloz, não requer GPU local, requer internet.

### Stack Tecnológica
- **Linguagem & Padronização:** Python 3.12+ empacotado e gerenciado via `uv`. O código-fonte é formatado com `black`.
- **UI Principal:** `Flet` (framework assíncrono baseado em Flutter).
- **Transcrição Cloud:** `google-genai` (Gemini) + `groq` (Whisper cloud).
- **Orquestração de Agentes:** `agno` (framework de agentes com streaming).
- **Processamento de Áudio:** `sounddevice` e `soundfile`.
- **Banco de Dados:** SQLite nativo, via `app/database.py`.

---

## 🛠️ Guia de Instalação e Configuração

Esse é um projeto adaptado para uso livre, você pode cloná-lo e customizá-lo visando as suas necessidades.

### 1. Clonando o Repositório e Preparando o Ambiente
Recomenda-se o uso do instalador super rápido `uv`.

```bash
git clone <seu-repo-aqui> transcricao-assistente
cd transcricao-assistente

# Use o 'uv' para sincronizar os pacotes listados em pyproject.toml
uv sync
```

### 2. Configurando o Ambiente (`.env`)
Uma etapa primordial. O arquivo de configuração mapeia o hardware local e a API a ser consumida.
Copie o template:
```bash
cp .env.example .env
```

**Principais Váriaveis:**
- `GOOGLE_API_KEY`: Necessário para transcrição via Google Gemini (Pegue em: aistudio.google.com).
- `GROQ_API_KEY`: Necessário para fallback via Groq Whisper cloud (Pegue em: console.groq.com).
- `GEMINI_MODEL`: (ex: `gemini-2.0-flash` ou `gemini-1.5-pro`).

### 3. Executando a Aplicação
Após atrelar seu ambiente, execute o Ponto de Entrada:

```bash
uv run main.py
```

Isso fará _trigger_ do módulo `app.config`, validando a leitura das suas chaves de API, instanciando o banco SQLite local (em `transcriber_data.db` por padrão se não mudado via ENV) e levantando a janela gráfica. 

---

## 🗃️ Entendendo as Camadas
As dependências se relacionam de forma limpa, não hesite em expandir as integrações:
- **`app/ui_flet/`**: Interface Flet com componentes assíncronos para gravação, transcrição e edição.
- **`app/agents/transcriber_agent.py`**: Orquestração Agno com streaming para transcrição via Gemini.
- **`app/audio_recorder.py`**: Captura de áudio via sounddevice, salvando WAV temporários.
- **`app/database.py`**: SQLite com tabelas para sessões, prompts e glossário de keywords.
- **`app/network_monitor.py`**: Verificação de conectividade transparente, determina roteamento cloud vs. fallback.

## Como Contribuir
Sinta-se à vontade para expandir as integrações de transcrição ou contribuir com a interface Electron (Vue 3 + Tailwind) em desenvolvimento!
