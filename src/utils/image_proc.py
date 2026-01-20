import cv2
import numpy as np

class ImageProcessor:
    @staticmethod
    def encode_frame(frame, quality=80):
        """
        OpenCV 프레임을 JPEG 바이트로 압축
        :param frame: numpy array 형태의 이미지
        :param quality: JPEG 압축 품질 (1-100, 높을수록 고화질)
        :return: 인코딩된 바이트 데이터
        """
        try:
            # JPEG 형식으로 압축 (용량 최적화)
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            result, buffer = cv2.imencode('.jpg', frame, encode_param)
            
            if not result:
                return None
            
            return buffer.tobytes()
        except Exception as e:
            print(f"Encoding Error: {e}")
            return None

    @staticmethod
    def decode_frame(byte_data):
        """
        수신된 바이트 데이터를 다시 OpenCV 프레임으로 복구
        :param byte_data: 수신된 JPEG 바이트 데이터
        :return: numpy array 형태의 이미지
        """
        try:
            # 바이트 배열을 uint8 넘파이 배열로 변환
            nparr = np.frombuffer(byte_data, np.uint8)
            # 이미지 디코딩
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return frame
        except Exception as e:
            print(f"Decoding Error: {e}")
            return None

    @staticmethod
    def resize_for_ai(frame, target_size=(640, 640)):
        """
        AI 분석(YOLO)을 위해 이미지 크기를 조정
        """
        return cv2.resize(frame, target_size)

    @staticmethod
    def draw_labels(frame, detections):
        """
        이미지 위에 감지된 객체의 바운딩 박스와 라벨을 그림 (디버깅용)
        detections: [{'box': [x1, y1, x2, y2], 'label': 'Apple'}, ...]
        """
        for det in detections:
            x1, y1, x2, y2 = det['box']
            label = det.get('label', 'Object')
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, label, (x1, y1 - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        return frame