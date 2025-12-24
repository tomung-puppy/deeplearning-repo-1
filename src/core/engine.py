import cv2
from utils.image_proc import ImageProcessor # 영상 압축/해제 유틸
from common.constants import DANGER_THRESHOLD_HIGH, DANGER_THRESHOLD_LOW

class SmartCartEngine:
    def __init__(self, obstacle_detector, product_recognizer, product_dao):
        """
        메인 서버로부터 필요한 모듈들을 주입받아 초기화
        """
        self.obstacle_detector = obstacle_detector
        self.product_recognizer = product_recognizer
        self.product_dao = product_dao
        self.last_detected_product = None

    def process_obstacle_frame(self, frame):
        """
        전방 영상 분석 엔진: 위험도에 따른 상태 판단
        """
        # AI 분석 호출
        analysis = self.obstacle_detector.detect(frame)
        danger_level = analysis.get('danger_level', 0)

        # 비즈니스 로직: 위험도에 따른 메시지 결정
        status = "NORMAL"
        if danger_level >= DANGER_THRESHOLD_HIGH:
            status = "CRITICAL_DANGER"
        elif danger_level >= DANGER_THRESHOLD_LOW:
            status = "CAUTION"

        return {
            "status": status,
            "danger_level": danger_level,
            "object_count": len(analysis.get('objects', []))
        }

    def process_product_frame(self, frame):
        """
        상품 스캔 엔진: 중복 인식 방지 및 DB 정보 결합
        """
        analysis = self.product_recognizer.recognize(frame)
        
        if analysis['status'] == 'detected':
            p_id = analysis['product_id']
            
            # 동일 상품이 계속 인식되는 것을 방지 (간단한 로직)
            if p_id != self.last_detected_product:
                product_info = self.product_dao.get_product_by_id(p_id)
                if product_info:
                    self.last_detected_product = p_id
                    return {"action": "ADD_TO_CART", "data": product_info}
        
        return {"action": "NONE"}

    def reset_session(self):
        """세션 종료 시 데이터 초기화"""
        self.last_detected_product = None