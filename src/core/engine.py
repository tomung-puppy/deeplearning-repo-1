import threading
import queue
import time
from src.network.tcp_client import AIClient
from src.database.db_handler import DBHandler
from src.common.protocols import DetectionResult, CartUpdate, DetectionType
from src.utils.logger import Logger

class SmartCartEngine:
    def __init__(self, network_config, db_config):
        self.logger = Logger("Engine")
        
        # 1. 컴포넌트 초기화
        self.ai_client = AIClient(network_config['pc1_ai']['ip'], network_config['pc1_ai']['port'])
        self.db_handler = DBHandler(db_config)
        
        # 2. 데이터 큐 (영상 프레임 및 처리 결과 저장)
        self.frame_queue = queue.Queue(maxsize=30)
        self.result_queue = queue.Queue()
        
        # 3. 실행 상태 제어
        self.is_running = False

    def start(self):
        """엔진의 핵심 스레드들을 시작합니다."""
        self.is_running = True
        self.logger.info("Starting Smart Cart Engine...")

        # AI 추론 요청 스레드
        threading.Thread(target=self._inference_loop, daemon=True).hexdoc()
        # 결과 처리 및 DB 연동 스레드
        threading.Thread(target=self._process_results_loop, daemon=True).start()

    def put_frame(self, frame_data):
        """UDP 핸들러가 수신한 프레임을 큐에 넣습니다."""
        if not self.frame_queue.full():
            self.frame_queue.put(frame_data)

    def _inference_loop(self):
        """큐에서 프레임을 가져와 PC1(AI 서버)에 분석을 요청합니다."""
        while self.is_running:
            if not self.frame_queue.empty():
                frame = self.frame_queue.get()
                try:
                    # AI 서버에 TCP로 분석 요청 (JSON 반환 가정)
                    raw_response = self.ai_client.request_inference(frame)
                    self.result_queue.put(raw_response)
                except Exception as e:
                    self.logger.error(f"Inference request failed: {e}")
            time.sleep(0.01) # CPU 점유율 조절

    def _process_results_loop(self):
        """AI 결과를 해석하고 필요한 경우 DB를 조회하여 UI 업데이트 정보를 생성합니다."""
        while self.is_running:
            if not self.result_queue.empty():
                ai_data = self.result_queue.get()
                
                for det in ai_data.get('detections', []):
                    label = det['label']
                    
                    if det['detect_type'] == DetectionType.PRODUCT.value:
                        # 상품인 경우 DB 조회 (AWS RDS TCP 통신)
                        product_info = self.db_handler.get_product_info(label)
                        if product_info:
                            update_packet = CartUpdate(
                                item_name=product_info['name'],
                                price=product_info['price'],
                                quantity=1, # 로직에 따라 증감 처리
                                total_price=product_info['price']
                            )
                            self._send_to_ui(update_packet)
                            
                    elif det['detect_type'] == DetectionType.OBSTACLE.value:
                        # 장애물인 경우 즉시 경고 전송
                        alert_packet = CartUpdate(
                            item_name="DANGER", price=0, quantity=0, 
                            total_price=0, is_danger=True
                        )
                        self._send_to_ui(alert_packet)
            time.sleep(0.01)

    def _send_to_ui(self, update_packet):
        """PC3(UI)로 결과 데이터를 전송합니다 (TCP Server 사용)."""
        # 이 부분은 tcp_server.py를 통해 PC3로 push하는 로직이 들어갑니다.
        self.logger.info(f"Sending update to UI: {update_packet.item_name}")
        # logic: self.ui_sender.send(update_packet.to_json())

    def stop(self):
        self.is_running = False
        self.logger.info("Engine stopped.")