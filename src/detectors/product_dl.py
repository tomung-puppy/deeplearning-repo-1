from ultralytics import YOLO
from common.config import config
import time
import numpy as np


class ProductRecognizer:
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = (
                config.model.product_recognizer.weights
                if config
                else "models/product_recognizer/product_yolov8s.pt"
            )
        self.model = YOLO(model_path)
        self.threshold = config.model.product_recognizer.confidence if config else 0.7

        # Check if model is OBB (Oriented Bounding Box) or regular detection
        self.is_obb = self.model.task == "obb"
        print(
            f"[ProductRecognizer] Model type: {'OBB' if self.is_obb else 'Detection'}"
        )

        # ROI + 모션 추적 시스템
        self.tracked_objects = (
            {}
        )  # {product_id: {"first_y": y, "last_y": y, "status": str, "last_seen": time}}
        self.last_added = {}  # {product_id: timestamp} - 쿨다운용
        self.cooldown_seconds = 3  # 같은 물건 3초 내 재인식 방지

        # ROI 영역 설정 (화면 비율 기준)
        self.entry_zone_ratio = 0.55  # 상단 55%까지를 진입 영역으로 (더 넓게)
        self.trigger_zone_ratio = 0.70  # 70% 아래로 내려가면 카트에 추가됨
        self.min_movement = 80  # 최소 이동 거리 (픽셀)

    def recognize(self, frame):
        """
        프레임 내의 상품을 인식하여 DB 조회를 위한 ID 반환
        바운딩 박스 정보도 포함
        """
        try:
            results = self.model.predict(frame, conf=self.threshold, verbose=False)

            # 안전한 None 체크
            if results is None:
                return {"status": "none"}

            # OBB vs Detection 모델 처리
            if self.is_obb:
                if (
                    len(results) > 0
                    and results[0].obb is not None
                    and len(results[0].obb) > 0
                ):
                    # OBB 모델: obb 속성 사용
                    top_box = results[0].obb[0]
                    yolo_class = int(top_box.cls[0])
                    confidence = float(top_box.conf[0])

                    # OBB는 회전된 박스이므로 xyxyxyxy (8개 좌표) 형식
                    # 하지만 간단하게 하려면 xyxy 형식으로 변환
                    xyxyxyxy = top_box.xyxyxyxy[0].cpu().numpy()
                    x_coords = xyxyxyxy[::2]  # x 좌표들
                    y_coords = xyxyxyxy[1::2]  # y 좌표들
                    bbox = [
                        float(x_coords.min()),
                        float(y_coords.min()),
                        float(x_coords.max()),
                        float(y_coords.max()),
                    ]

                    product_id = yolo_class + 1
                    return {
                        "product_id": product_id,
                        "confidence": confidence,
                        "bbox": bbox,
                        "status": "detected",
                    }
            else:
                if (
                    len(results) > 0
                    and results[0].boxes is not None
                    and len(results[0].boxes) > 0
                ):
                    # 일반 Detection 모델: boxes 속성 사용
                    top_box = results[0].boxes[0]
                    yolo_class = int(top_box.cls[0])
                    product_id = yolo_class + 1
                    confidence = float(top_box.conf[0])
                    bbox = top_box.xyxy[0].cpu().numpy().tolist()

                    return {
                        "product_id": product_id,
                        "confidence": confidence,
                        "bbox": bbox,
                        "status": "detected",
                    }

        except Exception as e:
            print(f"[ProductRecognizer] Error in recognize: {e}")

        return {"status": "none"}

    def recognize_with_trigger(self, frame, current_time=None):
        """
        물건을 카트에 넣는 순간을 감지하는 인식 메서드

        동작 원리:
        1. 상단 진입 영역(0~55%)에서 물체 첫 감지 → 추적 시작
        2. 물체가 트리거 영역(70% 이하)으로 이동 → "카트에 추가됨" 이벤트 발생
        3. 쿨다운: 같은 물건을 3초 내에 재인식하지 않음

        Args:
            frame: 입력 프레임
            current_time: 현재 시간 (None이면 자동 생성)

        Returns:
            dict: {
                "status": "added" | "tracking" | "none",
                "main_event": {...},  # 주요 이벤트 (added 또는 tracking)
                "all_detections": [...]  # 모든 감지된 물체들 (바운딩 박스 표시용)
            }
        """
        if current_time is None:
            current_time = time.time()

        h, w = frame.shape[:2]
        entry_zone_y = h * self.entry_zone_ratio
        trigger_zone_y = h * self.trigger_zone_ratio

        try:
            results = self.model.predict(frame, conf=self.threshold, verbose=False)
        except Exception as e:
            print(f"[ProductRecognizer] Error in predict: {e}")
            return {"status": "none", "all_detections": []}

        # 현재 프레임에서 감지된 모든 물체들
        all_detections = []
        main_event = None

        # 안전한 None 체크
        if results is None or len(results) == 0:
            return {"status": "none", "all_detections": []}

        # OBB vs Detection 모델 처리
        boxes_data = []
        if self.is_obb:
            if results[0].obb is not None and len(results[0].obb) > 0:
                for obb_box in results[0].obb:
                    # OBB를 일반 bbox로 변환
                    xyxyxyxy = obb_box.xyxyxyxy[0].cpu().numpy()
                    x_coords = xyxyxyxy[::2]
                    y_coords = xyxyxyxy[1::2]
                    bbox = np.array(
                        [x_coords.min(), y_coords.min(), x_coords.max(), y_coords.max()]
                    )

                    boxes_data.append(
                        {
                            "bbox": bbox,
                            "cls": int(obb_box.cls[0]),
                            "conf": float(obb_box.conf[0]),
                        }
                    )
        else:
            if results[0].boxes is not None and len(results[0].boxes) > 0:
                for box in results[0].boxes:
                    boxes_data.append(
                        {
                            "bbox": box.xyxy[0].cpu().numpy(),
                            "cls": int(box.cls[0]),
                            "conf": float(box.conf[0]),
                        }
                    )

        if len(boxes_data) > 0:
            for box_data in boxes_data:
                product_id = box_data["cls"] + 1
                bbox = box_data["bbox"]
                center_y = (bbox[1] + bbox[3]) / 2
                confidence = box_data["conf"]

                # 모든 물체 정보 수집 (바운딩 박스 표시용)
                detection_info = {
                    "product_id": product_id,
                    "confidence": confidence,
                    "bbox": bbox.tolist(),
                    "center_y": center_y,
                }

                # 쿨다운 체크 - 최근에 추가한 물건
                if product_id in self.last_added:
                    time_since_added = current_time - self.last_added[product_id]
                    if time_since_added < self.cooldown_seconds:
                        detection_info["state"] = "cooldown"
                        detection_info["cooldown_remaining"] = (
                            self.cooldown_seconds - time_since_added
                        )
                        all_detections.append(detection_info)
                        continue

                # 추적 상태 업데이트
                if product_id not in self.tracked_objects:
                    # 새로 발견된 물체 - 무조건 추적 시작! (위치 상관없이)
                    self.tracked_objects[product_id] = {
                        "first_y": center_y,
                        "last_y": center_y,
                        "status": "entering",
                        "last_seen": current_time,
                        "bbox": bbox.tolist(),
                    }

                    # 진입 영역인지 표시
                    in_entry = center_y < entry_zone_y
                    zone_name = "entry" if in_entry else "mid"

                    detection_info["state"] = "tracking"
                    detection_info["zone"] = zone_name
                    all_detections.append(detection_info)

                    if main_event is None:
                        main_event = {
                            "product_id": product_id,
                            "confidence": confidence,
                            "bbox": bbox.tolist(),
                            "status": "tracking",
                            "zone": zone_name,
                        }
                else:
                    # 이미 추적 중인 물체
                    obj = self.tracked_objects[product_id]
                    movement = center_y - obj["first_y"]

                    # 상태 업데이트
                    obj["last_y"] = center_y
                    obj["last_seen"] = current_time
                    obj["bbox"] = bbox.tolist()

                    # 트리거 조건 체크
                    if obj["status"] == "entering" and center_y > trigger_zone_y:
                        if movement > self.min_movement:
                            # 🎉 카트에 추가됨!
                            self.last_added[product_id] = current_time
                            del self.tracked_objects[product_id]

                            detection_info["state"] = "added"
                            detection_info["movement"] = movement
                            all_detections.append(detection_info)

                            main_event = {
                                "product_id": product_id,
                                "confidence": confidence,
                                "bbox": bbox.tolist(),
                                "status": "added",
                                "trigger": "motion_detected",
                                "movement": movement,
                            }
                        else:
                            # 이동 거리 부족
                            detection_info["state"] = "tracking"
                            detection_info["zone"] = "moving"
                            detection_info["movement"] = movement
                            all_detections.append(detection_info)
                    else:
                        detection_info["state"] = "tracking"
                        detection_info["zone"] = "moving"
                        detection_info["movement"] = movement
                        all_detections.append(detection_info)

                        if main_event is None:
                            main_event = {
                                "product_id": product_id,
                                "confidence": confidence,
                                "bbox": bbox.tolist(),
                                "status": "tracking",
                                "zone": "moving",
                            }

        # 오래된 추적 정보 정리 (2초 이상 보이지 않으면 제거)
        lost_ids = []
        for pid, data in self.tracked_objects.items():
            if current_time - data.get("last_seen", current_time) > 2.0:
                lost_ids.append(pid)

        for pid in lost_ids:
            del self.tracked_objects[pid]

        # 쿨다운 정리 (쿨다운 시간이 지난 항목 제거)
        cooldown_cleanup = []
        for pid, added_time in self.last_added.items():
            if current_time - added_time > self.cooldown_seconds:
                cooldown_cleanup.append(pid)

        for pid in cooldown_cleanup:
            del self.last_added[pid]

        # 결과 반환
        if main_event and main_event["status"] == "added":
            return {
                "status": "added",
                "main_event": main_event,
                "all_detections": all_detections,
            }
        elif main_event:
            return {
                "status": "tracking",
                "main_event": main_event,
                "all_detections": all_detections,
            }
        else:
            return {"status": "none", "all_detections": all_detections}

    def get_debug_zones(self, frame_shape):
        """
        디버깅용: ROI 영역 정보 반환

        Returns:
            dict: {
                "entry_zone": (x1, y1, x2, y2),
                "trigger_zone": (x1, y1, x2, y2),
                "tracked_count": int
            }
        """
        h, w = frame_shape[:2]
        entry_y = int(h * self.entry_zone_ratio)
        trigger_y = int(h * self.trigger_zone_ratio)

        return {
            "entry_zone": (0, 0, w, entry_y),
            "trigger_zone": (0, trigger_y, w, h),
            "tracked_count": len(self.tracked_objects),
            "cooldown_count": len(self.last_added),
        }

    def reset_tracking(self):
        """추적 상태 초기화"""
        self.tracked_objects.clear()
        self.last_added.clear()
