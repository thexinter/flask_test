import os
from flask import Flask, request, Response
from ftplib import FTP

app = Flask(__name__)

FTP_HOST = os.environ.get("FTP_HOST", "storage.bunnycdn.com")
FTP_USER = os.environ.get("FTP_USER")
FTP_PASS = os.environ.get("FTP_PASS")

CHUNK_SIZE = 64 * 1024  # 64KB por pedaço

@app.route('/<path:filename>')
def stream_ftp_file(filename):
    try:
        ftp = FTP(FTP_HOST)
        ftp.login(FTP_USER, FTP_PASS)
        size = ftp.size(filename)

        range_header = request.headers.get('Range', None)
        start, end = 0, size - 1

        if range_header:
            byte_range = range_header.strip().lower().split('=')[-1]
            parts = byte_range.split('-')
            if parts[0]:
                start = int(parts[0])
            if len(parts) > 1 and parts[1]:
                end = int(parts[1])

        content_length = end - start + 1

        def ftp_stream():
            total_read = 0

            def callback(data):
                nonlocal total_read
                if total_read + len(data) > content_length:
                    data = data[:content_length - total_read]
                total_read += len(data)
                yield_queue.append(data)

            yield_queue = []

            # Usa o comando REST para iniciar a partir do byte "start"
            ftp.sendcmd(f"TYPE I")
            ftp.sendcmd(f"REST {start}")
            conn = ftp.transfercmd(f"RETR {filename}")

            try:
                while total_read < content_length:
                    chunk = conn.recv(min(CHUNK_SIZE, content_length - total_read))
                    if not chunk:
                        break
                    total_read += len(chunk)
                    yield chunk
            finally:
                conn.close()
                ftp.quit()

        headers = {
            "Content-Type": "video/mp4",
            "Content-Length": str(content_length),
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Accept-Ranges": "bytes",
        }

        return Response(ftp_stream(), status=206 if range_header else 200, headers=headers)

    except Exception as e:
        return Response(f"Erro ao acessar o FTP: {str(e)}", status=500)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
