"""
College Gate Monitor - ANPR (Automatic Number Plate Recognition)
Uses EasyOCR + OpenCV for real-time plate detection from camera or uploaded images.
"""

# Fix PIL.Image compatibility issue
import sys
try:
    from PIL import Image
    if not hasattr(Image, 'ANTIALIAS'):
        Image.ANTIALIAS = Image.Resampling.LANCZOS
except Exception as e:
    print(f"[WARN] PIL patch failed: {e}")

import cv2
import numpy as np
import re
import threading
import time
import base64
import io
from datetime import datetime
from difflib import SequenceMatcher  # ADD THIS

# ────────────────────────────────────────────────────────────────
#  Fuzzy Matching Function
# ────────────────────────────────────────────────────────────────
def fuzzy_match_plate(detected_plate, registered_plates, threshold=0.85):
    """
    Match detected plate against registered plates with tolerance for OCR errors.
    Returns the best match if similarity > threshold, else returns None.
    """
    detected_clean = detected_plate.replace(' ', '').upper()
    best_match = None
    best_score = 0
    
    for reg_plate in registered_plates:
        reg_clean = reg_plate.replace(' ', '').upper()
        score = SequenceMatcher(None, detected_clean, reg_clean).ratio()
        
        if score > best_score:
            best_score = score
            best_match = reg_plate if score > threshold else None
    
    return best_match, best_score

# ─────────────────────────────────────────────────────────────────────────────
#  Indian number plate patterns
# ─────────────────────────────────────────────────────────────────────────────

PLATE_PATTERNS = [
    r'^[A-Z]{2}\d{2}[A-Z]{1,3}\d{4}$',   # DL01AB1234
    r'^[A-Z]{2}\d{2}[A-Z]{1,2}\d{1,4}$',  # Short variants
    r'^[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{1,4}$',  # Flexible
]


def validate_indian_plate(raw: str):
    """Validate and format an Indian number plate string."""
    clean = re.sub(r'[\s\-\.]', '', raw.upper())
    clean = clean.replace('O', '0').replace('I', '1')   # common OCR mistakes

    for pattern in PLATE_PATTERNS:
        if re.match(pattern, clean):
            # Pretty-format: XX 00 XX 0000
            try:
                state   = clean[:2]
                district= clean[2:4]
                series  = clean[4:-4]
                number  = clean[-4:]
                return f"{state} {district} {series} {number}"
            except Exception:
                return clean  # return cleaned without formatting

    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Plate Detector
