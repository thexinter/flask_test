import os
from flask import Flask, Response
from ftplib import FTP

app = Flask(__name__)

# Configurações do FTP a partir de variáveis de ambiente
FTP_HOST = os.environ.get("FTP_HOST", "storage.bunnycdn.com")
FTP_USER = os.environ.get("FTP_USER")
FTP_PASS = os.environ.get("FTP_PASS")

CHUNK_SIZE = 64 * 1024  # 64 KB

@app.route('/<path:filename>')
def serve_ftp_file_stream(filename):
    try:
        ftp = FTP(FTP_HOST)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.voidcmd("TYPE I")  # modo binário

        conn = ftp.transfercmd(f"RETR {filename}")

        def generate():
            try:
                while True:
                    chunk = conn.recv(CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
            finally:
                conn.close()
                ftp.quit()

        return Response(generate(), content_type="application/octet-stream")

    except Exception as e:
        return Response(f"Erro ao acessar o FTP: {str(e)}", status=500)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
