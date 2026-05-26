.PHONY: run test-ssl test-httpx test-httpx-post test-httpx2 test-genai test-network test-all install uninstall

# Variáveis de diretório e versão para instalação local no Ubuntu
INSTALL_DIR := $(HOME)/.local/share/transcribe-assistant
BIN_DIR := $(HOME)/.local/bin
DESKTOP_DIR := $(HOME)/.local/share/applications
AUTOSTART_DIR := $(HOME)/.config/autostart
VERSION := $(shell grep -m 1 'version =' pyproject.toml | cut -d '"' -f 2)

# ==========================================
# Aplicação Principal
# ==========================================

# Iniciar o sistema Transcribe Assistant com interface Electron (Vue 3)
run:
	cd electron && npm run start

# ==========================================
# Instalação Local (Ubuntu)
# ==========================================
install:
	@echo "🤖 Compilando e empacotando o frontend Electron..."
	cd electron && npm install && npm run package
	
	@echo "🤖 Limpando diretório de instalação antigo..."
	rm -rf $(INSTALL_DIR)
	mkdir -p $(INSTALL_DIR)
	
	@echo "🤖 Copiando build do Electron para a pasta de instalação..."
	# Copia o conteúdo gerado pelo Electron Forge
	cp -r electron/out/transcribe-assistant-electron-linux-x64/* $(INSTALL_DIR)/
	
	@echo "🤖 Copiando o backend Python e configurações para os resources do Electron..."
	cp -r app $(INSTALL_DIR)/resources/
	cp pyproject.toml uv.lock $(INSTALL_DIR)/resources/
	# Copia o arquivo .env se existir, senão usa o .env.example como modelo
	if [ -f .env ]; then cp .env $(INSTALL_DIR)/resources/; else cp .env.example $(INSTALL_DIR)/resources/.env; fi
	
	@echo "🤖 Instalando e sincronizando dependências do Python nos recursos instalados..."
	# Usa o uv para sincronizar e recriar o ambiente virtual na pasta instalada de forma limpa e otimizada
	uv sync --project $(INSTALL_DIR)/resources
	
	@echo "🤖 Configurando ícone da aplicação..."
	mkdir -p $(INSTALL_DIR)/resources/assets
	cp assets/assist_transcribe_1x1.png $(INSTALL_DIR)/resources/assets/icon.png
	
	@echo "🤖 Criando script executável em $(BIN_DIR)/transcribe-assistant..."
	mkdir -p $(BIN_DIR)
	@echo '#!/bin/bash' > $(BIN_DIR)/transcribe-assistant
	@echo 'exec "$(INSTALL_DIR)/transcribe-assistant-electron" --no-sandbox "$$@"' >> $(BIN_DIR)/transcribe-assistant
	chmod +x $(BIN_DIR)/transcribe-assistant
	
	@echo "🤖 Criando atalho de desktop (.desktop)..."
	mkdir -p $(DESKTOP_DIR)
	@echo '[Desktop Entry]' > $(DESKTOP_DIR)/transcribe-assistant.desktop
	@echo 'Type=Application' >> $(DESKTOP_DIR)/transcribe-assistant.desktop
	@echo 'Name=Transcribe Assistant' >> $(DESKTOP_DIR)/transcribe-assistant.desktop
	@echo 'Comment=Assistente de Transcrição e Agente de IA (v$(VERSION))' >> $(DESKTOP_DIR)/transcribe-assistant.desktop
	@echo 'Exec=$(BIN_DIR)/transcribe-assistant' >> $(DESKTOP_DIR)/transcribe-assistant.desktop
	@echo 'Icon=$(INSTALL_DIR)/resources/assets/icon.png' >> $(DESKTOP_DIR)/transcribe-assistant.desktop
	@echo 'Terminal=false' >> $(DESKTOP_DIR)/transcribe-assistant.desktop
	@echo 'Categories=Utility;Office;' >> $(DESKTOP_DIR)/transcribe-assistant.desktop
	@echo 'StartupNotify=true' >> $(DESKTOP_DIR)/transcribe-assistant.desktop
	@echo 'StartupWMClass=transcribe-assistant-electron' >> $(DESKTOP_DIR)/transcribe-assistant.desktop
	chmod +x $(DESKTOP_DIR)/transcribe-assistant.desktop
	
	@echo "🤖 Configurando inicialização automática (autostart)..."
	mkdir -p $(AUTOSTART_DIR)
	cp $(DESKTOP_DIR)/transcribe-assistant.desktop $(AUTOSTART_DIR)/
	
	@echo "🎉 Instalação concluída com sucesso (v$(VERSION))!"
	@echo "👉 O aplicativo foi instalado em: $(INSTALL_DIR)"
	@echo "👉 Um atalho de inicialização foi criado em: $(AUTOSTART_DIR)"
	@echo "👉 Você pode iniciar a aplicação buscando por 'Transcribe Assistant' no menu de aplicativos do Ubuntu ou rodando 'transcribe-assistant' no terminal (caso $(BIN_DIR) esteja no seu PATH)."

uninstall:
	@echo "🤖 Removendo arquivos de instalação..."
	rm -rf $(INSTALL_DIR)
	rm -f $(BIN_DIR)/transcribe-assistant
	rm -f $(DESKTOP_DIR)/transcribe-assistant.desktop
	rm -f $(AUTOSTART_DIR)/transcribe-assistant.desktop
	@echo "🎉 Desinstalação concluída!"

# ==========================================
# Testes de Conectividade e Integração
# ==========================================

# Teste básico de SSL
test-ssl:
	uv run python scripts/connectivity_tests/test_ssl.py

# Teste básico do HTTPX com a API do Google (GET /)
test-httpx:
	uv run python scripts/connectivity_tests/test_httpx.py

# Teste HTTPX enviando um POST real
test-httpx-post:
	uv run python scripts/connectivity_tests/test_httpx_post.py

# Teste comparando chamadas com HTTP/1.1 e HTTP/2
test-httpx2:
	uv run python scripts/connectivity_tests/test_httpx2.py

# Teste end-to-end com o SDK oficial google-genai
test-genai:
	uv run python scripts/connectivity_tests/test_genai.py

# Rodar todos os testes de rede/conexões em sequência
test-network: test-ssl test-httpx test-httpx-post test-httpx2

# Rodar todos os testes de rede e finalizando com a integração oficial
test-all: test-network test-genai
