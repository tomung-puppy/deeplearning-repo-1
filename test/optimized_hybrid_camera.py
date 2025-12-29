#!/usr/bin/env python3
"""
최적화된 하이브리드 카메라 앱 (디버그 박스 포함)
- cv2.imshow()를 메인 스레드에서 처리
- 웹캠에서 상품 인식 바운딩 박스 표시
"""
import cv2
import time
import threading
import sys
from pathlib import Path
from queue import Queue

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from network.udp_handler import UDPFrameSender
from common.config import config
from utils.image_proc import ImageProcessor
from detectors.product_dl import ProductRecognizer


class OptimizedHybridCameraApp:
    """최적화된 하이브리드 카메라 앱"""

    def __init__(self, video_file):
        if config is None:
            raise RuntimeError("Configuration could not be loaded. Exiting.")

        # Get config values
        main_hub_ip = config.network.pc2_main.ip
        front_cam_port = config.network.pc2_main.udp_front_cam_port
        cart_cam_port = config.network.pc2_main.udp_cart_cam_port
        
        # Camera resolution and FPS
        self.img_width, self.img_height = config.app.camera.resolution
        self.fps = config.app.camera.fps

        # UDP Senders
        self.front_sender = UDPFrameSender(main_hub_ip, front_cam_port, jpeg_quality=70)
        self.cart_sender = UDPFrameSender(main_hub_ip, cart_cam_port, jpeg_quality=70)

        # Video file
        self.video_file = video_file
        self.front_cap = cv2.VideoCapture(video_file)
        if not self.front_cap.isOpened():
            raise RuntimeError(f"Cannot open video file: {video_file}")
        
        # 영상 FPS 가져오기
        video_fps = self.front_cap.get(cv2.CAP_PROP_FPS)
        if video_fps > 0:
            self.video_interval = 1.0 / min(video_fps, 15)  # 최대 15 FPS로 제한
        else:
            self.video_interval = 1.0 / 15
        
        # Webcam
        self.cart_cap = cv2.VideoCapture(0)
        if not self.cart_cap.isOpened():
            raise RuntimeError("Webcam not available")
        
        # 웹캠 해상도 설정
        self.cart_cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cart_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # Product recognizer for debug visualization
        print("상품 인식 모델 로딩 중...")
        self.product_recognizer = ProductRecognizer()
        print("모델 로딩 완료!")

        # Frame queues for display
        self.front_frame_queue = Queue(maxsize=2)
        self.cart_frame_queue = Queue(maxsize=2)
        
        self.is_running = True
        
        print("=" * 60)
        print("최적화된 하이브리드 카메라 앱 (디버그 박스)")
        print(f"  전방: {video_file}")
        print(f"  카트: 웹캠 (상품 인식 바운딩 박스 표시)")
        print(f"  Main Hub: {main_hub_ip}")
        print("=" * 60)

    def _capture_video_thread(self):
        """영상 파일 캡처 스레드"""
        print("[전방] 영상 캡처 시작")
        while self.is_running:
            ret, frame = self.front_cap.read()
            
            if not ret:
                self.front_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            
            # 리사이즈
            resized = ImageProcessor.resize_for_ai(frame, (self.img_width, self.img_height))
            
            # UDP 전송
            self.front_sender.send_frame(resized)
            
            # 디스플레이 큐에 추가
            if not self.front_frame_queue.full():
                self.front_frame_queue.put(resized.copy())
            
            time.sleep(self.video_interval)
        
        print("[전방] 캡처 종료")

    def _capture_webcam_thread(self):
        """웹캠 캡처 스레드 (상품 인식 포함)"""
        print("[카트] 웹캠 캡처 시작 (상품 인식 활성화)")
        interval = 1.0 / self.fps
        frame_count = 0
        last_result = None
        
        while self.is_running:
            ret, frame = self.cart_cap.read()
            if not ret:
                time.sleep(interval)
                continue
            
            frame_count += 1
            
            # 리사이즈
            resized = ImageProcessor.resize_for_ai(frame, (self.img_width, self.img_height))
            
            # UDP 전송
            self.cart_sender.send_frame(resized)
            
            # 디스플레이용 프레임
            display_frame = resized.copy()
            
            # 상품 인식 (3프레임마다 - 성능 최적화)
            if frame_count % 3 == 0:
                try:
                    last_result = self.product_recognizer.recognize(resized)
                except Exception as e:
                    last_result = {"status": "error", "message": str(e)}
            
            # 인식 결과 시각화
            if last_result:
                if last_result.get("status") == "detected":
                    product_id = last_result.get("product_id")
                    confidence = last_result.get("confidence", 0.0)
                    bbox = last_result.get("bbox")
                    
                    if bbox:
                        # 바운딩 박스 그리기
                        x1, y1, x2, y2 = map(int, bbox)
                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                        
                        # 레이블 배경
                        label = f"ID:{product_id} {confidence:.2f}"
                        label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                        cv2.rectangle(display_frame, (x1, y1 - label_size[1] - 10), 
                                    (x1 + label_size[0], y1), (0, 255, 0), -1)
                        
                        # 레이블 텍스트 (검은색)
                        cv2.putText(display_frame, label, (x1, y1 - 5),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
                    else:
                        # bbox 없으면 화면 상단에만 표시
                        text = f"Product ID: {product_id} ({confidence:.2f})"
                        cv2.putText(display_frame, text, (10, 30),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                elif last_result.get("status") == "error":
                    cv2.putText(display_frame, f"Error: {last_result.get('message', '')[:40]}", 
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                else:
                    # 인식 안됨
                    cv2.putText(display_frame, "No product detected", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 2)
            
            # FPS 표시
            cv2.putText(display_frame, f"Frame: {frame_count}", (10, display_frame.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # 디스플레이 큐에 추가
            if not self.cart_frame_queue.full():
                self.cart_frame_queue.put(display_frame)
            
            time.sleep(interval)
        
        print("[카트] 캡처 종료")

    def run(self):
        """메인 실행"""
        # 캡처 스레드 시작
        front_thread = threading.Thread(target=self._capture_video_thread, daemon=True)
        cart_thread = threading.Thread(target=self._capture_webcam_thread, daemon=True)
        
        front_thread.start()
        cart_thread.start()
        
        print("\n화면 표시 시작 ('q' 키로 종료)...")
        
        # 메인 스레드에서 화면 표시
        try:
            while self.is_running:
                # 전방 카메라 프레임 표시
                if not self.front_frame_queue.empty():
                    front_frame = self.front_frame_queue.get()
                    cv2.imshow('Front Camera (Obstacle)', front_frame)
                
                # 카트 카메라 프레임 표시 (바운딩 박스 포함)
                if not self.cart_frame_queue.empty():
                    cart_frame = self.cart_frame_queue.get()
                    cv2.imshow('Cart Camera (Product - Debug)', cart_frame)
                
                # 키 입력 확인
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\n종료 요청...")
                    self.is_running = False
                    break
                
        except KeyboardInterrupt:
            print("\n\n종료 요청...")
            self.is_running = False
        
        # 스레드 종료 대기
        front_thread.join(timeout=2)
        cart_thread.join(timeout=2)
        
        # 리소스 정리
        self.front_cap.release()
        self.cart_cap.release()
        cv2.destroyAllWindows()
        print("종료 완료")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="최적화된 하이브리드 카메라 앱")
    parser.add_argument(
        "--video", 
        default="test/Grocery Store Vocabulary_ shop in English.mp4",
        help="전방 카메라용 영상 파일"
    )
    
    args = parser.parse_args()
    
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"ERROR: 영상 파일을 찾을 수 없습니다: {video_path}")
        sys.exit(1)
    
    try:
        app = OptimizedHybridCameraApp(str(video_path))
        app.run()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
