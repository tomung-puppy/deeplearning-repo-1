#!/usr/bin/env python3
"""
PC 1대 하이브리드 테스트
- AI Server, Main Hub, UI는 자동 실행
- 카메라: 전방(영상파일) + 카트(웹캠)
"""
import sys
import time
import subprocess
import signal
from pathlib import Path

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent
PYTHON_PATH = sys.executable

print("=" * 60)
print("PC 1대 하이브리드 시스템 테스트")
print("  - 전방 카메라: 웹캠 2번 (USB 카메라 - 장애물 감지)")
print("  - 카트 카메라: 웹캠 0번 (내장 카메라 - 상품 인식)")
print("=" * 60)

processes = []


def cleanup(signum=None, frame=None):
    """모든 프로세스 종료"""
    print("\n\n종료 중...")
    for name, proc in processes:
        if proc.poll() is None:  # 아직 실행 중이면
            print(f"  {name} 종료...")
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
    print("모든 프로세스 종료 완료")
    sys.exit(0)


# Ctrl+C 핸들러
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

try:
    # 1. AI Server 시작
    print("\n[1/4] AI Server 시작 중...")
    ai_log = open(PROJECT_ROOT / "test_ai_server.log", "w", buffering=1)
    ai_proc = subprocess.Popen(
        [PYTHON_PATH, "-u", "src/ai_server.py"],  # -u for unbuffered
        cwd=PROJECT_ROOT,
        stdout=ai_log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    processes.append(("AI Server", ai_proc))
    time.sleep(3)

    if ai_proc.poll() is not None:
        ai_log.close()
        with open(PROJECT_ROOT / "test_ai_server.log", "r") as f:
            print("  ✗ AI Server 시작 실패!")
            print(f.read())
        cleanup()
    print("  ✓ AI Server 실행 중 (PID: {})".format(ai_proc.pid))

    # 2. Main Hub 시작
    print("\n[2/4] Main Hub 시작 중...")
    hub_log = open(PROJECT_ROOT / "test_main_hub.log", "w", buffering=1)
    hub_proc = subprocess.Popen(
        [PYTHON_PATH, "-u", "src/main_hub.py"],  # -u for unbuffered
        cwd=PROJECT_ROOT,
        stdout=hub_log,
        stderr=subprocess.STDOUT,
        text=True,
    )
    processes.append(("Main Hub", hub_proc))
    time.sleep(3)

    if hub_proc.poll() is not None:
        hub_log.close()
        with open(PROJECT_ROOT / "test_main_hub.log", "r") as f:
            print("  ✗ Main Hub 시작 실패!")
            print(f.read())
        cleanup()
    print("  ✓ Main Hub 실행 중 (PID: {})".format(hub_proc.pid))

    # 3. 최적화된 하이브리드 카메라 앱 시작
    print("\n[3/4] 최적화된 카메라 앱 시작 중...")
    print("  (듀얼 웹캠: USB + 내장)")
    cam_proc = subprocess.Popen(
        [PYTHON_PATH, "test/optimized_hybrid_camera.py", "--front", "2", "--cart", "0"],
        cwd=PROJECT_ROOT,
        # stdout과 stderr를 파이프하지 않음 - 터미널에 직접 출력
        text=True,
    )
    processes.append(("Hybrid Camera", cam_proc))
    time.sleep(2)

    if cam_proc.poll() is not None:
        print("  ✗ 카메라 앱 시작 실패!")
        print("  웹캠을 연결하고 다시 시도하세요.")
        cleanup()
    print("  ✓ 하이브리드 카메라 실행 중 (PID: {})".format(cam_proc.pid))

    # 4. UI 앱 시작
    print("\n[4/4] UI 앱 시작 중...")
    ui_proc = subprocess.Popen(
        [PYTHON_PATH, "src/cart_ui_app.py"],
        cwd=PROJECT_ROOT,
    )
    processes.append(("UI App", ui_proc))

    print("\n" + "=" * 60)
    print("시스템 실행 중!")
    print("=" * 60)
    print("\n실행 중인 프로세스:")
    for name, proc in processes:
        if proc.poll() is None:
            print(f"  ✓ {name} (PID: {proc.pid})")
        else:
            print(f"  ✗ {name} (종료됨)")

    print("\n" + "=" * 60)
    print("테스트 방법:")
    print("  1. UI 창이 열립니다")
    print("  2. 두 개의 카메라 창이 열립니다:")
    print("     - Front Camera: 웹캠 2번 (USB 카메라 - 장애물 감지)")
    print("     - Cart Camera: 웹캠 0번 (내장 카메라 - 상품 인식 + ROI 표시)")
    print("  3. 사람이나 장애물이 감지되면 UI에 경고 표시")
    print("  4. 내장 카메라에 상품을 보여주고 아래로 이동시키면")
    print("     → 장바구니에 추가됩니다 (주황색 라인 통과)")
    print("  5. 카메라 창에서 'q' 키를 누르면 종료")
    print("=" * 60)
    print("\n종료하려면 Ctrl+C를 누르세요...")

    # UI 프로세스가 종료될 때까지 대기
    ui_proc.wait()

except KeyboardInterrupt:
    pass
finally:
    cleanup()
