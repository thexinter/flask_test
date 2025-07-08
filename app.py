from flask import Flask, send_file, Response
from ftplib import FTP
from io import BytesIO

app = Flask(__name__)

# Configurações do FTP
FTP_HOST = "storage.bunnycdn.com"
FTP_USER = "vz-364e076f-3d3"
FTP_PASS = "fc006d56-8af8-4f26-94ff4562faac-e0af-4cb8"

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
