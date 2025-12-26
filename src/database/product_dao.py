# database/product_dao.py
from typing import Optional, Dict, List


class ProductDAO:
    """
    Product Master Data Access Object
    """

    def __init__(self, db_handler):
        self.db = db_handler

    # =========================
    # Product Queries
    # =========================
    def get_product_by_id(self, product_id: int) -> Optional[Dict]:
        sql = """
        SELECT
            p.product_id,
            p.name,
            p.price,
            p.stock_quantity,
            p.image_url,
            c.category_id,
            c.name AS category_name
        FROM products p
        JOIN categories c ON p.category_id = c.category_id
        WHERE p.product_id = %s
        """
        return self.db.fetch_one(sql, (product_id,))

    def list_products_by_category(self, category_id: int) -> List[Dict]:
        sql = """
        SELECT product_id, name, price, stock_quantity
        FROM products
        WHERE category_id = %s
        ORDER BY name
        """
        return self.db.fetch_all(sql, (category_id,))

    # =========================
    # Stock Management
    # =========================
    def decrease_stock(self, product_id: int, quantity: int) -> bool:
        """
        Decrease stock when purchase confirmed
        """
        sql = """
        UPDATE products
        SET stock_quantity = stock_quantity - %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE product_id = %s
          AND stock_quantity >= %s
        """
        affected = self.db.execute(sql, (quantity, product_id, quantity))
        return affected == 1
