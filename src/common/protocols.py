import json
import time

class Protocol:
    """
    모든 PC 간 통신에 사용되는 표준 메시지 포맷 정의
    """

    @staticmethod
    def create_message(cmd_type, data):
        """
        공통 메시지 구조 생성
        :param cmd_type: 명령 종류 (AI_REQ, DB_RES, UI_ALARM 등)
        :param data: 실제 전달할 데이터 (dict)
        """
        return {
            "header": {
                "timestamp": time.time(),
                "type": cmd_type,
                "version": "1.0"
            },
            "payload": data
        }

    # --- PC2(Main) -> PC1(AI) 요청 규약 ---
    @staticmethod
    def pack_ai_request(task_type, image_bytes):
        """
        AI 분석 요청용 패킷
        task_type: 'obstacle' 또는 'product'
        """
        return Protocol.create_message("AI_REQ", {
            "task": task_type,
            "image_data": image_bytes.hex()  # 바이트를 문자열로 변환하여 JSON 전송
        })

    # --- PC1(AI) -> PC2(Main) 응답 규약 ---
    @staticmethod
    def pack_ai_response(result_data):
        """AI 분석 결과 응답 패킷"""
        return Protocol.create_message("AI_RES", result_data)

    # --- PC2(Main) -> PC3(UI) 제어 규약 ---
    @staticmethod
    def pack_ui_command(cmd, content):
        """
        UI 업데이트 및 알람 명령
        cmd: 'SHOW_ALARM', 'ADD_CART', 'SET_STATUS'
        """
        return Protocol.create_message("UI_CMD", {
            "command": cmd,
            "content": content
        })

    # --- 공통 파서 (수신 측) ---
    @staticmethod
    def parse_message(json_str):
        """수신된 JSON 문자열을 딕셔너리로 변환 및 검증"""
        try:
            data = json.loads(json_str)
            if "header" in data and "payload" in data:
                return data
            return None
        except json.JSONDecodeError:
            return None