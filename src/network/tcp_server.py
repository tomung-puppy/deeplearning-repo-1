import socket
import json
import threading

class TCPServer:
    def __init__(self, host, port, handle_function):
        self.host = host
        self.port = port
        self.handle_function = handle_function # 데이터를 처리할 비즈니스 로직 함수

    def start(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind((self.host, self.port))
        server_sock.listen(5)
        print(f"Server listening on {self.host}:{self.port}")

        while True:
            client_sock, addr = server_sock.accept()
            # 멀티스레딩으로 여러 연결 처리
            thread = threading.Thread(target=self._client_handler, args=(client_sock,))
            thread.start()

    def _client_handler(self, client_sock):
        with client_sock:
            data = client_sock.recv(4096)
            if data:
                request = json.loads(data.decode('utf-8'))
                # 수신된 데이터 처리 후 응답 생성
                response = self.handle_function(request)
                client_sock.sendall(json.dumps(response).encode('utf-8'))