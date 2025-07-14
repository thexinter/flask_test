import os
import mimetypes
import socket
import logging
from functools import lru_cache
from ftplib import FTP
from flask import Flask, Response, stream_with_context, abort, render_template_string

app = Flask(__name__)

# ========================
# Configurações do Servidor FTP
# ========================
FTP_HOST = os.environ.get("FTP_HOST")
FTP_USER = os.environ.get("FTP_USER")
FTP_PASS = os.environ.get("FTP_PASS")

# Configurações de performance
CHUNK_SIZE = 1024 * 128  # 128KB (equilíbrio entre memória e performance)
SOCKET_BUFFER_SIZE = 1024 * 1024  # 1MB (para redes de alta velocidade)
FTP_TIMEOUT = 30  # segundos
MAX_CACHED_MIME_TYPES = 2048  # Tamanho do cache para MIME types

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
# Pool de Conexões FTP (simplificado)
# ========================
class FTPConnectionManager:
    @staticmethod
    def create_connection():
        ftp = FTP()
        ftp.connect(FTP_HOST, 21, timeout=FTP_TIMEOUT)
        ftp.set_pasv(True)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.voidcmd("TYPE I")
        return ftp

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
        # 1. Estabelecer conexão FTP
        ftp = FTPConnectionManager.create_connection()
        
        # 2. Verificar se arquivo existe primeiro (opcional)
        try:
            file_size = ftp.size(filename)
            if file_size < 0:  # -1 indica falha
                logger.warning(f"Arquivo não encontrado: {filename}")
                abort(403)
        except Exception as size_error:
            logger.warning(f"Erro ao verificar tamanho do arquivo: {size_error}")
            # Continua mesmo com erro, alguns servidores não suportam SIZE

        # 3. Iniciar transferência
        conn = ftp.transfercmd(f"RETR {filename}")
        
        # 4. Otimizar buffer de rede
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, SOCKET_BUFFER_SIZE)
        
        # 5. Obter tipo MIME (com cache)
        content_type = get_cached_mime_type(filename)

        # 6. Stream otimizado
        def generate():
            try:
                while True:
                    chunk = conn.recv(CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
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
                finally:
                    try:
                        ftp.quit()
                    except:
                        pass

        # 8. Configurar resposta
        response = Response(
            stream_with_context(generate()),
            content_type=content_type,
            direct_passthrough=True  # Otimização para streaming
        )
        
        # 9. Headers importantes
        response.headers["Access-Control-Allow-Origin"] = "*"
        
        # 10. Cache-Control para arquivos de mídia
        if content_type.startswith(('video/', 'audio/', 'image/')):
            response.headers["Cache-Control"] = "public, max-age=86400"
        
        return response

    except Exception as e:
        logger.error(f"Erro FTP grave: {str(e)}")
        if ftp:
            try:
                ftp.quit()
            except:
                pass
        abort(403)

# ========================
# Execução local
# ========================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
