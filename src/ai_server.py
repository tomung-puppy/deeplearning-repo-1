import cv2
import numpy as np
from network.tcp_server import TCPServer
from detectors.obstacle_dl import ObstacleDetector  # 장애물 탐지 래퍼
from detectors.product_dl import ProductRecognizer # 상품 인식 래퍼

class AIServer:
    def __init__(self):
        # 모델 로드 (weights 경로는 configs/model_config.yaml 기반으로 설정 권장)
        self.obstacle_model = ObstacleDetector()
        self.product_model = ProductRecognizer()
        
        # TCP 서버 초기화 (PC1의 IP와 포트 5000번 가정)
        self.server = TCPServer('0.0.0.0', 5000, self.handle_inference_request)

    def handle_inference_request(self, request):
        """
        PC2로부터의 요청을 처리하는 콜백 함수
        request: { 'type': 'obstacle' or 'product', 'image': [base64 or bytes] }
        """
        req_type = request.get('type')
        img_data = np.frombuffer(request['image'], dtype=np.uint8)
        frame = cv2.imdecode(img_data, cv2.IMREAD_COLOR)

        if req_type == 'obstacle':
            # 장애물 탐지 로직 실행 (거리/위험도 판단)
            result = self.obstacle_model.detect(frame)
        elif req_type == 'product':
            # 상품 인식 로직 실행 (클래스 ID 반환)
            result = self.product_model.recognize(frame)
        else:
            result = {"error": "Invalid request type"}

        return result

    def run(self):
        print("AI Server (PC1) Started...")
        self.server.start()

if __name__ == "__main__":
    ai_app = AIServer()
    ai_app.run()