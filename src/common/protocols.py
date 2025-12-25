import time
from enum import IntEnum
from typing import Any, Dict, Optional


# =========================
# Enums
# =========================
class MessageType(IntEnum):
    AI_REQ = 1
    AI_RES = 2
    DB_REQ = 3
    DB_RES = 4
    UI_CMD = 5
    UI_EVT = 6
    AI_EVT = 7 


class AITask(IntEnum):
    OBSTACLE = 1
    PRODUCT = 2


class UICommand(IntEnum):
    SHOW_ALARM = 1
    ADD_TO_CART = 2
    UPDATE_STATUS = 3


class UIEvent(IntEnum):
    CART_UPDATED = 1
    SESSION_END = 2


class DBAction(IntEnum):
    GET_PRODUCT = 1
    ADD_CART_ITEM = 2
    GET_CART = 3

class AIEvent(IntEnum):
    OBSTACLE_DANGER = 1
    PRODUCT_DETECTED = 2

class DangerLevel(IntEnum):
    NORMAL = 0
    CAUTION = 1
    CRITICAL = 2




# =========================
# Protocol
# =========================
class Protocol:
    """
    System-wide JSON control protocol (TCP only)
    Binary data (image/frame) is NOT allowed.
    """

    VERSION = 1

    # -------------------------
    # Core
    # -------------------------
    @staticmethod
    def _base_message(
        msg_type: MessageType,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "header": {
                "type": int(msg_type),
                "timestamp": time.time(),
                "version": Protocol.VERSION,
            },
            "payload": payload,
        }

    # =========================
    # AI <-> Main PC2
    # =========================
    @staticmethod
    def ai_request(task: AITask) -> Dict[str, Any]:
        return Protocol._base_message(
            MessageType.AI_REQ,
            {"task": int(task)},
        )

    @staticmethod
    def ai_response(
        status: bool,
        analysis: Dict[str, Any],
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "status": status,
            "analysis": analysis,
        }
        if error:
            payload["error"] = error

        return Protocol._base_message(MessageType.AI_RES, payload)
    
    @staticmethod
    def ai_event(event: AIEvent, data: Dict[str, Any]) -> Dict[str, Any]:
        return Protocol._base_message(
            MessageType.AI_EVT,
            {
                "event": int(event),
                "data": data,
            },
        )


    # =========================
    # DB <-> Main PC2
    # =========================
    @staticmethod
    def db_request(
        action: DBAction,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        return Protocol._base_message(
            MessageType.DB_REQ,
            {
                "action": int(action),
                "data": data,
            },
        )

    @staticmethod
    def db_response(
        status: bool,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {"status": status}
        if data is not None:
            payload["data"] = data
        if error:
            payload["error"] = error

        return Protocol._base_message(MessageType.DB_RES, payload)

    # =========================
    # UI <-> Main PC2
    # =========================
    @staticmethod
    def ui_command(
        command: UICommand,
        content: Any,
    ) -> Dict[str, Any]:
        return Protocol._base_message(
            MessageType.UI_CMD,
            {
                "command": int(command),
                "content": content,
            },
        )

    @staticmethod
    def ui_event(
        event: UIEvent,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        return Protocol._base_message(
            MessageType.UI_EVT,
            {
                "event": int(event),
                "data": data,
            },
        )

    # =========================
    # Validation
    # =========================
    @staticmethod
    def validate(message: Dict[str, Any]) -> bool:
        try:
            header = message["header"]
            payload = message["payload"]

            return (
                isinstance(header, dict)
                and isinstance(payload, dict)
                and isinstance(header.get("type"), int)
                and isinstance(header.get("version"), int)
            )
        except Exception:
            return False
