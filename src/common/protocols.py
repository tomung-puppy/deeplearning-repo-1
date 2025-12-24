from dataclasses import dataclass, asdict
from typing import List, Optional
import json

"""
PC 간에 주고받을 JSON 데이터 구조를 클래스 형태로 정의합니다. dataclass를 사용하면 객체를 JSON으로 변환하거나 관리하기가 매우 편리합니다.
"""

@dataclass
class DetectionResult:
    """PC1(AI)에서 PC2(Hub)로 보내는 개별 객체 탐지 결과"""
    label: str           # 사물 이름 (예: 'apple', 'coke')
    confidence: float    # 신뢰도 (0.0 ~ 1.0)
    bbox: List[int]      # 바운딩 박스 좌표 [x_min, y_min, x_max, y_max]
    detect_type: str     # DetectionType의 값

@dataclass
class AIResponse:
    """PC1이 PC2에게 주는 최종 응답 패킷"""
    frame_id: int
    detections: List[DetectionResult]
    timestamp: float

    def to_json(self):
        return json.dumps(asdict(self))

@dataclass
class CartUpdate:
    """PC2(Hub)에서 PC3(UI)로 보내는 장바구니 갱신 정보"""
    item_name: str
    price: int
    quantity: int
    total_price: int
    is_danger: bool = False  # 장애물 감지 시 경고 알람용

    def to_json(self):
        return json.dumps(asdict(self))