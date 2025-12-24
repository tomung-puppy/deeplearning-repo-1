import sys
import cv2
import threading
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt5.QtCore import pyqtSignal, QThread
from src.network.udp_handler import VideoSender
from src.network.tcp_server import UIUpdateServer

"""

"""

class CartApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Shopping Cart")
        self.init_ui()
        
        # 영상 송신 모듈 (PC2의 IP와 Port 입력)
        self.video_sender = VideoSender(target_ip='192.168.0.20', port=9999)
        
        # PC2로부터 상태를 업데이트 받을 서버 시작
        self.update_receiver = UIUpdateServer(port=7000)
        self.update_receiver.data_received.connect(self.update_dashboard)
        
        # 카메라 스레드 시작
        self.is_running = True
        threading.Thread(target=self.camera_loop, daemon=True).start()

    def init_ui(self):
        layout = QVBoxLayout()
        self.info_label = QLabel("상품을 카트에 담아주세요.")
        self.price_label = QLabel("합계: 0원")
        layout.addWidget(self.info_label)
        layout.addWidget(self.price_label)
        
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def camera_loop(self):
        cap = cv2.VideoCapture(0)
        while self.is_running:
            ret, frame = cap.read()
            if ret:
                # 영상을 압축하여 PC2로 전송
                self.video_sender.send_frame(frame)
        cap.release()

    def update_dashboard(self, data):
        """PC2로부터 받은 데이터를 UI에 반영 (TCP 수신 결과)"""
        # data: CartUpdate 객체
        self.info_label.setText(f"감지된 상품: {data.item_name}")
        self.price_label.setText(f"합계: {data.total_price}원")
        
        if data.is_danger:
            self.info_label.setText("⚠️ 장애물 주의! ⚠️")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CartApp()
    window.show()
    sys.exit(app.exec_())