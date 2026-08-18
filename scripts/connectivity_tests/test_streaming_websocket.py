#!/usr/bin/env python3
"""scripts/connectivity_tests/test_streaming_websocket.py

Simulates the Electron frontend and Audio Engine streaming flow to test the 
FastAPI Socket.IO and chunk REST endpoints locally.
"""

import asyncio
import json
import sys
from pathlib import Path

import numpy as np

# Setup path
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT))

from app.utils.audio_stream_processor import AudioStreamProcessor


async def main():
    print("🤖 Iniciando teste do pipeline de Streaming ASR via Socket.IO...")
    
    try:
        import socketio
    except ImportError:
        print("❌ Biblioteca 'python-socketio' não encontrada. Por favor, rode 'make install' ou 'uv sync' primeiro.")
        sys.exit(1)

    # 1. Cria o cliente Socket.IO assíncrono
    sio = socketio.AsyncClient()
    
    # Flags para controle do teste
    session_id = 'test_stream_' + str(int(asyncio.get_event_loop().time()))
    socket_connected = asyncio.Event()

    @sio.event
    async def connect():
        print(f"✅ Conectado com sucesso ao Socket.IO! Socket ID: {sio.sid}")
        socket_connected.set()

    @sio.on('transcription:stream:interim')
    async def on_interim(data):
        if data.get("sessionId") == session_id:
            print(f"📥 [SOCKET.IO EVENT] Tipo: 'interim' | Texto: '{data.get('text')}'")

    @sio.on('transcription:stream:final')
    async def on_final(data):
        if data.get("sessionId") == session_id:
            print(f"📥 [SOCKET.IO EVENT] Tipo: 'final' | Texto: '{data.get('text')}'")

    # 2. Conecta ao servidor local
    url = "http://localhost:18763"
    print(f"🔗 Conectando ao Socket.IO em {url}...")
    try:
        await sio.connect(url)
        await socket_connected.wait()
        
        # 3. Gera um áudio senoidal fictício de 3 segundos (16kHz)
        print("🔊 Gerando áudio de teste fictício (senoide)...")
        duration = 3.0
        sample_rate = 16000
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        audio_data = 0.5 * np.sin(2 * np.pi * 440 * t)
        
        # Converte em bytes de arquivo WAV PCM_16 em memória
        wav_io = AudioStreamProcessor.to_wav_bytes(audio_data, sample_rate)
        wav_bytes = wav_io.getvalue()

        # 4. Envia o chunk via HTTP POST local
        import urllib.request
        import urllib.parse
        
        print("📤 Enviando chunk de áudio via HTTP POST...")
        query_params = urllib.parse.urlencode({
            "prompt_text": "Teste de streaming de áudio local.",
            "keywords": "Reqflow, Faster-Whisper, Antigravity",
            "socket_id": sio.sid
        })
        post_url = f"http://localhost:18763/transcribe/stream/{session_id}/chunk?{query_params}"
        
        req = urllib.request.Request(
            url=post_url,
            data=wav_bytes,
            headers={"Content-Type": "audio/wav"}
        )
        
        loop = asyncio.get_running_loop()
        def send_post():
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read()

        try:
            res = await loop.run_in_executor(None, send_post)
            print(f"✅ Chunk enviado com sucesso! Resposta do servidor: {res.decode()}")
        except Exception as e:
            print(f"❌ Erro ao enviar chunk de áudio via POST: {e}")

        # Aguarda um pequeno momento para as respostas do Socket.IO chegarem
        await asyncio.sleep(3.0)

        # 5. Finaliza a sessão enviando done
        print("🏁 Finalizando sessão de streaming...")
        done_url = f"http://localhost:18763/transcribe/stream/{session_id}/done?{query_params}"
        done_req = urllib.request.Request(url=done_url, data=b"") # POST vazio
        
        def send_done():
            with urllib.request.urlopen(done_req, timeout=15) as response:
                return response.read()

        try:
            res_done = await loop.run_in_executor(None, send_done)
            print(f"✅ Sessão finalizada com sucesso! Resposta done: {res_done.decode()}")
        except Exception as e:
            print(f"❌ Erro ao finalizar sessão: {e}")

        # Aguarda as últimas mensagens consolidadas
        await asyncio.sleep(2.0)
        await sio.disconnect()

    except Exception as e:
        print(f"❌ Falha de conexão ou erro no teste: {e}")
        print("💡 Certifique-se de que o servidor FastAPI local está rodando ('make run' ou 'uv run python app/server.py')")


if __name__ == "__main__":
    asyncio.run(main())
