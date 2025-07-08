import os
from flask import Flask, send_file, Response
from ftplib import FTP
from io import BytesIO

app = Flask(__name__)

# Configurações do FTP a partir de variáveis de ambiente
FTP_HOST = os.environ.get("FTP_HOST", "storage.bunnycdn.com")
FTP_USER = os.environ.get("FTP_USER")
FTP_PASS = os.environ.get("FTP_PASS")

@app.route('/<path:filename>')
def serve_ftp_file(filename):
    try:
        ftp = FTP(FTP_HOST)
        ftp.login(FTP_USER, FTP_PASS)
        file_stream = BytesIO()
        ftp.retrbinary(f"RETR {filename}", file_stream.write)
        file_stream.seek(0)
        ftp.quit()
        return send_file(file_stream, download_name=filename)
    except Exception as e:
        return Response(f"Erro ao acessar o FTP: {str(e)}", status=500)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
