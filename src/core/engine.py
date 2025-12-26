# src/core/engine.py
import time
from typing import Optional

from common.protocols import DangerLevel, Protocol, UICommand
from database.obstacle_log_dao import ObstacleLogDAO
from database.product_dao import ProductDAO
from database.transaction_dao import TransactionDAO
from network.tcp_client import TCPClient


class SmartCartEngine:
    """
    Business decision engine.
    - Encapsulates business logic for handling events.
    - Processes data from AI events, interacts with the database, and sends commands to the UI.
    """

    DUPLICATE_PRODUCT_INTERVAL_SEC = 2.0

    def __init__(
        self,
        product_dao: ProductDAO,
        transaction_dao: TransactionDAO,
        obstacle_dao: ObstacleLogDAO,
        ui_client: TCPClient,
    ):
        self.product_dao = product_dao
        self.tx_dao = transaction_dao
        self.obstacle_dao = obstacle_dao
        self.ui_client = ui_client

        # State for obstacle danger level
        self.last_obstacle_level: DangerLevel = DangerLevel.NORMAL

        # State for product de-duplication
        self._last_product_id: Optional[int] = None
        self._last_product_ts: float = 0.0

    def process_obstacle_event(self, data: dict, session_id: int):
        """Processes an obstacle danger event from the AI."""
        level = DangerLevel(data["level"])

        # 1. Log event to database
        self.obstacle_dao.log_obstacle(
            session_id=session_id,
            object_type=data.get("object_type", "UNKNOWN"),
            distance=data.get("distance", 1000),
            speed=data.get("speed", 0),
            direction=data.get("direction", "stop"),
            is_warning=level >= DangerLevel.CAUTION,
        )

        # 2. Avoid sending duplicate events
        if level == self.last_obstacle_level:
            return
        self.last_obstacle_level = level

        # 3. Send warning to UI if danger level is high enough
        if level >= DangerLevel.CAUTION:
            msg = Protocol.ui_command(
                UICommand.SHOW_ALARM,
                data,
            )
            self.ui_client.send_request(msg)

    def process_product_event(self, data: dict, session_id: int):
        """Processes a product detection event from the AI."""
        product_id = data["product_id"]

        # 1. Debounce product detection
        if not self._is_new_product_detection(product_id):
            return

        # 2. Get product details from DB
        product = self.product_dao.get_product_by_id(product_id)
        if not product:
            print(f"[Engine] WARN: Product with ID {product_id} not found in database.")
            return

        # 3. Add item to cart in DB
        self.tx_dao.add_cart_item(
            session_id=session_id,
            product_id=product_id,
            quantity=1,
        )

        # 4. Send command to UI to update cart
        msg = Protocol.ui_command(
            UICommand.ADD_TO_CART,
            product,
        )
        self.ui_client.send_request(msg)

    def _is_new_product_detection(self, product_id: int) -> bool:
        """Internal helper to check for duplicate product detections."""
        now = time.time()

        is_duplicate = (
            self._last_product_id == product_id and
            (now - self._last_product_ts) < self.DUPLICATE_PRODUCT_INTERVAL_SEC
        )

        if is_duplicate:
            return False

        self._last_product_id = product_id
        self._last_product_ts = now
        return True

    def reset(self) -> None:
        """Resets the engine's session state."""
        self.last_obstacle_level = DangerLevel.NORMAL
        self._last_product_id = None
        self._last_product_ts = 0.0
