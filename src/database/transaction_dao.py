from datetime import datetime

class TransactionDAO:
    def __init__(self, db_handler):
        self.db_handler = db_handler

    def insert_transaction(self, user_id, items, total_price):
        """최종 결제 내역 저장"""
        query = "INSERT INTO transactions (user_id, items, total_price, created_at) VALUES (%s, %s, %s, %s)"
        conn = self.db_handler.get_connection()
        cursor = conn.cursor()

        try:
            # items는 리스트 형태이므로 JSON 문자열 등으로 변환하여 저장 권장
            cursor.execute(query, (user_id, str(items), total_price, datetime.now()))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            print(f"Transaction Error: {e}")
            return None
        finally:
            cursor.close()
            conn.close()