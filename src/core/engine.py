# src/core/engine.py
import time
from typing import Dict, Any, Optional

from common.constants import (
    DANGER_THRESHOLD_HIGH,
    DANGER_THRESHOLD_LOW,
)


class SmartCartEngine:
    """
    Business decision engine.
    - Receives AI analysis results (JSON)
    - Makes business decisions
    - No networking, no AI inference
    """

    DUPLICATE_PRODUCT_INTERVAL_SEC = 2.0

    def __init__(self, product_dao):
        self.product_dao = product_dao
        self._last_product_id: Optional[int] = None
        self._last_product_ts: float = 0.0

    # -------------------------
    # Obstacle use case
    # -------------------------
    def process_obstacle_analysis(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        danger_level = analysis.get("danger_level", 0)
        objects = analysis.get("objects", [])

        status = self._map_danger_level_to_status(danger_level)

        return {
            "event": "OBSTACLE_ANALYSIS",
            "status": status,
            "danger_level": danger_level,
            "object_count": len(objects),
        }

    def _map_danger_level_to_status(self, danger_level: int) -> str:
        if danger_level >= DANGER_THRESHOLD_HIGH:
            return "CRITICAL_DANGER"
        if danger_level >= DANGER_THRESHOLD_LOW:
            return "CAUTION"
        return "NORMAL"

    # -------------------------
    # Product use case
    # -------------------------
    def process_product_analysis(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        if analysis.get("status") != "detected":
            return {"event": "NONE"}

        product_id = analysis.get("product_id")
        if not product_id:
            return {"event": "NONE"}

        if self._is_duplicate_product(product_id):
            return {"event": "NONE"}

        product_info = self.product_dao.get_product_by_id(product_id)
        if not product_info:
            return {
                "event": "PRODUCT_NOT_FOUND",
                "product_id": product_id,
            }

        self._mark_product_detected(product_id)

        return {
            "event": "ADD_TO_CART",
            "product": product_info,
        }

    def _is_duplicate_product(self, product_id: int) -> bool:
        now = time.time()
        if self._last_product_id != product_id:
            return False
        return (now - self._last_product_ts) < self.DUPLICATE_PRODUCT_INTERVAL_SEC

    def _mark_product_detected(self, product_id: int) -> None:
        self._last_product_id = product_id
        self._last_product_ts = time.time()

    # -------------------------
    # Session control
    # -------------------------
    def reset_session(self) -> None:
        self._last_product_id = None
        self._last_product_ts = 0.0
