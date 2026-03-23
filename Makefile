.PHONY: run test-ssl test-httpx test-httpx-post test-httpx2 test-genai test-network test-all

# ==========================================
# Aplicação Principal
# ==========================================

# Iniciar o sistema Transcribe Assistant (Tkinter Padrão)
run:
	uv run python main.py

# Iniciar o sistema Transcribe Assistant com interface Flet
run-flet:
	uv run python main_flet.py

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
