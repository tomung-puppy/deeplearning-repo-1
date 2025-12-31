# ui/ui_controller_v2.py
"""
Enhanced UI Controller with full DB integration
- Manages shopping sessions
- Logs obstacles and safety events
- Real-time cart updates with notifications
"""

import threading
import socket
import json
from typing import Optional
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

from ui.dashboard_v2 import CartDashboard, DangerLevel
from common.config import config
from common.protocols import (
    Protocol,
    MessageType,
    UICommand,
    UIRequest,
)
from database.db_handler import DBHandler
from database.transaction_dao import TransactionDAO
from database.product_dao import ProductDAO
from database.obstacle_log_dao import ObstacleLogDAO


class UIEventSignals(QObject):
    """Qt Signals for thread-safe UI updates"""

    cart_updated = pyqtSignal(list, int)  # items, total
    product_added = pyqtSignal(str)  # product_name
    danger_updated = pyqtSignal(int, str)  # level, message
    status_changed = pyqtSignal(str)


class UIController:
    """
    Enhanced UI Controller with DB integration
    - Manages shopping sessions
    - Logs all events to database
    - Real-time cart synchronization
    """

    def __init__(self, dashboard: CartDashboard, main_pc2_ip: str, cart_id: int = 1):
        self.dashboard = dashboard
        self.main_pc2_ip = main_pc2_ip
        self.cart_id = cart_id

        if config is None:
            raise RuntimeError("Configuration could not be loaded.")

        # Database
        try:
            self.db = DBHandler(config.db.aws_rds)
            self.tx_dao = TransactionDAO(self.db)
            self.product_dao = ProductDAO(self.db)
            self.obstacle_dao = ObstacleLogDAO(self.db)
            print("[UI Controller] Database connected successfully")
        except Exception as e:
            print(f"[UI Controller] Database connection failed: {e}")
            self.db = None
            self.tx_dao = None
            self.product_dao = None
            self.obstacle_dao = None

        # Session state
        self.current_session_id: Optional[int] = None
        self.last_added_product_name: Optional[str] = None

        # Signals
        self.signals = UIEventSignals()
        self._bind_signals()
        self._bind_buttons()

        # Start TCP server
        self.server_thread = threading.Thread(
            target=self._tcp_server_loop,
            daemon=True,
        )
        self.server_thread.start()

        print(f"[UI Controller] Initialized for cart_id={cart_id}")

    # =========================
    # Signal Bindings
    # =========================
    def _bind_signals(self):
        """Connect signals to dashboard slots"""
        self.signals.cart_updated.connect(self.dashboard.update_cart_display)
        self.signals.product_added.connect(self.dashboard.show_product_added)
        self.signals.danger_updated.connect(self.dashboard.set_danger_level)
        self.signals.status_changed.connect(lambda msg: print(f"[UI] Status: {msg}"))

    def _bind_buttons(self):
        """Connect dashboard buttons to handlers"""
        self.dashboard.start_shopping_signal.connect(self._on_start_shopping)
        self.dashboard.confirm_checkout_signal.connect(self._on_checkout)
        self.dashboard.update_quantity_signal.connect(self._on_update_quantity)
        self.dashboard.remove_item_signal.connect(self._on_remove_item)

    # =========================
    # Shopping Session Management
    # =========================
    def _on_start_shopping(self):
        """Handle start shopping event - request Main Hub to start session"""
        print("[UI Controller] Requesting new shopping session from Main Hub...")

        try:
            # Send START_SESSION request to Main Hub
            msg = Protocol.ui_request(UIRequest.START_SESSION, {})

            # Send and wait for response
            response = self._send_to_main_sync(msg)

            if response and response.get("status") == "OK":
                session_id = response.get("session_id")
                self.current_session_id = session_id
                self.dashboard.set_session_id(session_id)
                print(
                    f"[UI Controller] Session started by Main Hub: session_id={session_id}"
                )
            else:
                print(f"[UI Controller] Failed to start session: {response}")

        except Exception as e:
            print(f"[UI Controller] Error starting session: {e}")

    def _on_checkout(self):
        """Handle checkout event - delegate to Main Hub"""
        print("[UI Controller] 🛒 CHECKOUT button clicked")
        print(f"[UI Controller]   Current session_id: {self.current_session_id}")

        if not self.current_session_id:
            print("[UI Controller] ❌ No active session")
            return

        try:
            # Send checkout request to Main Hub
            # Main Hub will handle:
            # - Getting cart items
            # - Creating order with totals
            # - Ending session
            msg = Protocol.ui_request(
                UIRequest.CHECKOUT,
                {"session_id": self.current_session_id},
            )
            print(f"[UI Controller] 📤 Sending CHECKOUT request to Main Hub...")
            self._send_to_main(msg)

            print(
                f"[UI Controller] ✅ Checkout request sent for session {self.current_session_id}"
            )

            # Reset local session tracking
            # (Main Hub will send CHECKOUT_DONE to confirm)
            self.current_session_id = None

        except Exception as e:
            print(f"[UI Controller] ❌ Error during checkout: {e}")

    def _on_update_quantity(self, product_id: int, new_quantity: int):
        """Handle quantity update request"""
        print(
            f"[UI Controller] Updating quantity: product_id={product_id}, new_quantity={new_quantity}"
        )

        if not self.current_session_id:
            print("[UI Controller] ❌ No active session")
            return

        try:
            msg = Protocol.ui_request(
                UIRequest.UPDATE_QUANTITY,
                {
                    "session_id": self.current_session_id,
                    "product_id": product_id,
                    "quantity": new_quantity,
                },
            )
            self._send_to_main(msg)
            print(f"[UI Controller] ✅ Quantity update request sent")
        except Exception as e:
            print(f"[UI Controller] ❌ Error updating quantity: {e}")

    def _on_remove_item(self, product_id: int):
        """Handle item removal request"""
        print(f"[UI Controller] Removing item: product_id={product_id}")

        if not self.current_session_id:
            print("[UI Controller] ❌ No active session")
            return

        try:
            msg = Protocol.ui_request(
                UIRequest.REMOVE_ITEM,
                {
                    "session_id": self.current_session_id,
                    "product_id": product_id,
                },
            )
            self._send_to_main(msg)
            print(f"[UI Controller] ✅ Item removal request sent")
        except Exception as e:
            print(f"[UI Controller] ❌ Error removing item: {e}")

    # =========================
    # TCP Communication
    # =========================
    def _send_to_main(self, message: dict):
        """Send message to Main Hub (fire and forget)"""
        port = config.network.pc2_main.ui_port
        print(f"[UI Controller] Connecting to Main Hub at {self.main_pc2_ip}:{port}")
        try:
            import struct

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                s.connect((self.main_pc2_ip, port))

                # Send with length prefix (matching TCPServer protocol)
                payload = json.dumps(message).encode("utf-8")
                header = struct.pack(">I", len(payload))
                s.sendall(header + payload)

                print(
                    f"[UI Controller] ✅ Sent to Main Hub: type={message['header']['type']}"
                )
        except Exception as e:
            print(f"[UI Controller] ❌ Send error to {self.main_pc2_ip}:{port}: {e}")

    def _send_to_main_sync(self, message: dict) -> dict:
        """Send message to Main Hub and wait for response (length-prefixed protocol)"""
        port = config.network.pc2_main.ui_port
        try:
            import struct

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                s.connect((self.main_pc2_ip, port))

                # Send with length prefix (4 bytes big-endian)
                payload = json.dumps(message).encode("utf-8")
                header = struct.pack(">I", len(payload))
                s.sendall(header + payload)

                # Receive response with length prefix
                header_data = self._recv_exact(s, 4)
                response_length = struct.unpack(">I", header_data)[0]
                response_data = self._recv_exact(s, response_length)

                response = json.loads(response_data.decode("utf-8"))
                print(f"[UI Controller] Received from Main Hub: {response}")
                return response
        except Exception as e:
            print(f"[UI Controller] Sync send error to {self.main_pc2_ip}:{port}: {e}")
            return None

    def _recv_exact(self, sock: socket.socket, size: int) -> bytes:
        """Receive exact number of bytes from socket"""
        buffer = bytearray()
        while len(buffer) < size:
            chunk = sock.recv(size - len(buffer))
            if not chunk:
                raise ConnectionError("Connection closed")
            buffer.extend(chunk)
        return bytes(buffer)

    def _tcp_server_loop(self):
        """TCP server to receive commands from Main Hub"""
        port = config.network.pc3_ui.ui_port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", port))
        sock.listen(5)

        print(f"[UI Controller] TCP server listening on port {port}")

        while True:
            try:
                conn, addr = sock.accept()
                print(f"[UI Controller] Connection from {addr}")
                with conn:
                    self._handle_connection(conn)
            except Exception as e:
                print(f"[UI Controller] Connection error: {e}")

    def _handle_connection(self, conn: socket.socket):
        """Handle incoming TCP connection"""
        # Read length-prefixed message
        header = conn.recv(4)
        if not header or len(header) != 4:
            return

        import struct

        payload_length = struct.unpack(">I", header)[0]

        # Read full payload
        data = bytearray()
        while len(data) < payload_length:
            chunk = conn.recv(min(8192, payload_length - len(data)))
            if not chunk:
                break
            data.extend(chunk)

        if len(data) < payload_length:
            print(f"[UI Controller] Incomplete message received")
            return

        self._handle_message(bytes(data))

    def _handle_message(self, raw: bytes):
        """Parse and handle incoming message"""
        try:
            message = Protocol.parse(raw.decode())
        except Exception as e:
            print(f"[UI Controller] Error parsing message: {e}")
            return

        msg_type = MessageType(message["header"]["type"])
        if msg_type != MessageType.UI_CMD:
            return

        payload = message["payload"]
        cmd = UICommand(payload["command"])

        print(f"[UI Controller] Received command: {cmd}")

        # Dispatch command
        if cmd == UICommand.UPDATE_CART:
            self._handle_update_cart(payload["content"])
        elif cmd == UICommand.SHOW_ALARM:
            self._handle_show_alarm(payload["content"])
        elif cmd == UICommand.ADD_TO_CART:
            self._handle_add_to_cart(payload["content"])
        elif cmd == UICommand.CHECKOUT_DONE:
            self._handle_checkout_done(payload["content"])

    # =========================
    # Command Handlers
    # =========================
    def _handle_update_cart(self, content: dict):
        """Handle UPDATE_CART command"""
        items = content.get("items", [])
        total = content.get("total", 0)

        print(f"[UI Controller] UPDATE_CART: {len(items)} items, total=₩{total}")

        # Update UI
        self.signals.cart_updated.emit(items, total)

        # Show toast for newly added product
        if items and self.last_added_product_name:
            self.signals.product_added.emit(self.last_added_product_name)
            self.last_added_product_name = None

    def _handle_add_to_cart(self, content: dict):
        """Handle ADD_TO_CART command (legacy)"""
        product_id = content.get("product_id")
        product_name = content.get("name", "Unknown Product")

        print(f"[UI Controller] ADD_TO_CART: {product_name}")

        # Store for toast notification
        self.last_added_product_name = product_name

        # Refresh cart from DB
        if self.current_session_id and self.tx_dao:
            try:
                cart_items = self.tx_dao.list_cart_items(self.current_session_id)
                total = sum(item["subtotal"] for item in cart_items)
                self.signals.cart_updated.emit(cart_items, total)
                self.signals.product_added.emit(product_name)
            except Exception as e:
                print(f"[UI Controller] Error refreshing cart: {e}")

    def _handle_show_alarm(self, content: dict):
        """Handle SHOW_ALARM command"""
        level = content.get("level", 0)
        object_type = content.get("object_type", "obstacle")
        distance = content.get("distance", 0)

        # Map level to DangerLevel
        danger_level = DangerLevel(level)

        # Create message
        if danger_level == DangerLevel.CRITICAL:
            message = f"⚠️ {object_type.title()} {distance:.1f}m ahead!"
        elif danger_level == DangerLevel.CAUTION:
            message = f"Caution: {object_type.title()} detected"
        else:
            message = "Clear"

        print(f"[UI Controller] SHOW_ALARM: {danger_level.name} - {message}")

        # Update UI
        self.signals.danger_updated.emit(danger_level.value, message)

        # Log to database
        if self.current_session_id and self.obstacle_dao:
            try:
                self.obstacle_dao.log_obstacle(
                    session_id=self.current_session_id,
                    object_type=object_type,
                    distance=distance,
                    speed=content.get("speed", 0),
                    direction=content.get("direction", "front"),
                    is_warning=(danger_level != DangerLevel.NORMAL),
                )
            except Exception as e:
                print(f"[UI Controller] Error logging obstacle: {e}")

    def _handle_checkout_done(self, content: dict):
        """Handle CHECKOUT_DONE command"""
        print("[UI Controller] Checkout completed by Main Hub")
        self.current_session_id = None
