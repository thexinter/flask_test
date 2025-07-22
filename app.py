import os
import mimetypes
import socket
import logging
from functools import lru_cache
from ftplib import FTP
from flask import Flask, Response, stream_with_context, abort, render_template_string
import threading
import time

app = Flask(__name__)

# ========================
# Configurações do Servidor FTP
# ========================
FTP_HOST = os.environ.get("FTP_HOST")
FTP_USER = os.environ.get("FTP_USER")
FTP_PASS = os.environ.get("FTP_PASS")

# Configurações de performance
CHUNK_SIZE = 1024 * 128  # 128KB
SOCKET_BUFFER_SIZE = 1024 * 1024  # 1MB
FTP_TIMEOUT = 30  # segundos
MAX_CACHED_MIME_TYPES = 2048
KEEPALIVE_INTERVAL = 20  # Enviar comando NOOP a cada 20 segundos

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ftp_proxy')

# ========================
# Cache para MIME types
# ========================
@lru_cache(maxsize=MAX_CACHED_MIME_TYPES)
def get_cached_mime_type(filename):
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"

# ========================
# Pool de Conexões FTP com Keepalive
# ========================
class FTPConnectionManager:
    _lock = threading.Lock()
    _connections = {}
    
    @classmethod
    def create_connection(cls):
        with cls._lock:
            thread_id = threading.get_ident()
            if thread_id in cls._connections:
                ftp = cls._connections[thread_id]
                try:
                    # Verifica se a conexão ainda está ativa
                    ftp.voidcmd("NOOP")
                    return ftp
                except:
                    # Remove conexão inválida
                    cls._connections.pop(thread_id, None)
            
            # Cria nova conexão
            ftp = FTP()
            ftp.connect(FTP_HOST, 21, timeout=FTP_TIMEOUT)
            ftp.set_pasv(True)
            ftp.login(FTP_USER, FTP_PASS)
            ftp.voidcmd("TYPE I")
            
            # Inicia thread de keepalive
            keepalive_thread = threading.Thread(
                target=cls._keepalive_thread,
                args=(ftp,),
                daemon=True
            )
            keepalive_thread.start()
            
            cls._connections[thread_id] = ftp
            return ftp
    
    @classmethod
    def _keepalive_thread(cls, ftp):
        try:
            while True:
                time.sleep(KEEPALIVE_INTERVAL)
                try:
                    with cls._lock:
                        if ftp in cls._connections.values():
                            ftp.voidcmd("NOOP")
                        else:
                            break
                except Exception as e:
                    logger.warning(f"Keepalive failed: {e}")
                    break
        finally:
            try:
                ftp.quit()
            except:
                pass
            with cls._lock:
                # Remove todas as referências a esta conexão
                for k, v in list(cls._connections.items()):
                    if v == ftp:
                        cls._connections.pop(k, None)

# ========================
# Página de Erro 403 Personalizada
# ========================
@app.errorhandler(403)
def forbidden(e):
    FORBIDDEN_PAGE = """<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML 2.0//EN">
    <html><head>
        <title>403 Forbidden</title>
    </head><body>
        <h1>Forbidden</h1>
        <p>You don't have permission to access / on this server.</p>
        <hr>
        <address>OpenCine/0.0.1</address>
    </body></html>"""
    return render_template_string(FORBIDDEN_PAGE), 403

# ========================
# Rota padrão bloqueada
# ========================
@app.route('/')
def default():
    abort(403)

# ========================
# Rota dinâmica para servir arquivos via FTP (Otimizada)
# ========================
@app.route('/<path:filename>')
def serve_ftp_file_stream(filename):
    ftp = None
    conn = None
    
    try:
        # 1. Estabelecer conexão FTP (reutilizável)
        ftp = FTPConnectionManager.create_connection()
        
        # 2. Verificar se arquivo existe
        try:
            file_size = ftp.size(filename)
            if file_size < 0:
                logger.warning(f"Arquivo não encontrado: {filename}")
                abort(404)
        except Exception as size_error:
            logger.warning(f"Erro ao verificar tamanho do arquivo: {size_error}")
            # Continua mesmo com erro, alguns servidores não suportam SIZE

        # 3. Iniciar transferência
        conn = ftp.transfercmd(f"RETR {filename}")
        
        # 4. Otimizar buffer de rede
        try:
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, SOCKET_BUFFER_SIZE)
        except:
            pass
        
        # 5. Obter tipo MIME (com cache)
        content_type = get_cached_mime_type(filename)

        # 6. Stream otimizado com tratamento de timeout
        def generate():
            last_active = time.time()
            try:
                while True:
                    try:
                        chunk = conn.recv(CHUNK_SIZE)
                        if not chunk:
                            break
                        last_active = time.time()
                        yield chunk
                    except socket.timeout:
                        # Verifica se a conexão ainda está ativa
                        if time.time() - last_active > FTP_TIMEOUT:
                            raise
                        continue
            except Exception as e:
                logger.error(f"Erro durante streaming: {str(e)}")
                abort(503)
            finally:
                # 7. Fechar recursos de forma segura
                try:
                    conn.close()
                    ftp.voidresp()  # Finalizar transferência
                except Exception as close_error:
                    logger.warning(f"Erro ao fechar conexão: {close_error}")

        # 8. Configurar resposta
        response = Response(
            stream_with_context(generate()),
            content_type=content_type,
            direct_passthrough=True
        )
        
        # 9. Headers importantes
        response.headers["Access-Control-Allow-Origin"] = "*"
        
        # 10. Cache-Control para arquivos de mídia
        if content_type.startswith(('video/', 'audio/', 'image/')):
            response.headers["Cache-Control"] = "public, max-age=86400"
            response.headers["Accept-Ranges"] = "bytes"
        
        return response

    except Exception as e:
        logger.error(f"Erro FTP grave: {str(e)}")
        abort(404)

# ========================
# Execução local
# ========================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, threaded=True)
