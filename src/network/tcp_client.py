import socket
import json

class TCPClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def send_request(self, data_dict):
        """JSON 데이터를 전송하고 응답을 받음"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.host, self.port))
                # 프로토콜 규약에 따른 JSON 직렬화
                message = json.dumps(data_dict).encode('utf-8')
                s.sendall(message)
                
                response = s.recv(4096)
                return json.loads(response.decode('utf-8'))
        except Exception as e:
            print(f"TCP Connection Error: {e}")
            return None