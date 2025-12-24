import sys
import cv2
import json
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QTextEdit
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QImage, QPixmap
from network.udp_handler import UDPHandler
from network.tcp_server import TCPServer

# 1. 영상 수신을 위한 스레드 (UDP)
class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(np.ndarray)

    def __init__(self, port):
        super().__init__()
        self.udp_handler = UDPHandler('0.0.0.0', port)

    def run(self):
        # PC2가 보낸 프레임을 수신하여 UI로 전달
        for frame in self.udp_handler.receive_frame():
            self.change_pixmap_signal.emit(frame)

# 2. 메인 대시보드 클래스
class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Shopping Cart - User Interface")
        self.resize(1000, 700)
        
        self.init_ui()
        
        # PC2로부터 명령(알람, 상품정보)을 받기 위한 TCP 서버 시작
        self.tcp_receiver = TCPServer('0.0.0.0', 7000, self.handle_server_command)
        self.tcp_thread = QThread()
        self.tcp_receiver.moveToThread(self.tcp_thread)
        self.tcp_thread.started.connect(self.tcp_receiver.start)
        self.tcp_thread.start()

        # 카메라 스레드 시작 (전방뷰 6000, 카트뷰 6001 포트 가정)
        self.front_cam_thread = VideoThread(6000)
        self.front_cam_thread.change_pixmap_signal.connect(self.update_front_image)
        self.front_cam_thread.start()

    def init_ui(self):
        """UI 레이아웃 초기화"""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)

        # 왼쪽: 카메라 뷰 섹션
        self.video_layout = QVBoxLayout()
        self.front_label = QLabel("Front View (Obstacle Detection)")
        self.front_label.setFixedSize(640, 360)
        self.front_label.setStyleSheet("background-color: black; color: white;")
        self.video_layout.addWidget(self.front_label)
        
        # 알람 메시지 표시줄
        self.alarm_label = QLabel("Status: Normal")
        self.alarm_label.setStyleSheet("font-size: 20px; font-weight: bold; color: green;")
        self.video_layout.addWidget(self.alarm_label)
        
        self.main_layout.addLayout(self.video_layout)

        # 오른쪽: 장바구니 리스트 섹션
        self.cart_layout = QVBoxLayout()
        self.cart_label = QLabel("🛒 Shopping Cart Items")
        self.cart_display = QTextEdit()
        self.cart_display.setReadOnly(True)
        self.cart_layout.addWidget(self.cart_label)
        self.cart_layout.addWidget(self.cart_display)
        
        self.main_layout.addLayout(self.cart_layout)

    def update_front_image(self, cv_img):
        """수신된 OpenCV 이미지를 QLabel에 표시"""
        qt_img = self.convert_cv_to_qt(cv_img)
        self.front_label.setPixmap(qt_img)

    def convert_cv_to_qt(self, cv_img):
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(convert_to_Qt_format)

    def handle_server_command(self, request):
        """PC2(메인)에서 온 명령 처리"""
        cmd = request.get('cmd')
        
        if cmd == 'SHOW_ALARM':
            self.alarm_label.setText(f"⚠️ {request['message']}")
            self.alarm_label.setStyleSheet("font-size: 20px; font-weight: bold; color: red;")
        
        elif cmd == 'ADD_CART':
            data = request['data']
            item_info = f"- {data['product_name']}: {data['price']}원\n"
            self.cart_display.append(item_info)
            
        return {"status": "success"}

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Dashboard()
    window.show()
    sys.exit(app.exec())