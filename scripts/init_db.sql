-- 데이터베이스 생성 및 선택
CREATE DATABASE IF NOT EXISTS smart_cart_db;
USE smart_cart_db;

-- 1. 상품 마스터 테이블 (AI 모델의 Class ID와 연동)
CREATE TABLE IF NOT EXISTS products (
    product_id INT PRIMARY KEY,         -- YOLO 모델의 클래스 인덱스 번호
    product_name VARCHAR(100) NOT NULL,
    price INT NOT NULL,
    category VARCHAR(50),
    stock_quantity INT DEFAULT 100,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 장바구니 세션 테이블 (현재 쇼핑 중인 정보)
CREATE TABLE IF NOT EXISTS cart_sessions (
    session_id INT AUTO_INCREMENT PRIMARY KEY,
    cart_id VARCHAR(50) NOT NULL,       -- 카트 고유 번호
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- 3. 장바구니 상세 내역 (어떤 카트에 어떤 상품이 담겼는지)
CREATE TABLE IF NOT EXISTS cart_items (
    item_id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT,
    product_id INT,
    quantity INT DEFAULT 1,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES cart_sessions(session_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 4. 결제 및 트랜잭션 로그
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT,
    total_price INT NOT NULL,
    payment_method VARCHAR(20),
    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES cart_sessions(session_id)
);