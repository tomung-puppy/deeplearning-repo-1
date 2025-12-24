from enum import Enum, IntEnum

"""
시스템 전반에서 사용할 에러 코드, 상태 값, 사물 카테고리 등을 정의합니다. 문자열을 직접 쓰기보다 Enum을 사용하면 오타로 인한 버그를 방지할 수 있습니다.
"""

class DeviceState(IntEnum):
    """장치의 연결 상태를 나타냅니다."""
    IDLE = 0
    CONNECTING = 1
    RUNNING = 2
    ERROR = 3
    TERMINATED = 4

class DetectionType(Enum):
    """탐지된 객체의 종류를 구분합니다."""
    PRODUCT = "PRODUCT"   # 상품
    OBSTACLE = "OBSTACLE" # 장애물
    NONE = "NONE"

class StatusCode(IntEnum):
    """통신 응답 코드 정의"""
    SUCCESS = 200
    BAD_REQUEST = 400
    SERVER_ERROR = 500
    DB_CONNECTION_FAIL = 501