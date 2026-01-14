from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Tuple


def unique_track_id_for_untracked(frame_index: int, det_index: int, base: int = -1_000_000) -> int:
    """track_id=-1 같은 untracked가 한 버킷에 섞여 상태가 튀는 걸 방지."""
    return base - frame_index * 1000 - det_index


def is_border_box(x1: float, y1: float, x2: float, y2: float, W: int, H: int, margin_ratio: float = 0.01) -> bool:
    mx = margin_ratio * W
    my = margin_ratio * H
    return (x1 <= mx) or (x2 >= (W - mx)) or (y1 <= my) or (y2 >= (H - my))


def get_xyxy(det: Any) -> Tuple[float, float, float, float]:
    xyxy = getattr(det, "xyxy", None)
    if xyxy is None:
        return (0.0, 0.0, 0.0, 0.0)
    x1, y1, x2, y2 = xyxy
    return float(x1), float(y1), float(x2), float(y2)


def get_cls_name(det: Any) -> str:
    return str(getattr(det, "cls_name", ""))


def get_track_id(det: Any) -> int:
    return int(getattr(det, "track_id", -1))


def get_conf(det: Any) -> float:
    return float(getattr(det, "conf", 0.0))


def clone_with_track_id(det: Any, new_tid: int) -> Any:
    """dev Detection이 dataclass면 replace가 되고, 아니면 생성자 기반으로 새로 만든다."""
    try:
        return replace(det, track_id=int(new_tid))
    except Exception:
        C = det.__class__
        return C(
            int(new_tid),
            int(getattr(det, "cls_id", -1)),
            str(getattr(det, "cls_name", "")),
            float(getattr(det, "conf", 0.0)),
            tuple(getattr(det, "xyxy", (0, 0, 0, 0))),
        )


def geom_from_xyxy(x1: float, y1: float, x2: float, y2: float, W: int, H: int) -> Dict[str, float]:
    """bbox 기하(폭/높이/면적/비율/중심) 계산."""
    w = max(1.0, x2 - x1)
    h = max(1.0, y2 - y1)
    cx = 0.5 * (x1 + x2)

    bw = w / max(1.0, W)                 # box_w / W
    hh = h / max(1.0, H)                 # box_h / H
    ar = (w * h) / max(1.0, (W * H))     # area / (W*H)
    wh = w / max(1e-6, h)                # w/h
    cxn = cx / max(1.0, W)               # center_x normalized
    close = min(bw, hh)                  # "둘 다 커야 가까움" (AND 성질)

    return {"bw": bw, "hh": hh, "ar": ar, "wh": wh, "cxn": cxn, "close": close}


@dataclass
class MotionState:
    ar_ema: float = 0.0
    prev_ar_ema: float = 0.0
    cx_ema: float = 0.0
    prev_cx_ema: float = 0.0
    initialized: bool = False


class MotionEstimator:
    """
    해결안 2) approaching 재정의:
      - area_rate(면적 증가율): 전방 접근이면 bbox 면적비(ar)이 증가
      - cx_speed(중심 좌우 이동 속도): 옆 이동이면 cx가 빠르게 이동
    """
    def __init__(self, alpha: float = 0.40):
        self.alpha = float(alpha)
        self.states: Dict[int, MotionState] = {}

    def update(self, track_id: int, ar: float, cxn: float, fps: float) -> Tuple[float, float, float]:
        st = self.states.get(track_id)
        if st is None:
            st = MotionState()
            self.states[track_id] = st

        if not st.initialized:
            st.ar_ema = float(ar)
            st.prev_ar_ema = float(ar)
            st.cx_ema = float(cxn)
            st.prev_cx_ema = float(cxn)
            st.initialized = True
            return st.ar_ema, 0.0, 0.0

        a = self.alpha
        st.prev_ar_ema = st.ar_ema
        st.prev_cx_ema = st.cx_ema

        st.ar_ema = a * float(ar) + (1 - a) * st.ar_ema
        st.cx_ema = a * float(cxn) + (1 - a) * st.cx_ema

        fps = max(1e-6, float(fps))
        ar_rate = (st.ar_ema - st.prev_ar_ema) * fps                 # +면 가까워짐(면적 증가)
        cx_speed = abs(st.cx_ema - st.prev_cx_ema) * fps            # +면 좌우 이동 큼(옆 통과)

        return st.ar_ema, float(ar_rate), float(cx_speed)


class StreakGate:
    """N프레임 연속 만족 시에만 True."""
    def __init__(self, need_frames: int = 3):
        self.need_frames = int(need_frames)
        self._streak: Dict[int, int] = {}

    def step(self, track_id: int, ok: bool) -> bool:
        cur = self._streak.get(track_id, 0)
        if ok:
            cur += 1
        else:
            cur = max(0, cur - 1)
        self._streak[track_id] = cur
        return cur >= self.need_frames


def box_quality_ok(
    cls_name: str,
    conf: float,
    bw: float,
    hh: float,
    wh: float,
    border: bool,
    close: float,
    min_conf_person: float,
    min_conf_cart: float,
    person_wh_max: float,
    cart_wh_min: float,
    cart_wh_max: float,
    border_close_min: float,
) -> bool:
    """
    해결안 3) 박스 품질 필터:
      - conf 너무 낮으면 제거
      - border에서 멀리(=close 낮음)면 제거 (잘린 박스 노이즈)
      - 비율 이상한 박스 제거 (의자/배경이 Person으로 잡히는 케이스 완화)
    """
    if cls_name == "Person":
        if conf < min_conf_person:
            return False
        if wh > person_wh_max:   # 너무 납작/가로로 긴 "Person" 제거
            return False
        if border and close < border_close_min:
            return False
        return True

    if cls_name == "Cart":
        if conf < min_conf_cart:
            return False
        if wh < cart_wh_min or wh > cart_wh_max:
            return False
        if border and close < border_close_min:
            return False
        return True

    # 다른 클래스는 필터 약하게
    if border and close < border_close_min:
        return False
    return True


def pttc_area(ar_ema: float, ar_rate: float, target_ar: float) -> float:
    """
    'pTTC 같은 개념'을 area로 정의:
      - 목표 면적비(target_ar)에 도달하기까지 남은 시간
      - ar_rate>0 일 때만 유효
    """
    if ar_rate <= 1e-6:
        return 1e9
    remain = max(0.0, float(target_ar) - float(ar_ema))
    return remain / max(1e-6, float(ar_rate))
