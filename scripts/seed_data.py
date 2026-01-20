import mysql.connector
import yaml

def seed_database():
    # 1. 설정 파일 로드
    with open('configs/db_config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    try:
        # 2. DB 연결
        conn = mysql.connector.connect(
            host=config['host'],
            user=config['user'],
            password=config['password'],
            database=config['database'],
            port=config.get('port', 3306)
        )
        cursor = conn.cursor()

        # 3. 초기 상품 데이터 (YOLO 모델 클래스 ID와 매칭 필수)
        # 예: 0번은 사과, 1번은 우유, 2번은 스낵
        initial_products = [
            (0, '신선한 사과', 1500, '과일'),
            (1, '매일우유 1L', 2800, '유제품'),
            (2, '포카칩 양파맛', 1700, '스낵'),
            (3, '생수 500ml', 800, '음료'),
            (4, '컵라면 매운맛', 1300, '면류')
        ]

        # 4. 데이터 삽입 (기존 데이터 무시 혹은 업데이트)
        query = """
            INSERT INTO products (product_id, product_name, price, category)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            product_name=VALUES(product_name), price=VALUES(price);
        """

        cursor.executemany(query, initial_products)
        conn.commit()

        print(f"Successfully inserted {cursor.rowcount} products into the database.")

    except mysql.connector.Error as e:
        print(f"Error seeding database: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    seed_database()