import threading
import time
import yaml

from network.udp_handler import UDPFrameReceiver, UDPFrameSender
from network.tcp_server import TCPServer
from network.tcp_client import TCPClient
from core.engine import SmartCartEngine
from database.db_handler import DBHandler
from database.product_dao import ProductDAO
from database.transaction_dao import TransactionDAO
from database.obstacle_log_dao import ObstacleLogDAO
from common.constants import (
    UDP_PORT_FRONT_CAM,
    UDP_PORT_CART_CAM,
    AI_UDP_PORT_FRONT,
    AI_UDP_PORT_CART,
    TCP_PORT_UI,
    TCP_PORT_MAIN_EVT,
)
from common.protocols import (
    Protocol,
    MessageType,
    AIEvent,
    DangerLevel,
    UICommand,
    UIRequest
)
from utils.logger import SystemLogger


class MainPC2Hub:
    """
    PC2 Main Hub (Gateway + Orchestrator)

    - Receives frames via UDP from PC3
    - Forwards frames via UDP to AI Server
    - Receives AI events via TCP (PUSH)
    - Applies business logic
    """

    def __init__(self):
        self.logger = SystemLogger(name="MainHub")
        self.config = self._load_config()

        # -------------------------
        # Database
        # -------------------------
        self.db_handler = DBHandler(self.config["db"])
        self.product_dao = ProductDAO(self.db_handler)
        self.tx_dao = TransactionDAO(self.db_handler)
        self.obstacle_dao = ObstacleLogDAO(self.db_handler)

        # -------------------------
        # Session
        # -------------------------
        cart_code = self.config["network"]["cart"]["code"]
        self.session_id = self.tx_dao.start_session(cart_code)
        self.logger.log_event("SESSION", f"Session started: {self.session_id}")

        # -------------------------
        # Business Engine
        # -------------------------
        self.engine = SmartCartEngine(
            product_dao=self.product_dao,
            transaction_dao=self.tx_dao,
            obstacle_dao=self.obstacle_dao,
            ui_client=self.ui_client,
        )

        # -------------------------
        # UDP Receivers (PC3 → PC2)
        # -------------------------
        self.front_receiver = UDPFrameReceiver(
            "0.0.0.0",
            UDP_PORT_FRONT_CAM,
        )
        self.cart_receiver = UDPFrameReceiver(
            "0.0.0.0",
            UDP_PORT_CART_CAM,
        )

        # -------------------------
        # UDP Forwarders (PC2 → AI)
        # -------------------------
        ai_ip = self.config["network"]["pc1_ai"]["ip"]

        self.front_forwarder = UDPFrameSender(
            ai_ip,
            AI_UDP_PORT_FRONT,
        )
        self.cart_forwarder = UDPFrameSender(
            ai_ip,
            AI_UDP_PORT_CART,
        )

        # -------------------------
        # UI Client
        # -------------------------
        self.ui_client = TCPClient(
            self.config["network"]["pc3_ui"]["ip"],
            TCP_PORT_UI,
        )

        # -------------------------
        # UI Request Server (TCP PULL)
        # -------------------------
        self.ui_request_server = TCPServer(
            "0.0.0.0",
            TCP_PORT_UI,
            self.handle_ui_request,
        )



        # -------------------------
        # AI Event Server (TCP PUSH)
        # -------------------------
        self.ai_event_server = TCPServer(
            "0.0.0.0",
            TCP_PORT_MAIN_EVT,
            self.handle_ai_event,
        )

        self.logger.log_event("SYSTEM", "Main PC2 Hub initialized")

    # =========================
    # Config
    # =========================
    def _load_config(self) -> dict:
        with open("configs/db_config.yaml", "r") as f:
            db_cfg = yaml.safe_load(f)
        with open("configs/network_config.yaml", "r") as f:
            net_cfg = yaml.safe_load(f)
        return {"db": db_cfg, "network": net_cfg}

    # =========================
    # UDP Forwarding Loops
    # =========================
    def forward_front_cam(self):
        self.logger.log_event("NET", "Front cam forwarding started")
        for jpeg_bytes in self.front_receiver.receive_packets():
            self.front_forwarder.send_frame(jpeg_bytes)

    def forward_cart_cam(self):
        self.logger.log_event("NET", "Cart cam forwarding started")
        for jpeg_bytes in self.cart_receiver.receive_packets():
            self.cart_forwarder.send_frame(jpeg_bytes)

    # =========================
    # UI Request Handler
    # =========================
    def handle_ui_request(self, message: dict) -> dict:
        if not Protocol.validate(message):
            return {"status": "ERROR", "reason": "Invalid protocol"}

        if MessageType(message["header"]["type"]) != MessageType.UI_REQ:
            return {"status": "IGNORED"}

        cmd = UIRequest(message["payload"]["event"])

        if cmd == UIRequest.START_SESSION:
            return self._handle_ui_start()

        if cmd == UIRequest.CHECKOUT:
            return self._handle_ui_checkout()

        return {"status": "UNKNOWN_CMD"}
    
    def _handle_ui_start(self) -> dict:
        # 이미 세션이 있으면 무시
        if self.session_id:
            return {"status": "ALREADY_STARTED"}

        cart_code = self.config["network"]["cart"]["code"]
        self.session_id = self.tx_dao.start_session(cart_code)

        self.logger.log_event(
            "SESSION",
            f"Session started by UI: {self.session_id}",
        )

        return {"status": "OK", "session_id": self.session_id}
    
    def _handle_ui_checkout(self) -> dict:
        if not self.session_id:
            return {"status": "NO_ACTIVE_SESSION"}

        # 주문 생성
        order_id = self.tx_dao.create_order(self.session_id)

        # 세션 종료
        self.tx_dao.close_session(self.session_id)

        self.logger.log_event(
            "SESSION",
            f"Checkout completed: order_id={order_id}",
        )

        # UI에 완료 알림
        msg = Protocol.ui_command(
            UICommand.CHECKOUT_DONE,
            {"order_id": order_id},
        )
        self.ui_client.send_request(msg)

        # 세션 초기화
        self.session_id = None
        self.engine.reset()

        return {"status": "OK", "order_id": order_id}




    # =========================
    # AI Event Handler
    # =========================
    def handle_ai_event(self, message: dict) -> dict:
        if not Protocol.validate(message):
            return {"status": "ERROR"}

        if MessageType(message["header"]["type"]) != MessageType.AI_EVT:
            return {"status": "IGNORED"}

        event = AIEvent(message["payload"]["event"])
        data = message["payload"]["data"]

        if event == AIEvent.OBSTACLE_DANGER:
            self._handle_obstacle(data)
        elif event == AIEvent.PRODUCT_DETECTED:
            self._handle_product(data)

        return {"status": "OK"}

    def _handle_obstacle(self, data: dict):
        self.engine.process_obstacle_event(data, self.session_id)


    def _handle_product(self, data: dict):
        self.engine.process_product_event(data, self.session_id)

    # =========================
    # Lifecycle
    # =========================
    def run(self):
        threading.Thread(
            target=self.forward_front_cam,
            daemon=True,
        ).start()

        threading.Thread(
            target=self.forward_cart_cam,
            daemon=True,
        ).start()

        threading.Thread(
        target=self.ui_request_server.start,
        daemon=True,
        ).start()

        self.ai_event_server.start()


if __name__ == "__main__":
    MainPC2Hub().run()
