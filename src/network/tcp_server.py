import socketserver
import json
import threading
from src.utils.logger import Logger

# 만약 PC3에서 PyQt5를 사용한다면 시그널 전송을 위해 아래 클래스가 필요합니다.
# PyQt5가 설치되지 않은 환경(PC1, PC2)에서도 동작하도록 예외 처리를 포함합니다.
try:
    from PyQt5.QtCore import QObject, pyqtSignal
    class UIBridge(QObject):
        data_received = pyqtSignal(dict)
except ImportError:
    UIBridge = None

class BaseTCPHandler(socketserver.BaseRequestHandler):
    """
    들어오는 모든 TCP 요청을 처리하는 핸들러입니다.
    """
    def handle(self):
        logger = Logger("TCPHandler")
        try:
            # 1. 데이터 수신 (JSON 데이터라고 가정)
            data = self.request.recv(8192).decode('utf-8')
            if not data:
                return

            parsed_data = json.loads(data)
            
            # 2. 결과 전달 (UI 시그널 또는 콜백 함수 호출)
            if hasattr(self.server, 'callback') and self.server.callback:
                self.server.callback(parsed_data)
            
            if UIBridge and hasattr(self.server, 'ui_bridge'):
                self.server.ui_bridge.data_received.emit(parsed_data)

            # 3. 응답 (필요 시)
            response = {"status": "ok", "message": "Data received"}
            self.request.sendall(json.dumps(response).encode('utf-8'))

        except json.JSONDecodeError:
            logger.error("Received data is not a valid JSON")
        except Exception as e:
            logger.error(f"Error handling request: {e}")

class CustomTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """
    멀티스레딩을 지원하는 범용 TCP 서버입니다.
    """
    allow_reuse_address = True  # 서버 재시작 시 포트 바인딩 에러 방지

    def __init__(self, port, callback=None):
        self.logger = Logger("TCPServer")
        self.callback = callback
        
        # UI 연동용 브릿지 생성
        if UIBridge:
            self.ui_bridge = UIBridge()
            self.data_received_signal = self.ui_bridge.data_received
        
        super().__init__(('0.0.0.0', port), BaseTCPHandler)
        self.logger.info(f"TCP Server started on port {port}")

    def run_server(self):
        """별도의 스레드에서 서버를 실행합니다."""
        server_thread = threading.Thread(target=self.serve_forever, daemon=True)
        server_thread.start()
        self.logger.info("Server thread running in background.")