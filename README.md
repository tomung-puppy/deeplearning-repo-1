# deeplearning-repo-1
딥러닝 프로젝트 1조 저장소. 배송 로봇 (Delivery robot)

---

# 🛒 Smart Shopping Cart System (AI 기반 지능형 쇼핑카트)

이 프로젝트는 **YOLO 객체 인식** 기술과 **분산 컴퓨팅 아키텍처**를 결합하여, 실시간 장애물 감지 및 상품 자동 인식 기능을 제공하는 스마트 쇼핑카트 시스템입니다.

---

## 🏗️ 시스템 아키텍처 (System Architecture)

본 시스템은 실시간 연산 부하를 분산하기 위해 3개의 독립적인 노드로 구성됩니다.

1. **PC1 (AI Inference Server):** 고성능 연산 자원을 활용하여 전송받은 영상에서 장애물(사람, 카트 등) 및 상품을 감지합니다.
2. **PC2 (Main Control Hub):** 시스템의 오케스트레이터입니다. 영상 데이터를 중계하고, AI 분석 결과를 해석하며, AWS RDS와 연동하여 상품 정보를 관리합니다.
3. **PC3 (Edge Device - Shopping Cart):** 전방/카트 카메라 영상을 송출하고, PyQt6 기반의 대시보드 UI를 통해 사용자에게 정보를 출력합니다.

---

## 📂 디렉토리 구조 (Directory Structure)

```text
smart-shopping-cart/
├── src/
│   ├── main_pc2.py           # [Main] 중앙 제어 및 데이터 중계 허브
│   ├── ai_server_pc1.py      # [AI] 분석 요청 수신 및 YOLO 추론 실행
│   ├── cart_app_pc3.py       # [Edge] 카메라 영상 인코딩 및 전송 앱
│   ├── core/
│   │   └── engine.py         # [Logic] 비즈니스 판단 및 상태 관리 엔진
│   ├── network/
│   │   ├── tcp_server.py     # 제어 명령 수신용 TCP 서버
│   │   ├── tcp_client.py     # 분석 요청용 TCP 클라이언트
│   │   └── udp_handler.py    # 실시간 영상 전송용 UDP 핸들러
│   ├── database/
│   │   ├── db_handler.py     # AWS RDS 연결 관리 (Singleton)
│   │   ├── product_dao.py    # 상품 정보 접근 객체
│   │   └── transaction_dao.py # 결제 내역 기록 객체
│   ├── ui/
│   │   └── dashboard.py      # PyQt6 사용자 대시보드 UI
│   ├── detectors/
│   │   ├── obstacle_dl.py    # 장애물 탐지 래퍼 클래스
│   │   └── product_dl.py     # 상품 인식 래퍼 클래스
│   ├── common/
│   │   ├── constants.py      # 시스템 전역 상수 (IP, Port, Threshold)
│   │   └── protocols.py      # 통신 메시지 규격 정의
│   └── utils/
│       ├── logger.py         # 이벤트 및 에러 로깅 유틸리티
│       └── image_proc.py     # 영상 압축(JPEG)/디코딩 유틸리티
├── configs/                  # YAML 기반 환경 설정 파일
├── scripts/                  # DB 스키마 및 초기 데이터 스크립트
├── models/                   # 학습된 YOLO (.pt) 가중치 파일
└── logs/                     # 시스템 구동 로그 저장소

```

---

## 🚀 주요 기능 (Key Features)

### 1. 실시간 장애물 탐지 및 알람

* **UDP Streaming:** 전방 카메라 영상을 JPEG로 압축하여 지연 시간을 최소화()하여 전송합니다.
* **Danger Level Analysis:** 객체의 크기와 거리를 계산하여 위험도에 따른 시각적 알람(CAUTION / DANGER)을 UI에 표시합니다.

### 2. 상품 자동 스캔 및 장바구니 관리

* **Automatic Recognition:** 카트에 담기는 상품을 AI가 식별합니다.
* **DB Integration:** AWS RDS에서 실시간 가격 및 상품 정보를 조회하여 장바구니 리스트를 동적으로 업데이트합니다.
* **Duplicate Prevention:** 엔진 레이어에서 동일 상품의 중복 인식 방지 로직이 적용되어 있습니다.

---

## 🛠️ 설치 및 실행 방법 (Installation & Usage)

### 1. 환경 설정

모든 PC에서 필요한 라이브러리를 설치합니다.

```bash
pip install -r requirements.txt

```

### 2. 인프라 준비

`scripts/init_db.sql`을 실행하여 DB 테이블을 생성하고, `seed_data.py`로 상품 마스터 데이터를 입력합니다.

### 3. 시스템 가동 (권장 순서)

1. **AI Server (PC1):** `python src/ai_server_pc1.py`
2. **User UI (PC3):** `python src/ui/dashboard.py`
3. **Main Hub (PC2):** `python src/main_pc2.py`
4. **Cart App (PC3):** `python src/cart_app_pc3.py`

---

## 📡 데이터 통신 규격 (Communication Protocol)

모든 데이터는 `src/common/protocols.py`에 정의된 JSON 규격을 따릅니다.

* **AI_REQ:** 영상 바이트 데이터와 태스크 타입 송신
* **AI_RES:** 클래스 ID, 신뢰도, 바운딩 박스 좌표 수신
* **UI_CMD:** 알람 메시지 또는 상품 상세 정보 전달
