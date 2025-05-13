# websocket_routes.py
import json
from queue import Queue, Empty

signals_queue: Queue = Queue()

def register(sock):
    @sock.route("/api/signals/ws")
    def signals_ws(ws):
        while True:
            try:
                payload = signals_queue.get(timeout=60)
            except Empty:
                continue
            ws.send(json.dumps(payload))