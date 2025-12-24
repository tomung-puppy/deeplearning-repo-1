import mysql.connector

class ProductDAO:
    def __init__(self, db_handler):
        self.db_handler = db_handler

    def get_product_by_id(self, product_id):
        """상품 ID로 이름과 가격 조회"""
        query = "SELECT product_name, price FROM products WHERE product_id = %s"
        conn = self.db_handler.get_connection()
        cursor = conn.cursor(dictionary=True) # 결과를 딕셔너리 형태로 반환

        try:
            cursor.execute(query, (product_id,))
            result = cursor.fetchone()
            return result # {'product_name': 'Apple', 'price': 1500}
        except mysql.connector.Error as e:
            print(f"Query Error: {e}")
            return None
        finally:
            cursor.close()
            conn.close() # 커넥션을 풀로 반납

    def check_inventory(self, product_id):
        """재고 확인 (선택 기능)"""
        query = "SELECT stock_quantity FROM products WHERE product_id = %s"
        # ... 구현 로직 동일