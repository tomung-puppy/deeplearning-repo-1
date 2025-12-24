import threading
import yaml
import cv2
from network.udp_handler import UDPHandler
from network.tcp_client import TCPClient
from database.db_handler import DBHandler
from database.product_dao import ProductDAO
from core.engine import SmartCartEngine
from common.protocols import Protocol
from common.constants import *
from utils.logger import SystemLogger
from utils.image_proc import ImageProcessor

class MainPC2Hub:
    def __init__(self):
        # 1. 로거 및 설정 초기화
        self.logger = SystemLogger(name="MainHub")
        self.config = self._load_config()
        
        # 2. 데이터베이스 및 DAO 초기화
        self.db_handler = DBHandler(self.config['db'])
        self.product_dao = ProductDAO(self.db_handler)
        
        # 3. 비즈니스 로직 엔진 초기화
        self.engine = SmartCartEngine(
            obstacle_detector=None, # 분석 주체는 PC1이므로 None
            product_recognizer=None,
            product_dao=self.product_dao
        )
        
        # 4. 네트워크 통신 모듈 (수신용 UDP 핸들러 분리)
        self.front_receiver = UDPHandler('0.0.0.0', UDP_PORT_FRONT_CAM)
        self.cart_receiver = UDPHandler('0.0.0.0', UDP_PORT_CART_CAM)
        
        self.ai_client = TCPClient(self.config['network']['pc1_ai']['ip'], TCP_PORT_AI)
        self.ui_client = TCPClient(self.config['network']['pc3_ui']['ip'], TCP_PORT_UI)

        self.logger.log_event("SYSTEM", "Main Hub Initialized and Ready")

    def _load_config(self):
        try:
            with open('configs/db_config.yaml', 'r') as f:
                db_cfg = yaml.safe_load(f)
            with open('configs/network_config.yaml', 'r') as f:
                net_cfg = yaml.safe_load(f)
            return {'db': db_cfg, 'network': net_cfg}
        except Exception as e:
            self.logger.log_error(f"Config Load Error: {e}")
            raise

    def process_obstacle_logic(self):
        """[시나리오 1] 장애물 인식 및 알람 처리"""
        self.logger.log_event("LOGIC", "Obstacle monitoring thread started")
        
        # 수신된 바이트 데이터를 frame으로 처리
        for byte_data in self.front_receiver.receive_frame():
            # 1. ImageProcessor를 통해 JPEG 바이트를 다시 프레임으로 복구
            frame = ImageProcessor.decode_frame(byte_data)
            if frame is None: continue

            # 2. AI 서버에 분석 요청 (이미지는 다시 바이트로 전송하거나 처리 방식에 따름)
            request_packet = Protocol.pack_ai_request("obstacle", byte_data) # 이미 압축된 상태인 byte_data 전송
            ai_res = self.ai_client.send_request(request_packet)
            
            if ai_res and ai_res.get('header', {}).get('type') == "AI_RES":
                # 3. 엔진을 통해 결과 해석
                analysis = self.engine.process_obstacle_frame(frame) # 또는 ai_res['payload'] 기반 처리
                
                # 4. 위험 판단 시 UI로 알람 전송
                if analysis['status'] in ["CAUTION", "CRITICAL_DANGER"]:
                    alarm_packet = Protocol.pack_ui_command(CMD_ALARM, f"Warning: {analysis['status']}")
                    self.ui_client.send_request(alarm_packet)
                    self.logger.log_event("OBSTACLE", f"Status: {analysis['status']}, Level: {analysis['danger_level']}")

    def process_product_logic(self):
        """[시나리오 2] 상품 스캔 및 장바구니 업데이트"""
        self.logger.log_event("LOGIC", "Product scanning thread started")
        
        for byte_data in self.cart_receiver.receive_frame():
            frame = ImageProcessor.decode_frame(byte_data)
            if frame is None: continue

            request_packet = Protocol.pack_ai_request("product", byte_data)
            ai_res = self.ai_client.send_request(request_packet)
            
            if ai_res and ai_res.get('header', {}).get('type') == "AI_RES":
                # 엔진에서 중복 제거 및 DB 연동 처리 (payload에 product_id 포함 가정)
                # 여기서는 ai_res 결과를 엔진에 전달하여 가공
                result = self.engine.process_product_frame(frame) # 내부에서 AI 결과와 매칭 로직 수행 가능
                
                if result['action'] == "ADD_TO_CART":
                    ui_packet = Protocol.pack_ui_command(CMD_CART_UPDATE, result['data'])
                    self.ui_client.send_request(ui_packet)
                    self.logger.log_event("SCAN", f"Product Added: {result['data']['product_name']}")

    def run(self):
        # 각각의 리시버로부터 독립적으로 데이터를 받기 위해 멀티스레딩
        obstacle_thread = threading.Thread(target=self.process_obstacle_logic, daemon=True)
        product_thread = threading.Thread(target=self.process_product_logic, daemon=True)
        
        obstacle_thread.start()
        product_thread.start()
        
        self.logger.log_event("SYSTEM", "All logic threads are running")
        
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.log_event("SYSTEM", "Main Hub shutting down")

if __name__ == "__main__":
    hub = MainPC2Hub()
    hub.run()