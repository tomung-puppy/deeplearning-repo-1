from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Union

import cv2
import yaml

from patch_rules import (
    MotionEstimator,
    StreakGate,
    box_quality_ok,
    clone_with_track_id,
    geom_from_xyxy,
    get_cls_name,
    get_conf,
    get_track_id,
    get_xyxy,
    is_border_box,
    pttc_area,
    unique_track_id_for_untracked,
)

# repo root를 sys.path에 넣어 dev 모듈 import 안정화
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _parse_source(src: str) -> Union[int, str]:
    return int(src) if src.isdigit() else src


RISK_SAFE = 0
RISK_CAUTION = 1
RISK_WARN = 2
RISK_NAME = {0: "SAFE", 1: "CAUTION", 2: "WARN"}


def _color_for(level: int) -> tuple[int, int, int]:
    if level >= 2:
        return (0, 0, 255)
    if level == 1:
        return (0, 255, 255)
    return (0, 255, 0)


def in_center(cx: float, W: int, center_band_ratio: float) -> bool:
    left = (1.0 - center_band_ratio) * 0.5 * W
    right = W - left
    return left <= cx <= right


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=str, default="configs/model_config.yaml")
    ap.add_argument("--source", type=str, default="0")
    ap.add_argument("--show", action="store_true")

    # 공통
    ap.add_argument("--border_margin", type=float, default=0.01)
    ap.add_argument("--motion_alpha", type=float, default=0.40)

    # 해결안 2) approaching 재정의 파라미터(로직)
    ap.add_argument("--min_area_rate", type=float, default=0.020)    # ar_rate 최소(전방 접근)
    ap.add_argument("--max_cx_speed", type=float, default=0.45)      # cx_speed 최대(옆 통과 제거)
    ap.add_argument("--min_ar_for_motion", type=float, default=0.020)

    # 해결안 3) 박스 품질 필터
    ap.add_argument("--min_conf_person", type=float, default=0.25)
    ap.add_argument("--min_conf_cart", type=float, default=0.25)
    ap.add_argument("--person_wh_max", type=float, default=1.60)     # Person이 너무 가로로 길면 제거(의자/배경)
    ap.add_argument("--cart_wh_min", type=float, default=0.40)
    ap.add_argument("--cart_wh_max", type=float, default=4.50)
    ap.add_argument("--border_close_min", type=float, default=0.18)  # border인데 close 낮으면 제거

    # ✅ A안: 정지라도 너무 가까우면 WARN (사람 기본 ON)
    ap.add_argument("--allow_static_person_warn", action="store_true")
    ap.add_argument("--allow_static_cart_warn", action="store_true")  # 카트는 기본 OFF로 쓰는 걸 추천

    # 가까움(close = min(bw,hh)) 기준
    ap.add_argument("--person_caution_close", type=float, default=0.22)
    ap.add_argument("--person_static_warn_close", type=float, default=0.48)

    ap.add_argument("--cart_caution_close", type=float, default=0.26)
    ap.add_argument("--cart_static_warn_close", type=float, default=0.60)
    ap.add_argument("--cart_caution_require_center", action="store_true")  # 카트 CAUTION을 중앙에서만 주고 싶을 때

    # WARN 판정(approach + center + pTTC-like)
    ap.add_argument("--person_warn_frames", type=int, default=3)
    ap.add_argument("--cart_warn_frames", type=int, default=3)

    ap.add_argument("--person_warn_ar_target", type=float, default=0.30)  # 이 면적비에 "곧 도달"이면 위험
    ap.add_argument("--cart_warn_ar_target", type=float, default=0.35)

    ap.add_argument("--person_warn_ttc_s", type=float, default=2.0)
    ap.add_argument("--person_warn_close_min", type=float, default=0.30)  # WARN 최소 close(멀리 WARN 방지)
    ap.add_argument("--cart_warn_ttc_s", type=float, default=2.0)
    ap.add_argument("--cart_warn_close_min", type=float, default=0.34)    # WARN 최소 close(멀리 WARN 방지)

    args = ap.parse_args()

    cfg: Dict[str, Any] = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))

    # dev tracker만 사용(엔진 파일은 변경 없음)
    from src.detectors.obstacle_tracker import YoloTrackerDetector

    detector = YoloTrackerDetector(
        weights=cfg["models"]["weights"],
        **cfg.get("tracking", {}),
        **cfg.get("inference", {}),
    )

    # center band는 config risk 값을 그대로 사용(없으면 0.45)
    center_band_ratio = float(cfg.get("risk", {}).get("center_band_ratio", 0.45))

    motion = MotionEstimator(alpha=float(args.motion_alpha))
    person_warn_gate = StreakGate(need_frames=int(args.person_warn_frames))
    cart_warn_gate = StreakGate(need_frames=int(args.cart_warn_frames))

    src = _parse_source(args.source)

    # 사람은 A안이 기본이므로 allow_static_person_warn 기본 True처럼 쓰고 싶으면
    # 실행 시 --allow_static_person_warn을 넣어 사용
    ALLOW_STATIC_PERSON = bool(args.allow_static_person_warn)
    ALLOW_STATIC_CART = bool(args.allow_static_cart_warn)

    try:
        for frame_index, fd in enumerate(detector.stream(src)):
            frame = fd.frame_bgr.copy()
            H, W = frame.shape[:2]
            fps = float(fd.fps)

            dets_fixed: List[Any] = []
            for i, det in enumerate(fd.detections):
                tid = get_track_id(det)
                if tid < 0:
                    tid = unique_track_id_for_untracked(fd.frame_index, i)
                    det = clone_with_track_id(det, tid)
                dets_fixed.append(det)

            patched_levels: Dict[int, int] = {}

            best_idx = None
            best_lvl = -1

            for i, det in enumerate(dets_fixed):
                cls_name = get_cls_name(det)
                conf = get_conf(det)

                x1, y1, x2, y2 = get_xyxy(det)
                border = is_border_box(x1, y1, x2, y2, W, H, float(args.border_margin))

                g = geom_from_xyxy(x1, y1, x2, y2, W, H)
                bw, hh, ar, wh, cxn, close = g["bw"], g["hh"], g["ar"], g["wh"], g["cxn"], g["close"]
                cx = cxn * W
                inc = in_center(cx, W, center_band_ratio)

                # 박스 품질 필터
                ok_box = box_quality_ok(
                    cls_name=cls_name,
                    conf=conf,
                    bw=bw, hh=hh, wh=wh,
                    border=border, close=close,
                    min_conf_person=float(args.min_conf_person),
                    min_conf_cart=float(args.min_conf_cart),
                    person_wh_max=float(args.person_wh_max),
                    cart_wh_min=float(args.cart_wh_min),
                    cart_wh_max=float(args.cart_wh_max),
                    border_close_min=float(args.border_close_min),
                )
                if not ok_box:
                    lvl = RISK_SAFE
                    patched_levels[i] = lvl
                    continue

                tid = get_track_id(det)

                # 해결안 2) motion 기반 approaching 재정의
                ar_ema, ar_rate, cx_speed = motion.update(tid, ar, cxn, fps)

                approach_est = (
                    (ar_ema >= float(args.min_ar_for_motion)) and
                    (ar_rate >= float(args.min_area_rate)) and
                    (cx_speed <= float(args.max_cx_speed))
                )

                # pTTC-like (area 기반)
                if cls_name == "Person":
                    warn_pttc = pttc_area(ar_ema, ar_rate, float(args.person_warn_ar_target))
                    warn_candidate = approach_est and inc and (close >= float(args.person_warn_close_min)) and (warn_pttc <= float(args.person_warn_ttc_s))
                    warn_ok = person_warn_gate.step(tid, warn_candidate)

                    # 최종 판정(엔진 risk_level 무시)
                    lvl = RISK_SAFE

                    # ✅ 접근+정면+임박이면 WARN
                    if warn_ok:
                        lvl = RISK_WARN
                    else:
                        # 가까우면 CAUTION
                        if close >= float(args.person_caution_close):
                            lvl = RISK_CAUTION

                        # ✅ A안: 정지라도 너무 가까우면 WARN (border면 더 엄격)
                        if ALLOW_STATIC_PERSON and (close >= float(args.person_static_warn_close)):
                            super_close = close >= float(args.person_static_warn_close) * 1.10
                            if (not border) or super_close:
                                lvl = RISK_WARN

                elif cls_name == "Cart":
                    warn_pttc = pttc_area(ar_ema, ar_rate, float(args.cart_warn_ar_target))
                    warn_candidate = approach_est and inc and (close >= float(args.cart_warn_close_min)) and (warn_pttc <= float(args.cart_warn_ttc_s))
                    warn_ok = cart_warn_gate.step(tid, warn_candidate)

                    lvl = RISK_SAFE

                    # ✅ 해결안 1) 카트 WARN은 접근일 때만
                    if warn_ok:
                        lvl = RISK_WARN
                    else:
                        allow_caution = True
                        if args.cart_caution_require_center:
                            allow_caution = bool(inc)

                        if allow_caution and (close >= float(args.cart_caution_close)):
                            lvl = RISK_CAUTION

                        # (옵션) 카트도 정지 초근접 WARN이 필요하면 켜기
                        if ALLOW_STATIC_CART and (close >= float(args.cart_static_warn_close)):
                            super_close = close >= float(args.cart_static_warn_close) * 1.10
                            if (not border) or super_close:
                                lvl = RISK_WARN
                else:
                    # 다른 클래스는 SAFE 처리(필요 시 확장)
                    lvl = RISK_SAFE

                patched_levels[i] = int(lvl)

                if lvl > best_lvl:
                    best_lvl = lvl
                    best_idx = i

                # draw per object
                x1i, y1i, x2i, y2i = map(int, (x1, y1, x2, y2))
                color = _color_for(lvl)
                thick = 4 if best_idx == i else 2
                cv2.rectangle(frame, (x1i, y1i), (x2i, y2i), color, thick)

                # label (디버그 포함)
                app = int(approach_est)
                label = (
                    f"{cls_name} id={tid} {RISK_NAME[lvl]} "
                    f"close={close:.2f} ar={ar:.2f} arE={ar_ema:.2f} arR={ar_rate:.3f} "
                    f"cxS={cx_speed:.3f} inc={int(inc)} app={app} conf={conf:.2f} border={int(border)}"
                )
                cv2.putText(frame, label, (x1i, max(20, y1i - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.52, color, 2, cv2.LINE_AA)

            # HUD
            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)

            if args.show:
                cv2.imshow("Obstacle (patch v3: motion+quality+policy)", frame)
                if (cv2.waitKey(1) & 0xFF) == ord("q"):
                    break

    finally:
        if args.show:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
