# Assistente de Transcrição

O **Assistente de Transcrição** é uma aplicação desktop desenvolvida em Python (CustomTkinter) projetada para otimizar fluxos de anotação de áudio. Ela utiliza um roteador híbrido e inteligente de transcrição que mescla modelos leves em execução local via GPU/CPU com as capacidades de nuvem da API do Google Gemini.

O foco da arquitetura é fornecer transcrições contínuas, seja conectado ou totalmente offline.

## ✨ Principais Funcionalidades

- **Roteamento Híbrido e Resiliente:** Alternância automática ou manual entre a nuvem (Google Gemini) e processamento local (Whisper).
- **Interface Múltiplas Abas (Tabs):** Gerencie de forma organizada inúmeras sessões de gravação e transcrição de áudio simultaneamente.
- **Internacionalização (i18n):** Suporte integrado a múltiplos idiomas nativos abrangendo toda a interface da aplicação.
- **Controle de Gravação:** Flexibilidade total, agora com a opção acessível de cancelar (abortar) facilmente qualquer gravação em andamento.

## 🚀 Arquitetura e Roteamento Híbrido

O sistema (`app/transcriber.py`) possui 3 modos de transcrição:
1. **Modo Automático ("auto"):** Executa um _ping_ no host configurado (`NETWORK_PING_HOST`) via `network_monitor.py`. Se houver internet, envia o áudio via `Files API` para o Google Gemini. Se falhar ou estiver sem internet, cai silenciosamente para o modelo local do Whisper.
2. **Forçar Cloud ("gemini"):** Pula a execução local, garantindo máxima precisão utilizando o modelo configurado no seu `.env` (ex: `gemini-2.0-flash`).
3. **Forçar Offline ("whisper"):** Usa exclusivamente a biblioteca `faster-whisper`. A engine carrega o modelo preguiçosamente (lazy load), alocando a VRAM apenas quando requisitada, e suporta rollback para CPU (int8) caso os drivers CUDA não estejam configurados corretamente na sua máquina.

### Stack Tecnológica
- **Linguagem & Padronização:** Python 3.12+ empacotado e gerenciado via `uv`. O código-fonte é estritamente formatado com o formatador de código `black`.
- **UI:** `customtkinter` (Interface Gráfica Nativa de Desempenho Flexível).
- **Transcrição Local:** `faster-whisper`.
- **Transcrição Cloud:** `google-genai`.
- **Processamento de Áudio:** `sounddevice` e `soundfile`.
- **Banco de Dados:** SQLite nativo, via script utilitário em `app/database.py`.

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
- `GOOGLE_API_KEY`: Necessário para transcrição via cloud no modelo híbrido (Pegue em: aistudio.google.com).
- `GEMINI_MODEL`: (ex: `gemini-2.0-flash` ou `gemini-1.5-pro`).
- `WHISPER_MODEL`: Define a quantização e o tamanho da rede offline (`base`, `small`, `medium`). Modelos como `base` rodam estavelmente em placas com ~4GB de VRAM.
- `WHISPER_DEVICE`: Escolha `cuda` para GPU ou `cpu` para fallback manual.
- `WHISPER_COMPUTE_TYPE`: Defina em `float16` (NVIDIA GPUs recomendadas), `int8` para máquinas modestas, e `float32` se exclusivo com CPU.

### 3. Executando a Aplicação
Após atrelar seu ambiente, execute o Ponto de Entrada:

```bash
uv run main.py
```

Isso fará _trigger_ do módulo `app.config`, validando a leitura das suas chaves de API, instanciando o banco SQLite local (em `transcriber_data.db` por padrão se não mudado via ENV) e levantando a janela gráfica. 

---

## 🗃️ Entendendo as Camadas
As dependências se relacionam de forma limpa, não hesite em expandir as integrações:
- **`app/ui/`**: Lida com a montagem CustomTkinter, modais e binds de evento de botões.  
- **`app/audio_recorder.py`**: Trata gravações do sistema através do buffer do sounddevice, salvando como WAV temporário ou de longo prazo.  
- **`app/database.py`**: Lida com o SQLite, criando as tabelas padrões (`initialize_db()`) armazenando logs, gravações ou prompts salvos.
- **`app/network_monitor.py`**: Singleton ou Threading encarregado de medir interrupções de conexão à internet transparentemente sem travar a UI principal.

## Como Contribuir
Sinta-se à vontade para alterar o banco de dados e os tratamentos locais de erros do CUDA contidos dentro de `transcriber.py` (_fallback para CPU_) perante as restrições da sua infraestrutura!
