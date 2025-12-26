"""
Smart Shopping Cart Project - System Constants
모든 모듈에서 공유하는 상수 및 설정값 정의
"""

# --- Network Configuration (Default) ---
# 실제 운영 시 configs/network_config.yaml에서 로드하지만, 기본값으로 활용
DEFAULT_PC1_IP = "192.168.0.10"
DEFAULT_PC2_IP = "192.168.0.20"
DEFAULT_PC3_IP = "192.168.0.30"

# Ports
AI_UDP_PORT_FRONT = 5000         # PC1: AI Inference Server
AI_UDP_PORT_CART = 5001
UDP_PORT_FRONT_CAM = 6000  # PC2: Main Hub (Front Camera Stream)
UDP_PORT_CART_CAM = 6001   # PC2: Main Hub (Cart Camera Stream)
TCP_PORT_MAIN_EVT =6002
TCP_PORT_UI = 7000         # PC3: Dashboard UI Command Server


# --- System Status Codes ---
STATUS_IDLE = 0
STATUS_SCANNING = 1
STATUS_OBSTACLE_DETECTED = 2
STATUS_PAYMENT_PROCEEDING = 3
STATUS_ERROR = -1

# --- AI & Camera Settings ---
IMG_WIDTH = 640
IMG_HEIGHT = 480
FRAME_RATE = 30

# --- Error Messages ---
ERR_DB_CONN = "E101: Database Connection Failed"
ERR_AI_TIMEOUT = "E201: AI Inference Server Timeout"
ERR_UDP_DROP = "E301: Video Frame Dropped"

# --- Protocol Command Types ---
# Protocol.py에서 사용할 명령 레이블
CMD_ALARM = "SHOW_ALARM"
CMD_CART_UPDATE = "ADD_CART"
CMD_SESSION_START = "START_SESSION"
CMD_SESSION_END = "END_SESSION"

# --- Obstacle Detection Thresholds ---
DANGER_THRESHOLD_LOW = 0.3
DANGER_THRESHOLD_HIGH = 0.7