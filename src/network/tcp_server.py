# tcp_server.py
import socket
import json
import struct
import threading
from typing import Any, Dict, Callable


class TCPServer:
    """
    Length-prefixed JSON TCP server.
    Protocol:
    - 4 bytes: big-endian unsigned int (payload length)
    - N bytes: JSON payload (utf-8)
    """

    HEADER_SIZE = 4

    def __init__(self, host: str, port: int, handler: Callable[[Dict[str, Any]], Dict[str, Any]]):
        self.host = host
        self.port = port
        self.handler = handler

    def start(self) -> None:
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #포트 재사용 허용
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # 지정한 포트에 서버소켓 고정
        server_sock.bind((self.host, self.port))
        # 클라이언트 연결 대기상태로 전환
        server_sock.listen()
        print(f"Server listening on {self.host}:{self.port}")

        # 서버를 계속 실행
        while True:
            # 클라이언트와 연결
            client_sock, addr = server_sock.accept()
            # 클라이언트 1명당 전용 스레드 생성
            # _client_handler가 실제 통신 처리
            thread = threading.Thread(
                target=self._client_handler,
                args=(client_sock, addr),
                daemon=True,
            )
            thread.start()

    def _client_handler(self, client_sock: socket.socket, addr) -> None:
        with client_sock:
            try:
                request_payload = self._receive(client_sock)
                request = self._deserialize(request_payload)

                response = self.handler(request)
                response_payload = self._serialize(response)

                self._send(client_sock, response_payload)

            except (ConnectionError, json.JSONDecodeError, ValueError) as e:
                print(f"[CLIENT {addr}] Error: {e}")
            except Exception as e:
                print(f"[CLIENT {addr}] Unexpected error: {e}")

    def _send(self, sock: socket.socket, payload: bytes) -> None:
        header = struct.pack(">I", len(payload))
        sock.sendall(header + payload)

    def _receive(self, sock: socket.socket) -> bytes:
        header = self._recv_exact(sock, self.HEADER_SIZE)
        payload_length = struct.unpack(">I", header)[0]
        return self._recv_exact(sock, payload_length)

    def _recv_exact(self, sock: socket.socket, size: int) -> bytes:
        buffer = bytearray()
        while len(buffer) < size:
            chunk = sock.recv(size - len(buffer))
            if not chunk:
                raise ConnectionError("Client disconnected")
            buffer.extend(chunk)
        return bytes(buffer)

    def _serialize(self, data: Dict[str, Any]) -> bytes:
        return json.dumps(data, ensure_ascii=False).encode("utf-8")

    def _deserialize(self, payload: bytes) -> Dict[str, Any]:
        return json.loads(payload.decode("utf-8"))
