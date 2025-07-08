import os
from flask import Flask, request, Response
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
        # Conecta ao FTP e busca o tamanho do arquivo
        ftp = FTP(FTP_HOST)
        ftp.login(FTP_USER, FTP_PASS)
        size = ftp.size(filename)

        # Verifica se o cabeçalho Range foi enviado
        range_header = request.headers.get('Range', None)
        byte_range = None

        if range_header:
            # Exemplo do cabeçalho: Range: bytes=1000-2000
            match = range_header.strip().lower().split('=')[-1]
            start, end = match.split('-')
            start = int(start) if start else 0
            end = int(end) if end else size - 1
            byte_range = (start, end)
        else:
            byte_range = (0, size - 1)

        start, end = byte_range
        length = end - start + 1

        # Abre conexão e faz o download apenas da parte solicitada
        buffer = BytesIO()

        def handle_binary(data):
            buffer.write(data)

        ftp.retrbinary(f"RETR {filename}", callback=handle_binary)
        ftp.quit()

        buffer.seek(start)
        data = buffer.read(length)

        headers = {
            'Content-Type': 'video/mp4',  # ou use mimetypes
            'Content-Length': str(length),
            'Content-Range': f'bytes {start}-{end}/{size}',
            'Accept-Ranges': 'bytes',
        }

        return Response(data, status=206, headers=headers)

    except Exception as e:
        return Response(f"Erro ao acessar o FTP: {str(e)}", status=500)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
