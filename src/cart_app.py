import cv2
import time
import threading
from network.udp_handler import UDPHandler
from common.constants import PC2_IP, UDP_PORT_FRONT_CAM, UDP_PORT_CART_CAM, IMG_WIDTH, IMG_HEIGHT
from utils.image_proc import ImageProcessor

class CartEdgeApp:
    def __init__(self):
        # 1. PC2(메인 서버)의 포트 설정 (상수 활용)
        self.front_sender = UDPHandler(PC2_IP, UDP_PORT_FRONT_CAM)
        self.cart_sender = UDPHandler(PC2_IP, UDP_PORT_CART_CAM)
        
        # 2. 카메라 장치 연결 (0: 전방, 1: 카트 내부)
        self.front_cap = cv2.VideoCapture(0)
        self.cart_cap = cv2.VideoCapture(1)
        
        # 3. 전송 상태 제어
        self.is_running = True

    def stream_front_camera(self):
        """전방 카메라 영상 송신 (장애물 인식용)"""
        print(f"Front camera streaming to {PC2_IP}:{UDP_PORT_FRONT_CAM}...")
        while self.is_running:
            ret, frame = self.front_cap.read()
            if ret:
                # ImageProcessor를 이용한 리사이징 및 인코딩
                # AI 분석 효율을 위해 상수(640x480)에 맞춰 리사이즈
                resized_frame = ImageProcessor.resize_for_ai(frame, (IMG_WIDTH, IMG_HEIGHT))
                encoded_data = ImageProcessor.encode_frame(resized_frame, quality=80)
                
                if encoded_data:
                    self.front_sender.send_frame(encoded_data)
                    
            time.sleep(0.03)  # 약 30 FPS 유지

    def stream_cart_camera(self):
        """카트 내부 카메라 영상 송신 (상품 스캔용)"""
        print(f"Cart camera streaming to {PC2_IP}:{UDP_PORT_CART_CAM}...")
        while self.is_running:
            ret, frame = self.cart_cap.read()
            if ret:
                # 상품 인식용 프레임 처리
                resized_frame = ImageProcessor.resize_for_ai(frame, (IMG_WIDTH, IMG_HEIGHT))
                encoded_data = ImageProcessor.encode_frame(resized_frame, quality=85) # 상품 인식은 약간 더 고화질
                
                if encoded_data:
                    self.cart_sender.send_frame(encoded_data)
                    
            time.sleep(0.03)

    def stop(self):
        print("Stopping streams...")
        self.is_running = False
        time.sleep(0.5)
        self.front_cap.release()
        self.cart_cap.release()

    def run(self):
        # 두 대의 카메라를 멀티스레드로 동시 송출
        front_thread = threading.Thread(target=self.stream_front_camera, daemon=True)
        cart_thread = threading.Thread(target=self.stream_cart_camera, daemon=True)
        
        front_thread.start()
        cart_thread.start()
        
        # 메인 스레드 대기
        while self.is_running:
            time.sleep(1)

if __name__ == "__main__":
    app = CartEdgeApp()
    try:
        app.run()
    except KeyboardInterrupt:
        app.stop()
        print("Streaming stopped.")