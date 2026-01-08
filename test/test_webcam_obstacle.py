#!/usr/bin/env python3
"""
실시간 웹캠 장애물 감지 테스트
통합된 obstacle_v2 알고리즘 실시간 검증
"""
import sys
import cv2
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from detectors.obstacle_dl import ObstacleDetector


def draw_detection_info(frame, result):
    """프레임에 감지 정보 표시"""
    h, w = frame.shape[:2]

    # 배경 오버레이
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 120), (0, 0, 0), -1)
    frame = cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)

    # 위험 레벨 표시
    level = result.get("level", 0)
    risk_names = ["SAFE", "CAUTION", "WARN"]
    risk_colors = [(0, 255, 0), (0, 255, 255), (0, 0, 255)]  # Green, Yellow, Red

    risk_name = risk_names[level]
    risk_color = risk_colors[level]

    cv2.putText(
        frame,
        f"Risk: {risk_name}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        risk_color,
        2,
    )

    # 객체 정보
    obj_count = len(result.get("objects", []))
    cv2.putText(
        frame,
        f"Objects: {obj_count}",
        (10, 65),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )

    # 최고 위험 객체 정보
    highest_risk = result.get("highest_risk_object")
    if highest_risk:
        track_id = highest_risk.get("track_id", -1)
        pttc = highest_risk.get("pttc_s", 1e9)
        pttc_str = f"{pttc:.1f}s" if pttc < 1e6 else "∞"

        cv2.putText(
            frame,
            f"Track: {track_id} | pTTC: {pttc_str}",
            (10, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )

        # 객체 박스 그리기
        for obj in result.get("objects", []):
            if obj.get("track_id") == track_id:
                box = obj.get("box", [0, 0, 0, 0])
                x1, y1, x2, y2 = box

                # 위험도에 따른 색상
                box_color = risk_colors[obj.get("risk_level", 0)]

                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

                # 라벨
                label = f"{obj.get('class_name', 'unknown')} #{track_id}"
                cv2.putText(
                    frame,
                    label,
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    box_color,
                    2,
                )

    # 모든 객체 박스 그리기
    for obj in result.get("objects", []):
        box = obj.get("box", [0, 0, 0, 0])
        x1, y1, x2, y2 = box
        track_id = obj.get("track_id", -1)
        risk_level = obj.get("risk_level", 0)

        # 위험도에 따른 색상
        box_color = risk_colors[risk_level]

        # 박스
        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

        # 라벨
        label = f"{obj.get('class_name', 'unknown')} #{track_id}"
        in_center = "C" if obj.get("in_center") else ""
        approaching = "→" if obj.get("approaching") else ""
        label += f" {in_center}{approaching}"

        cv2.putText(
            frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 2
        )

    return frame


def main():
    print("=" * 70)
    print("실시간 웹캠 장애물 감지 테스트")
    print("=" * 70)

    # 카메라 선택
    camera_id = 0
    if len(sys.argv) > 1:
        camera_id = int(sys.argv[1])

    print(f"\n[1] 카메라 {camera_id} 초기화 중...")
    cap = cv2.VideoCapture(camera_id)

    if not cap.isOpened():
        print(f"❌ 카메라 {camera_id}를 열 수 없습니다.")
        print("사용법: python test_webcam_obstacle.py [camera_id]")
        return

    print("✅ 카메라 초기화 완료")

    # Detector 초기화
    print("\n[2] ObstacleDetector 초기화 중...")
    detector = ObstacleDetector()
    print("✅ Detector 초기화 완료")

    print("\n[3] 실시간 감지 시작...")
    print("=" * 70)
    print("조작법:")
    print("  - 'q': 종료")
    print("  - 's': 스크린샷 저장")
    print("  - 카메라 앞에서 움직여보세요!")
    print("=" * 70)

    frame_count = 0
    fps = 0
    start_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("프레임을 읽을 수 없습니다.")
                break

            # 감지 실행
            result = detector.detect(frame)

            # 정보 표시
            frame = draw_detection_info(frame, result)

            # FPS 계산
            frame_count += 1
            if frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed

            # FPS 표시
            cv2.putText(
                frame,
                f"FPS: {fps:.1f}",
                (frame.shape[1] - 120, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )

            # 화면 표시
            cv2.imshow("Obstacle Detection Test (Press 'q' to quit)", frame)

            # 키 입력 처리
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("s"):
                filename = f"screenshot_{int(time.time())}.jpg"
                cv2.imwrite(filename, frame)
                print(f"스크린샷 저장: {filename}")

    except KeyboardInterrupt:
        print("\n사용자 중단...")

    finally:
        cap.release()
        cv2.destroyAllWindows()

        print("\n" + "=" * 70)
        print(f"테스트 완료!")
        print(f"  - 처리 프레임: {frame_count}")
        print(f"  - 평균 FPS: {fps:.1f}")
        print("=" * 70)


if __name__ == "__main__":
    main()
