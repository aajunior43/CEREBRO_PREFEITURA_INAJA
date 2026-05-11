"""
Script para iniciar Cloudflare Quick Tunnel e capturar a URL pública.
Usado pelo bot do Telegram para enviar o link de acesso externo.
"""
import subprocess
import re
import time
import os
import sys
from pathlib import Path

# Adiciona o diretório pai ao path para imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bot.config import logger

TUNNEL_URL_FILE = Path(__file__).resolve().parent.parent / 'tunnel_url.txt'

def start_cloudflare_tunnel(port: int = 5000) -> str | None:
    """
    Inicia o Cloudflare Quick Tunnel e retorna a URL pública.
    Salva a URL em tunnel_url.txt para o bot ler depois.
    """
    cloudflared_path = Path(__file__).resolve().parent.parent / 'cloudflared.exe'
    
    if not cloudflared_path.exists():
        logger.error(f"cloudflared.exe não encontrado em: {cloudflared_path}")
        return None
    
    logger.info(f"Iniciando Cloudflare Quick Tunnel na porta {port}...")
    
    try:
        # Inicia cloudflared em modo captura de output
        process = subprocess.Popen(
            [str(cloudflared_path), 'tunnel', '--url', f'http://localhost:{port}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW  # Não mostra janela no Windows
        )
        
        url = None
        timeout = 30  # segundos para esperar o link
        start_time = time.time()
        
        # Lê output linha por linha procurando a URL
        for line in process.stdout:
            line = line.strip()
            logger.debug(f"cloudflared: {line}")
            
            # Procura pela URL do tunnel (formato: https://xxxxx.trycloudflare.com)
            url_match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
            if url_match:
                url = url_match.group(0)
                logger.info(f"✅ Tunnel Cloudflare criado: {url}")
                break
            
            # Verifica timeout
            if time.time() - start_time > timeout:
                logger.error("Timeout aguardando URL do Cloudflare Tunnel")
                process.terminate()
                return None
        
        if url:
            # Salva a URL em arquivo para o bot ler
            with open(TUNNEL_URL_FILE, 'w', encoding='utf-8') as f:
                f.write(url)
            logger.info(f"URL salva em: {TUNNEL_URL_FILE}")
            return url
        else:
            logger.error("Não foi possível capturar a URL do tunnel")
            process.terminate()
            return None
            
    except Exception as e:
        logger.error(f"Erro ao iniciar Cloudflare Tunnel: {e}")
        return None


def get_tunnel_url() -> str | None:
    """
    Lê a URL do tunnel salva em arquivo.
    Retorna None se o arquivo não existir ou estiver vazio.
    """
    try:
        if TUNNEL_URL_FILE.exists():
            url = TUNNEL_URL_FILE.read_text(encoding='utf-8').strip()
            if url and url.startswith('https://'):
                return url
    except Exception as e:
        logger.error(f"Erro ao ler URL do tunnel: {e}")
    return None


def clear_tunnel_url():
    """Remove o arquivo de URL do tunnel."""
    try:
        if TUNNEL_URL_FILE.exists():
            TUNNEL_URL_FILE.unlink()
            logger.info("Arquivo de URL do tunnel removido")
    except Exception as e:
        logger.error(f"Erro ao remover arquivo de URL: {e}")


if __name__ == '__main__':
    # Teste standalone
    url = start_cloudflare_tunnel()
    if url:
        print(f"Tunnel URL: {url}")
        print("Pressione Ctrl+C para encerrar...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nEncerrando...")
    else:
        print("Falha ao iniciar tunnel")
