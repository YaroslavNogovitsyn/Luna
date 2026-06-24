"""
Простой приёмник webhook для локального тестирования.

Запуск:   python tools/webhook_receiver.py [PORT]
По умолчанию слушает порт 9000 и печатает тело каждого POST-запроса.

Чтобы платёж слал webhook сюда из docker-compose, укажите при создании
платежа webhook_url, доступный из контейнера consumer'а, например
http://host.docker.internal:9000/webhook  (Docker Desktop, Win/Mac).
"""

import json
import sys

from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            pretty = json.dumps(data, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            pretty = body.decode('utf-8', errors='replace')
        print(f'\n[webhook] {self.path}\n{pretty}', flush=True)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def log_message(self, *args) -> None:  # тише
        pass


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9000
    print(f'Webhook receiver слушает http://0.0.0.0:{port}', flush=True)
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
