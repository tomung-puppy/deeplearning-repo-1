import cv2
import socket
import numpy as np

class UDPHandler:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_frame(self, frame):
        """이미지를 압축하여 UDP로 전송 (PC3 -> PC2)"""
        # 이미지 크기 조절 및 인코딩 (속도를 위해 JPEG 사용)
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        data = buffer.tobytes()
        
        # UDP 패킷 크기 제한(64KB) 주의: 실제 구현 시 프레임 분할이 필요할 수 있음
        if len(data) < 65507:
            self.sock.sendto(data, (self.ip, self.port))

    def receive_frame(self):
        """UDP 패킷을 수신하여 이미지로 복구 (PC2 수신용)"""
        self.sock.bind((self.ip, self.port))
        while True:
            data, _ = self.sock.recvfrom(65536)
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is not None:
                yield frame