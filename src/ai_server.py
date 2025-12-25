# ai_server.py
import threading
import time
import cv2
import numpy as np

from network.udp_handler import UDPFrameReceiver
from network.tcp_server import TCPServer
from network.tcp_client import TCPClient
from common.protocol import (
    Protocol,
    MessageType,
    AITask,
    AIEvent,
    DangerLevel,
)
from detectors.obstacle_dl import ObstacleDetector
from detectors.product_dl import ProductRecognizer
from common.constants import (
    UDP_PORT_AI_OBSTACLE,
    UDP_PORT_AI_PRODUCT,
    TCP_PORT_AI,
    TCP_PORT_MAIN_EVT,
    MAIN_PC2_IP,
)


class AIServer:
    """
    AI Server (PC1)

    - UDP: frame input (raw JPEG bytes)
    - Decode + inference in worker threads
    - PUSH: event → Main PC2 (state change only)
    - PULL: TCP → latest inference result
    """

    def __init__(self):
        # -------------------------
        # Models
        # -------------------------
        self.obstacle_model = ObstacleDetector()
        self.product_model = ProductRecognizer()

        # -------------------------
        # Latest frame buffers (bytes)
        # -------------------------
        self._latest_obstacle_bytes = None
        self._latest_product_bytes = None

        # -------------------------
        # Latest inference results
        # -------------------------
        self._latest_obstacle_result = None
        self._latest_product_result = None

        # -------------------------
        # Locks
        # -------------------------
        self._obstacle_lock = threading.Lock()
        self._product_lock = threading.Lock()

        # -------------------------
        # UDP receivers
        # -------------------------
        self.obstacle_receiver = UDPFrameReceiver(
            "0.0.0.0", UDP_PORT_AI_OBSTACLE
        )
        self.product_receiver = UDPFrameReceiver(
            "0.0.0.0", UDP_PORT_AI_PRODUCT
        )

        # -------------------------
        # TCP interfaces
        # -------------------------
        self.pull_server = TCPServer(
            "0.0.0.0",
            TCP_PORT_AI,
            self.handle_pull_request,
        )
        self.event_client = TCPClient(
            MAIN_PC2_IP,
            TCP_PORT_MAIN_EVT,
        )

    # =========================
    # UDP receive loops
    # =========================
    def _obstacle_udp_loop(self):
        for jpeg_bytes in self.obstacle_receiver.receive_packets():
            with self._obstacle_lock:
                self._latest_obstacle_bytes = jpeg_bytes

    def _product_udp_loop(self):
        for jpeg_bytes in self.product_receiver.receive_packets():
            with self._product_lock:
                self._latest_product_bytes = jpeg_bytes

    # =========================
    # Inference loops
    # =========================
    def _obstacle_inference_loop(self):
        last_level = DangerLevel.NORMAL

        while True:
            with self._obstacle_lock:
                jpeg = self._latest_obstacle_bytes

            if jpeg is None:
                time.sleep(0.01)
                continue

            frame = self._decode(jpeg)
            if frame is None:
                continue

            result = self.obstacle_model.detect(frame)
            self._latest_obstacle_result = result

            level = DangerLevel(result.get("danger_level", 0))

            if level != last_level and level >= DangerLevel.CAUTION:
                self._push_event(
                    AIEvent.OBSTACLE_DANGER,
                    {
                        "level": int(level),
                        "distance": result.get("distance"),
                    },
                )
                last_level = level

            time.sleep(0.02)

    def _product_inference_loop(self):
        last_product_id = None

        while True:
            with self._product_lock:
                jpeg = self._latest_product_bytes

            if jpeg is None:
                time.sleep(0.01)
                continue

            frame = self._decode(jpeg)
            if frame is None:
                continue

            result = self.product_model.recognize(frame)
            self._latest_product_result = result

            product_id = result.get("product_id")
            if product_id and product_id != last_product_id:
                self._push_event(
                    AIEvent.PRODUCT_DETECTED,
                    {"product_id": product_id},
                )
                last_product_id = product_id

            time.sleep(0.05)

    # =========================
    # Utilities
    # =========================
    @staticmethod
    def _decode(jpeg_bytes: bytes):
        arr = np.frombuffer(jpeg_bytes, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    # =========================
    # PUSH (AI → Main PC2)
    # =========================
    def _push_event(self, event: AIEvent, data: dict):
        msg = Protocol.ai_event(event, data)
        self.event_client.send_request(msg)

    # =========================
    # PULL (Main → AI)
    # =========================
    def handle_pull_request(self, message: dict) -> dict:
        if not Protocol.validate(message):
            return Protocol.ai_response(False, {}, "Invalid protocol")

        if MessageType(message["header"]["type"]) != MessageType.AI_REQ:
            return Protocol.ai_response(False, {}, "Invalid message type")

        task = AITask(message["payload"]["task"])

        if task == AITask.OBSTACLE:
            result = self._latest_obstacle_result
        elif task == AITask.PRODUCT:
            result = self._latest_product_result
        else:
            result = None

        if result is None:
            return Protocol.ai_response(False, {}, "No result available")

        return Protocol.ai_response(True, result)

    # =========================
    # Lifecycle
    # =========================
    def run(self):
        print("AI Server (PC1) started")

        threads = [
            threading.Thread(target=self._obstacle_udp_loop, daemon=True),
            threading.Thread(target=self._product_udp_loop, daemon=True),
            threading.Thread(target=self._obstacle_inference_loop, daemon=True),
            threading.Thread(target=self._product_inference_loop, daemon=True),
        ]

        for t in threads:
            t.start()

        self.pull_server.start()


if __name__ == "__main__":
    AIServer().run()
