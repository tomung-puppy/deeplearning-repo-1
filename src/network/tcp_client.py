# tcp_client.py
import socket
import json
import struct
from typing import Any, Dict, Optional


class TCPClient:
    """
    Length-prefixed JSON TCP client.
    Protocol:
    - 4 bytes: big-endian unsigned int (payload length) ">I"
    - N bytes: JSON payload (utf-8)
    """

    HEADER_SIZE = 4

    def __init__(self, host: str, port: int, timeout: float = 5.0):
        # 접속하려는 클라이언트 서버 정보 저장
        self.host = host
        self.port = port
        self.timeout = timeout

    def send_request(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            # 직렬화 (dict -> JSON -> bytes)
            payload = self._serialize(data)
            # 소켓 생성
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                # 소켓 특성 저장 
                sock.settimeout(self.timeout)
                # 서버 연결
                sock.connect((self.host, self.port))
                # 메시지 전송 (헤더와 함께 전송)
                self._send(sock, payload)
                # 응답 수신
                response_payload = self._receive(sock)
            # 역직렬화 후 리턴
            return self._deserialize(response_payload)

        except (socket.timeout, ConnectionError) as e:
            print(f"[TCP ERROR] Network error: {e}")
        except (ValueError, json.JSONDecodeError) as e:
            print(f"[TCP ERROR] Serialization error: {e}")
        except Exception as e:
            print(f"[TCP ERROR] Unexpected error: {e}")

        return None

    def _serialize(self, data: Dict[str, Any]) -> bytes:
        return json.dumps(data, ensure_ascii=False).encode("utf-8")

    def _deserialize(self, payload: bytes) -> Dict[str, Any]:
        return json.loads(payload.decode("utf-8"))

    def _send(self, sock: socket.socket, payload: bytes) -> None:
        # payload의 길이를 고정크기로 만듬 (4bytes + len(payload))
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
                raise ConnectionError("Connection closed by server")
            buffer.extend(chunk)
        return bytes(buffer)

        
if __name__ == "__main__":
    client = TCPClient("127.0.0.1", 9000)
    response = client.send_request({"cmd": "ping"})
    print(response)
