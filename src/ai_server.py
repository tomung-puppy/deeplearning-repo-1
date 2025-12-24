import socketserver
import json
import cv2
import numpy as np
from src.detectors.product_dl import ProductDetector
from src.detectors.obstacle_dl import ObstacleDetector
from src.common.protocols import AIResponse, DetectionType

# 모델은 서버 시작 시 한 번만 로드하여 메모리에 유지합니다.
product_model = ProductDetector(model_path='models/product_recognizer/best.pt')
obstacle_model = ObstacleDetector(model_path='models/obstacle_detector/best.pt')

class AIInferenceHandler(socketserver.BaseRequestHandler):
    """
    PC2(Hub)로부터의 TCP 연결을 처리하는 핸들러입니다.
    """
    def handle(self):
        try:
            # 1. 이미지 데이터 크기 수신 (헤더 처리)
            # 클라이언트에서 먼저 데이터의 길이를 보낸다고 가정합니다.
            header = self.request.recv(8)
            if not header:
                return
            
            data_size = int(header.decode('utf-8').strip())
            
            # 2. 실제 이미지 바이트 수신
            chunks = []
            bytes_recvd = 0
            while bytes_recvd < data_size:
                chunk = self.request.recv(min(data_size - bytes_recvd, 4096))
                if not chunk:
                    break
                chunks.append(chunk)
                bytes_recvd += len(chunk)
            
            frame_data = b"".join(chunks)
            
            # 3. 이미지 디코딩 및 추론
            nparr = np.frombuffer(frame_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                results = []
                # 상품 및 장애물 탐지 실행
                results.extend(product_model.detect(frame))
                results.extend(obstacle_model.detect(frame))
                
                # 4. 결과 응답 생성 및 전송
                response = AIResponse(
                    frame_id=int(cv2.getTickCount()),
                    detections=results,
                    timestamp=cv2.getTickCount()
                )
                
                response_json = response.to_json().encode('utf-8')
                self.request.sendall(response_json)
                
        except Exception as e:
            print(f"Error handling request from {self.client_address}: {e}")

class ThreadedAIInferenceServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """
    여러 연결을 동시에 처리할 수 있는 스레딩 기반 TCP 서버입니다.
    """
    daemon_threads = True
    allow_reuse_address = True

if __name__ == "__main__":
    HOST, PORT = "0.0.0.0", 5000
    
    # 서버 생성 및 실행
    with ThreadedAIInferenceServer((HOST, PORT), AIInferenceHandler) as server:
        print(f"AI Inference Server (Threaded) started on {HOST}:{PORT}")
        # 서버가 종료될 때까지 무한 루프
        server.serve_forever()