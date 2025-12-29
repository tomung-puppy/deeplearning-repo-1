# database/transaction_dao.py
from typing import Dict, List, Optional
from datetime import datetime


class TransactionDAO:
    """
    Transaction & Session Data Access Object
    """

    def __init__(self, db_handler):
        self.db = db_handler

    # =========================
    # Shopping Session
    # =========================
    def start_session(self, cart_id: int) -> int:
        """Start new cart session"""
        sql = """
        INSERT INTO shopping_sessions (cart_id, start_time, status)
        VALUES (%s, NOW(), 'ACTIVE')
        """
        session_id = self.db.insert(sql, (cart_id,))
        return session_id 

    def end_session(self, session_id: int) -> None:
        sql = """
        UPDATE shopping_sessions
        SET end_time = NOW(),
            status = 'COMPLETED'
        WHERE session_id = %s
        """
        self.db.execute(sql, (session_id,))

    def get_active_session(self, cart_id: int) -> Optional[Dict]:
        sql = """
        SELECT session_id
        FROM shopping_sessions
        WHERE cart_id = %s
          AND status = 'ACTIVE'
        LIMIT 1
        """
        return self.db.fetch_one(sql, (cart_id,))

    # =========================
    # Cart Items
    # =========================
    def add_cart_item(
        self,
        session_id: int,
        product_id: int,
        quantity: int = 1,
    ) -> None:
        sql = """
        INSERT INTO cart_items (session_id, product_id, quantity)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            quantity = quantity + VALUES(quantity)
        """
        self.db.execute(sql, (session_id, product_id, quantity))

    def list_cart_items(self, session_id: int) -> List[Dict]:
        """Get all items in cart with product info"""
        sql = """
        SELECT
            ci.item_id,
            ci.product_id,
            p.name as product_name,
            p.price,
            ci.quantity,
            (ci.quantity * p.price) AS subtotal
        FROM cart_items ci
        JOIN products p ON ci.product_id = p.product_id
        WHERE ci.session_id = %s
        ORDER BY ci.added_at DESC
        """
        return self.db.fetch_all(sql, (session_id,))


    # =========================
    # Order / Checkout
    # =========================
    def create_order(
        self,
        session_id: int,
        total_amount: int,
        total_items: int,
    ) -> int:
        sql = """
        INSERT INTO orders (
            session_id,
            total_amount,
            total_items
        )
        VALUES (%s, %s, %s)
        """
        return self.db.insert(sql, (session_id, total_amount, total_items))

    def add_order_detail(
        self,
        order_id: int,
        product_id: int,
        snap_price: int,
        snap_img_url: Optional[str],
    ) -> None:
        sql = """
        INSERT INTO order_details (
            order_id,
            product_id,
            snap_price,
            snap_img_url
        )
        VALUES (%s, %s, %s, %s)
        """
        self.db.execute(
            sql,
            (order_id, product_id, snap_price, snap_img_url),
        )
