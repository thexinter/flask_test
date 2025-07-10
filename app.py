import os
from flask import Flask, Response, stream_with_context
from ftplib import FTP

app = Flask(__name__)

# Configurações do FTP (via variáveis de ambiente)
FTP_HOST = os.environ.get("FTP_HOST", "storage.bunnycdn.com")
FTP_USER = os.environ.get("FTP_USER")
FTP_PASS = os.environ.get("FTP_PASS")

# Tamanho do buffer de leitura (chunks maiores = melhor performance em rede estável)
CHUNK_SIZE = 256 * 1024  # 256 KB

@app.route('/<path:filename>')
def serve_ftp_file_stream(filename):
    try:
        # Conecta ao FTP
        ftp = FTP()
        ftp.connect(FTP_HOST, 21, timeout=10)
        ftp.set_pasv(True)  # modo passivo
        ftp.login(FTP_USER, FTP_PASS)
        ftp.voidcmd("TYPE I")  # modo binário

        # Inicia a transferência do arquivo
        conn = ftp.transfercmd(f"RETR {filename}")

        # Generator para envio dos dados em tempo real
        def stream_data():
            try:
                while True:
                    chunk = conn.recv(CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
            finally:
                conn.close()
                ftp.quit()

        # Resposta com streaming e header CORS
        response = Response(stream_with_context(stream_data()), content_type="application/octet-stream")
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    except Exception as e:
        return Response(f"Erro ao acessar o FTP: {str(e)}", status=500)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