# ─────────────────────────────────────────────────────────────────────────────
class PlateDetector:
    def __init__(self):
        self._reader       = None
        self._reader_lock  = threading.Lock()
        self.camera        = None
        self.is_running    = False
        self.current_frame = None
        self._frame_lock   = threading.Lock()
        self._thread       = None
        self.callback      = None
        self._last_seen    = {}          # plate → last emitted timestamp
        self._cooldown     = 8          # seconds before same plate fires again

        # Try to load OCR in background so startup isn't slow
        threading.Thread(target=self._init_reader, daemon=True).start()

    def _init_reader(self):
        try:
            import easyocr
            with self._reader_lock:
                self._reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            print("[ANPR] EasyOCR ready.")
        except ImportError:
            print("[ANPR] EasyOCR not installed – falling back to Tesseract.")
            self._try_tesseract()
        except Exception as exc:
            print(f"[ANPR] OCR init failed: {exc}")

    def _try_tesseract(self):
        try:
            import pytesseract
            self._tesseract = pytesseract
            print("[ANPR] Tesseract ready (fallback).")
        except ImportError:
            print("[ANPR] No OCR engine available. Manual mode only.")
            self._tesseract = None

    @property
    def ocr_ready(self):
        with self._reader_lock:
            return self._reader is not None

    # ──────────────────────────────────────────────
    #  Image pre-processing helpers
    # ──────────────────────────────────────────────
    @staticmethod
    def _preprocess(image):
        """Enhance frame for better OCR results."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        _, thresh = cv2.threshold(gray, 0, 255,
                                  cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return thresh

    @staticmethod
    def _find_plate_regions(image):
        """Attempt to locate plate bounding boxes in image."""
        gray  = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur  = cv2.bilateralFilter(gray, 11, 17, 17)
        edges = cv2.Canny(blur, 30, 200)
        cnts, _ = cv2.findContours(edges.copy(),
                                   cv2.RETR_TREE,
                                   cv2.CHAIN_APPROX_SIMPLE)
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:10]

        regions = []
        for c in cnts:
            peri  = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.018 * peri, True)
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(approx)
                ar = w / h
                if 2 < ar < 7 and w > 60:      # plate aspect ratio
                    regions.append((x, y, w, h))

        return regions

    # ──────────────────────────────────────────────
    #  Core detection
    # ──────────────────────────────────────────────
    def detect_from_frame(self, frame):
        """Return list of dicts with plate, confidence, bbox."""
        results = []
        with self._reader_lock:
            reader = self._reader

        if reader is None:
            return results

        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            raw_results = reader.readtext(rgb, detail=1, paragraph=False)

            for (bbox, text, conf) in raw_results:
                plate = validate_indian_plate(text)
                if plate and conf > 0.25:
                    xs = [pt[0] for pt in bbox]
                    ys = [pt[1] for pt in bbox]
                    results.append({
                        'plate':      plate,
                        'raw_text':   text,
                        'confidence': round(conf * 100, 1),
                        'bbox':       [int(min(xs)), int(min(ys)),
                                       int(max(xs)), int(max(ys))],
                        'timestamp':  datetime.now().isoformat(),
                    })
        except Exception as exc:
            print(f"[ANPR] Detection error: {exc}")

        return results

    def detect_from_bytes(self, image_bytes: bytes):
        """Detect plates from raw image bytes (file upload)."""
        nparr = np.frombuffer(image_bytes, np.uint8)
        img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return []
        return self.detect_from_frame(img)

    def detect_from_base64(self, b64_string: str):
        """Detect plates from base64-encoded image."""
        try:
            header, data = b64_string.split(',', 1) if ',' in b64_string else ('', b64_string)
            img_bytes = base64.b64decode(data)
            return self.detect_from_bytes(img_bytes)
        except Exception as exc:
            print(f"[ANPR] Base64 decode error: {exc}")
            return []

    # ──────────────────────────────────────────────
    #  Camera streaming
    # ──────────────────────────────────────────────
    def start_camera(self, callback=None, camera_index=0):
        """Start background camera thread. Returns True on success."""
        if self.is_running:
            return True

        self.camera = cv2.VideoCapture(camera_index)
        if not self.camera.isOpened():
            self.camera = None
            return False

        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        self.is_running = True
        self.callback   = callback
        self._thread    = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        return True

    def _capture_loop(self):
        last_detect = 0
        while self.is_running:
            ret, frame = self.camera.read()
            if not ret:
                time.sleep(0.1)
                continue

            with self._frame_lock:
                self.current_frame = frame.copy()

            now = time.time()
            if now - last_detect >= 1.5:               # detect every 1.5 s
                plates = self.detect_from_frame(frame)
                for p in plates:
                    plate_key = p['plate'].replace(' ', '')
                    last_time = self._last_seen.get(plate_key, 0)
                    if now - last_time >= self._cooldown:
                        self._last_seen[plate_key] = now
                        if self.callback:
                            self.callback(p)
                last_detect = now

            time.sleep(0.033)   # ~30 fps

    def get_annotated_frame_jpeg(self):
        """Return current frame with bounding boxes drawn, as JPEG bytes."""
        with self._frame_lock:
            if self.current_frame is None:
                return None
            frame = self.current_frame.copy()

        # Draw any plates in this frame
        plates = self.detect_from_frame(frame)
        for p in plates:
            x1, y1, x2, y2 = p['bbox']
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 212, 255), 2)
            label = f"{p['plate']}  {p['confidence']}%"
            cv2.putText(frame, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 212, 255), 2)

        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return buf.tobytes()

    def get_frame_jpeg(self):
        """Return raw current frame as JPEG (fast, no detection overlay)."""
        with self._frame_lock:
            if self.current_frame is None:
                return None
            _, buf = cv2.imencode('.jpg', self.current_frame,
                                  [cv2.IMWRITE_JPEG_QUALITY, 75])
            return buf.tobytes()

    def stop_camera(self):
        self.is_running = False
        if self.camera:
            self.camera.release()
            self.camera = None

    # ──────────────────────────────────────────────
    #  Demo / simulation
    # ──────────────────────────────────────────────
    def generate_demo_frame(self, width=1280, height=720):
        """Generate a dark demo frame when no real camera is present."""
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (20, 20, 32)

        # Draw grid lines
        for x in range(0, width, 80):
            cv2.line(frame, (x, 0), (x, height), (30, 30, 50), 1)
        for y in range(0, height, 80):
            cv2.line(frame, (0, y), (width, y), (30, 30, 50), 1)

        # Center text
        ts  = datetime.now().strftime('%H:%M:%S')
        txt = f"CAMERA OFFLINE  |  {ts}"
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
        cv2.putText(frame, txt,
                    ((width - tw) // 2, height // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 212, 255), 2)
        sub = "Connect a camera or use Image Upload to detect plates"
        (sw, _), _ = cv2.getTextSize(sub, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.putText(frame, sub,
                    ((width - sw) // 2, height // 2 + 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (140, 140, 160), 1)

        _, buf = cv2.imencode('.jpg', frame)
        return buf.tobytes()
