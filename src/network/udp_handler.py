import cv2
import socket
import numpy as np
from src.utils.logger import Logger

class VideoSender:
    """
    [PC3 - Edge] 카메라 프레임을 압축하여 PC2(Hub)로 전송하는 클래스
    """
    def __init__(self, target_ip, port):
        self.logger = Logger("VideoSender")
        self.target_addr = (target_ip, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.logger.info(f"UDP Sender initialized. Target: {target_ip}:{port}")

    def send_frame(self, frame, quality=70):
        """
        프레임을 JPEG로 압축하여 전송합니다.
        :param frame: OpenCV 이미지 객체
        :param quality: JPEG 압축 품질 (1-100, 낮을수록 용량 작고 빠름)
        """
        try:
            # 1. 이미지 크기 조정 (속도 및 패킷 크기 최적화를 위해 필요한 경우)
            # frame = cv2.resize(frame, (640, 480))

            # 2. JPEG 인코딩
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            result, img_encode = cv2.imencode('.jpg', frame, encode_param)
            
            if not result:
                return False

            data = np.array(img_encode)
            byte_data = data.tobytes()

            # 3. UDP 최대 패킷 크기 체크 (64KB 제한)
            if len(byte_data) > 65507:
                self.logger.warning(f"Frame too large: {len(byte_data)} bytes. Lowering quality.")
                return False

            # 4. 전송
            self.sock.sendto(byte_data, self.target_addr)
            return True

        except Exception as e:
            self.logger.error(f"Failed to send frame: {e}")
            return False

    def close(self):
        self.sock.close()


class VideoReceiver:
    """
    [PC2 - Hub] PC3로부터 전달받은 UDP 패킷을 다시 이미지로 복원하는 클래스
    """
    def __init__(self, port):
        self.logger = Logger("VideoReceiver")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # 모든 IP로부터의 연결 수신
        try:
            self.sock.bind(('0.0.0.0', port))
            # 소켓 버퍼 크기 확장 (OS 레벨에서 패킷 유실 방지)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
            self.logger.info(f"UDP Receiver listening on port {port}")
        except Exception as e:
            self.logger.error(f"Bind failed: {e}")

    def receive_frame(self):
        """
        패킷을 수신하여 OpenCV 프레임으로 변환합니다.
        """
        try:
            # UDP 최대 허용 크기만큼 수신
            data, addr = self.sock.recvfrom(65535)
            
            if not data:
                return None, None

            # 1. 바이트 데이터를 numpy 배열로 변환
            nparr = np.frombuffer(data, np.uint8)
            
            # 2. 이미지 디코딩
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            return frame, addr

        except Exception as e:
            self.logger.error(f"Reception error: {e}")
            return None, None

    def close(self):
        self.sock.close()