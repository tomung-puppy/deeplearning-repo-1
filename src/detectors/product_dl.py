from ultralytics import YOLO
from common.config import config


class ProductRecognizer:
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = (
                config.model.product_recognizer.weights
                if config
                else "models/product_recognizer/product_yolo8s.pt"
            )
        self.model = YOLO(model_path)
        self.threshold = config.model.product_recognizer.confidence if config else 0.7

    def recognize(self, frame):
        """
        프레임 내의 상품을 인식하여 DB 조회를 위한 ID 반환
        바운딩 박스 정보도 포함
        """
        results = self.model.predict(frame, conf=self.threshold, verbose=False)

        if len(results) > 0 and len(results[0].boxes) > 0:
            # 가장 신뢰도가 높은 첫 번째 객체 선택
            top_box = results[0].boxes[0]
            yolo_class = int(top_box.cls[0])

            # YOLO class (0-8) → DB product_id (1-9) 매핑
            product_id = yolo_class + 1
            confidence = float(top_box.conf[0])

            # 바운딩 박스 좌표 (x1, y1, x2, y2)
            bbox = top_box.xyxy[0].cpu().numpy().tolist()

            return {
                "product_id": product_id,
                "confidence": confidence,
                "bbox": bbox,  # [x1, y1, x2, y2]
                "status": "detected",
            }

        return {"status": "none"}
