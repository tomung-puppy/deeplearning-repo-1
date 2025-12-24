from ultralytics import YOLO

class ProductRecognizer:
    def __init__(self, model_path='models/product_recognizer/best.pt'):
        self.model = YOLO(model_path)
        self.threshold = 0.7 # 상품 인식은 더 높은 정확도 요구

    def recognize(self, frame):
        """
        프레임 내의 상품을 인식하여 DB 조회를 위한 ID 반환
        """
        results = self.model.predict(frame, conf=self.threshold, verbose=False)
        
        if len(results) > 0 and len(results[0].boxes) > 0:
            # 가장 신뢰도가 높은 첫 번째 객체 선택
            top_box = results[0].boxes[0]
            product_id = int(top_box.cls[0])
            confidence = float(top_box.conf[0])
            
            return {
                "product_id": product_id,
                "confidence": confidence,
                "status": "detected"
            }
        
        return {"status": "none"}