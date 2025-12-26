import threading
import time

from network.udp_handler import UDPFrameReceiver, UDPFrameSender
from network.tcp_server import TCPServer
from network.tcp_client import TCPClient
from core.engine import SmartCartEngine
from database.db_handler import DBHandler
from database.product_dao import ProductDAO
from database.transaction_dao import TransactionDAO
from database.obstacle_log_dao import ObstacleLogDAO
from common.config import config
from common.protocols import (
    Protocol,
    MessageType,
    AIEvent,
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
        if config is None:
            raise RuntimeError("Configuration could not be loaded. Exiting.")

        # -------------------------
        # Database
        # -------------------------
        self.db_handler = DBHandler(config.db.aws_rds.dict())
        self.product_dao = ProductDAO(self.db_handler)
        self.tx_dao = TransactionDAO(self.db_handler)
        self.obstacle_dao = ObstacleLogDAO(self.db_handler)
        
        # -------------------------
        # UI Client (for sending commands to UI)
        # -------------------------
        self.ui_client = TCPClient(
            host=config.network.pc3_ui.ip,
            port=config.network.pc3_ui.ui_port,
        )

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
        # Session
        # -------------------------
        cart_code = config.network.pc2_main.cart_code
        try:
            self.session_id = self.tx_dao.start_session(cart_code)
            self.logger.log_event("SESSION", f"Session started with cart_code {cart_code}: session_id={self.session_id}")
        except Exception as e:
            self.logger.log_event("ERROR", f"Failed to start initial session for cart {cart_code}: {e}")
            raise RuntimeError(f"MainPC2Hub cannot start without a valid session.") from e


        # -------------------------
        # UDP Forwarders (PC2 → AI)
        # -------------------------
        ai_ip = config.network.pc1_ai.ip
        self.front_forwarder = UDPFrameSender(
            host=ai_ip,
            port=config.network.pc1_ai.udp_front_port,
        )
        self.cart_forwarder = UDPFrameSender(
            host=ai_ip,
            port=config.network.pc1_ai.udp_cart_port,
        )

        # -------------------------
        # UDP Receivers (from a hypothetical PC3)
        # We need to define ports for PC2 to listen on
        # These are not in the current network config, so we'll use temporary ports
        # This highlights a gap in the config design.
        # -------------------------
        self.front_receiver = UDPFrameReceiver(
            "0.0.0.0",
            config.network.pc2_main.udp_front_cam_port,
        )
        self.cart_receiver = UDPFrameReceiver(
            "0.0.0.0",
            config.network.pc2_main.udp_cart_cam_port,
        )
        # self.logger.log_event("WARN", "Using placeholder UDP receiver ports (9000, 9001)")


        # -------------------------
        # UI Request Server (TCP PULL from UI)
        # -------------------------
        self.ui_request_server = TCPServer(
            host="0.0.0.0",
            port=config.network.pc2_main.ui_port,
            handler=self.handle_ui_request,
        )

        # -------------------------
        # AI Event Server (TCP PUSH from AI)
        # -------------------------
        self.ai_event_server = TCPServer(
            host="0.0.0.0",
            port=config.network.pc2_main.event_port,
            handler=self.handle_ai_event,
        )

        self.logger.log_event("SYSTEM", f"Main PC2 Hub initialized, listening for AI events on port {config.network.pc2_main.event_port}")

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

        cart_code = config.network.pc2_main.cart_code
        try:
            self.session_id = self.tx_dao.start_session(cart_code)
            self.logger.log_event(
                "SESSION",
                f"Session started by UI: {self.session_id}",
            )
            return {"status": "OK", "session_id": self.session_id}
        except Exception as e:
            self.logger.log_event("ERROR", f"UI-initiated session failed for cart {cart_code}: {e}")
            return {"status": "ERROR", "reason": "Failed to start session"}
    
    def _handle_ui_checkout(self) -> dict:
        if not self.session_id:
            return {"status": "NO_ACTIVE_SESSION"}

        # 1. Get all cart items from the database for the current session
        cart_items = self.tx_dao.list_cart_items(self.session_id)
        if not cart_items:
            # Handle empty cart checkout? For now, we proceed.
            self.logger.log_event("SESSION", "Checkout initiated for an empty cart.")
            total_amount = 0
            total_items = 0
        else:
            # 2. Calculate total amount and item count
            total_amount = sum(item['total_price'] for item in cart_items)
            total_items = sum(item['quantity'] for item in cart_items)

        # 3. Create the order with the calculated totals
        order_id = self.tx_dao.create_order(
            session_id=self.session_id,
            total_amount=total_amount,
            total_items=total_items
        )

        # 4. End the session
        self.tx_dao.end_session(self.session_id)

        self.logger.log_event(
            "SESSION",
            f"Checkout completed: order_id={order_id}, total_amount={total_amount}, total_items={total_items}",
        )

        # 5. Notify the UI
        msg = Protocol.ui_command(
            UICommand.CHECKOUT_DONE,
            {"order_id": order_id, "total_amount": total_amount},
        )
        self.ui_client.send_request(msg)

        # 6. Reset session state
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
