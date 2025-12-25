import threading
import time
import yaml

from network.udp_handler import UDPFrameReceiver, UDPFrameSender
from network.tcp_server import TCPServer
from network.tcp_client import TCPClient
from core.engine import SmartCartEngine
from database.db_handler import DBHandler
from database.product_dao import ProductDAO
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

        # -------------------------
        # Business Engine
        # -------------------------
        self.engine = SmartCartEngine(self.product_dao)

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
        level = DangerLevel(data["level"])
        if level == self.engine.last_obstacle_level:
            return

        self.engine.last_obstacle_level = level

        if level >= DangerLevel.CAUTION:
            msg = Protocol.ui_command(
                UICommand.SHOW_ALARM,
                data,
            )
            self.ui_client.send_request(msg)

    def _handle_product(self, data: dict):
        product_id = data["product_id"]
        if not self.engine.handle_product_detected(product_id):
            return

        product = self.product_dao.get_product_by_id(product_id)
        if not product:
            return

        msg = Protocol.ui_command(
            UICommand.ADD_TO_CART,
            product,
        )
        self.ui_client.send_request(msg)

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

        self.ai_event_server.start()


if __name__ == "__main__":
    MainPC2Hub().run()
