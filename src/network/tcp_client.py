import socket
import json
import struct
from src.utils.logger import Logger

class TCPClient:
    """
    [PC2 - Hub] AI 서버(PC1) 또는 기타 TCP 서버에 요청을 보내는 공통 클라이언트
    """
    def __init__(self, host, port, timeout=5):
        self.logger = Logger("TCPClient")
        self.addr = (host, port)
        self.timeout = timeout

    def send_request(self, data_bytes):
        """
        데이터 크기 헤더를 포함하여 바이트 데이터를 전송하고 응답을 받습니다.
        :param data_bytes: 전송할 바이트 데이터 (이미지 등)
        :return: 서버로부터 받은 JSON 응답 (딕셔너리 형태)
        """
        try:
            # 1. 소켓 생성 및 타임아웃 설정
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(self.timeout)
                s.connect(self.addr)

                # 2. 헤더 생성 (데이터 크기를 8자리 문자열로 포맷팅)
                # 예: 데이터가 1024바이트면 "    1024"로 보냄
                data_len = len(data_bytes)
                header = f"{data_len:8}".encode('utf-8')

                # 3. 헤더 + 데이터 전송
                s.sendall(header + data_bytes)

                # 4. 응답 수신
                # AI 결과값은 텍스트(JSON)이므로 적절한 버퍼 크기로 설정
                response_data = self._receive_all(s)
                if not response_data:
                    return None

                return json.loads(response_data.decode('utf-8'))

        except socket.timeout:
            self.logger.error(f"Connection timeout to {self.addr}")
        except ConnectionRefusedError:
            self.logger.error(f"Connection refused by {self.addr}. Is the server running?")
        except Exception as e:
            self.logger.error(f"Unexpected error in TCPClient: {e}")
        
        return None

    def _receive_all(self, sock):
        """
        서버로부터 오는 응답 데이터를 끝까지 안전하게 수신합니다.
        """
        chunks = []
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            except socket.timeout:
                break
        return b"".join(chunks)

    def send_json_request(self, data_dict):
        """
        딕셔너리 데이터를 JSON으로 변환하여 전송합니다.
        """
        json_bytes = json.dumps(data_dict).encode('utf-8')
        return self.send_request(json_bytes)