import re
import time
import cv2
import numpy as np
import argparse
import os
from collections import defaultdict, Counter
from ultralytics import YOLO
import easyocr
import website_api

# Custom VideoCapture class to set resolution to 1080x1920
class CustomVideoCapture(cv2.VideoCapture):
    def __init__(self, src, apiPreference=cv2.CAP_ANY):
        super().__init__(src, apiPreference)
        self.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)


# Monkey-patch cv2.VideoCapture with our custom class
cv2.VideoCapture = CustomVideoCapture



class BibDetector:
    def __init__(self, model_path, device):
        self.model = YOLO(model_path)
        self.reader = easyocr.Reader(['en'], gpu=(device != "cpu"))
        self.device = device

    def detect(self, source, verbose=False):
        return self.model.track(source=source, device=self.device, stream=True, verbose=verbose,
                                tracker="bytetrack.yaml")

    def extract_bib_text(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        results = self.reader.readtext(thresh, detail=1)

        best_text, largest_height, final_conf = "", 0, 0
        for detection in results:
            bbox, text, conf = detection
            pts = np.array(bbox, dtype=np.int32)
            _, _, _, h = cv2.boundingRect(pts)
            if h > largest_height:
                best_text, largest_height, final_conf = text.strip(), h, conf
        return best_text, final_conf


class BibTracker:
    OCR_CONFIDENCE_THRESHOLD = 0.7
    MIN_BIB_WIDTH = 60
    MIN_BIB_HEIGHT = 60
    OCR_TIMESTAMP_THRESHOLD = 1
    MIN_OCR_ENTRIES = 5

    def __init__(self, api, bib_inset_location="top-left", config_path="bib_detector_config.ini"):
        self.ocr_history = defaultdict(list)
        self.api = api
        self.best_frames = {}
        self.bib_inset_location = bib_inset_location

        if os.path.isfile(config_path):
            print(f"[INFO] Loading config from {config_path}")
            self.load_config(config_path)
        else:
            print(f"[INFO] No config file found. Using default settings.")

    def load_config(self, path):
        try:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip()

                            # Try to cast value to float or int intelligently
                            if hasattr(self, key) or hasattr(BibTracker, key):
                                try:
                                    if "." in value:
                                        value = float(value)
                                    else:
                                        value = int(value)
                                    setattr(BibTracker, key, value)
                                    print(f"[CONFIG] {key} set to {value}")
                                except ValueError:
                                    print(f"[WARN] Could not parse value for {key}, skipping.")
        except Exception as e:
            print(f"[ERROR] Failed to load config: {e}")

    def update(self, track_id, bib_box, detector, frame):
        if bib_box.size == 0:
            return
        text, conf = detector.extract_bib_text(bib_box)
        if text and conf > self.OCR_CONFIDENCE_THRESHOLD:
            numbers = "".join(re.findall(r"\d+", text))
            if numbers:
                try:
                    self.ocr_history[track_id].append((int(numbers), time.time()))
                    if track_id not in self.best_frames or conf > self.best_frames[track_id][0]:
                        new_frame = self.add_bib_inset(frame, bib_box)
                        self.best_frames[track_id] = (conf, new_frame)
                except ValueError:
                    pass

    def add_bib_inset(self, frame, bib_box, margin=10, border_color=(0, 255, 255), border_thickness=2,
                      inset_fraction=0.2):
        """
        Add a resized inset of the bib_box to a corner of the frame.

        Args:
            frame: The full video frame.
            bib_box: Cropped bib box.
            margin: Margin from frame edges.
            border_color: Color of the border rectangle.
            border_thickness: Thickness of the border line.
            inset_fraction: Fraction of frame width used for inset width (e.g., 0.2 = 20% of width).
        """
        frame_h, frame_w, _ = frame.shape
        bib_h, bib_w, _ = bib_box.shape

        # Target size
        target_w = int(frame_w * inset_fraction)
        aspect_ratio = bib_h / bib_w
        target_h = int(target_w * aspect_ratio)

        # Check bounds
        if target_h + 2 * margin > frame_h or target_w + 2 * margin > frame_w:
            return frame

        # Resize bib
        resized_bib = cv2.resize(bib_box, (target_w, target_h))
        frame_copy = frame.copy()

        # Determine top-left corner based on position
        if self.bib_inset_location == "top-left":
            x1 = margin
            y1 = margin
        elif self.bib_inset_location == "top-right":
            x1 = frame_w - target_w - margin
            y1 = margin
        elif self.bib_inset_location == "bottom-left":
            x1 = margin
            y1 = frame_h - target_h - margin
        elif self.bib_inset_location == "bottom-right":
            x1 = frame_w - target_w - margin
            y1 = frame_h - target_h - margin
        else:
            # Fallback to top-right
            x1 = frame_w - target_w - margin
            y1 = margin

        x2 = x1 + target_w
        y2 = y1 + target_h

        # Paste and border
        frame_copy[y1:y2, x1:x2] = resized_bib
        cv2.rectangle(frame_copy, (x1, y1), (x2, y2), border_color, border_thickness)

        return frame_copy

    def get_summary(self, track_id):
        entries = self.ocr_history[track_id]
        return Counter([e[0] for e in entries]).most_common(1)[0][0] if entries else "Unknown"

    def draw_info(self, panel, tracked_bibs, frame_width):
        y_offset = 20
        for track_id, (x1, y1, x2, y2) in tracked_bibs.items():
            cv2.line(panel, (x2, (y1 + y2) // 2), (frame_width + 10, y_offset + 5), (255, 0, 0), 1)
            ocr_texts = [entry[0] for entry in self.ocr_history[track_id]]
            mode_text = Counter(ocr_texts).most_common(1)[0][0] if ocr_texts else "Unknown"
            cv2.putText(panel, f"Tracker ID: {track_id}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            y_offset += 20
            cv2.putText(panel, f"Bib Number: {mode_text}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0),
                        1)
            y_offset += 20
            cv2.putText(panel, "OCR Instances:", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            y_offset += 20
            for instance in self.ocr_history[track_id][-5:]:
                cv2.putText(panel, f"- {instance}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                y_offset += 20
            y_offset += 10

    def expire_old_entries(self):
        current_time = time.time()
        expired = []
        for track_id, entries in self.ocr_history.items():
            if entries and (current_time - max(ts for _, ts in entries)) > self.OCR_TIMESTAMP_THRESHOLD:
                count = len(entries)
                if count >= self.MIN_OCR_ENTRIES:
                    mode_val = Counter([text for text, _ in entries]).most_common(1)[0][0]
                else:
                    mode_val = -1
                image = self.best_frames.get(track_id, (None, None))[1]
                self.api.send_result(time.time(), mode_val, track_id, count, image)
                expired.append(track_id)
        for tid in expired:
            del self.ocr_history[tid]
            if tid in self.best_frames:
                del self.best_frames[tid]


class VideoProcessor:
    def __init__(self, detector, tracker, input_source, output_file=None, verbose=False, crop_coords=None):
        self.detector = detector
        self.tracker = tracker
        self.input_source = input_source
        self.output_file = output_file
        self.verbose = verbose
        self.out = None
        self.crop_coords = self.validate_crop_coords(crop_coords)

    def validate_crop_coords(self, coords):
        if coords is None:
            return None
        if len(coords) != 4:
            raise ValueError("Crop coordinates must be a tuple of (x1, y1, x2, y2)")
        x1, y1, x2, y2 = coords
        if x2 <= x1 or y2 <= y1:
            raise ValueError(f"Invalid crop coordinates: ({x1}, {y1}), ({x2}, {y2}) — x2/y2 must be greater than x1/y1")
        return coords

    def run(self):
        results = self.detector.detect(source=self.input_source, verbose=self.verbose)
        crop_coords = self.crop_coords

        for result in results:
            frame = result.orig_img
            frame_h, frame_w, _ = frame.shape

            # Step 1: Crop frame
            if crop_coords:
                x1_crop, y1_crop, x2_crop, y2_crop = crop_coords
                frame = frame[y1_crop:y2_crop, x1_crop:x2_crop]
                frame_h, frame_w, _ = frame.shape  # Update dimensions

            side_panel = np.ones((frame_h, 300, 3), dtype=np.uint8) * 50
            combined_w = frame_w + 300

            if self.output_file and self.out is None:
                self.out = cv2.VideoWriter(self.output_file, cv2.VideoWriter_fourcc(*'mp4v'), 30, (combined_w, frame_h))

            tracked_bibs = {}

            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                # Step 2: Ignore boxes outside crop area
                if crop_coords:
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2
                    if not (x1_crop <= center_x <= x2_crop and y1_crop <= center_y <= y2_crop):
                        continue

                    # Step 3: Shift coordinates to match cropped frame
                    x1 -= x1_crop
                    x2 -= x1_crop
                    y1 -= y1_crop
                    y2 -= y1_crop

                if (x2 - x1 < BibTracker.MIN_BIB_WIDTH or y2 - y1 < BibTracker.MIN_BIB_HEIGHT):
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    continue

                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                track_id = int(box.id[0]) if hasattr(box, "id") and box.id is not None else None
                tracked_bibs[track_id] = (x1, y1, x2, y2)

                bib_box = frame[y1:y2, x1:x2]
                self.tracker.update(track_id, bib_box, self.detector, frame)

            self.tracker.draw_info(side_panel, tracked_bibs, frame_w)
            self.tracker.expire_old_entries()

            combined = np.hstack((frame, side_panel))
            if self.output_file:
                self.out.write(combined)

            cv2.imshow("Bib-Detector", combined)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        if self.out:
            self.out.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--device", help="Select CUDA Device", default="cpu")
    parser.add_argument("-i", "--input", help="Input stream (file or device)", default=0)
    parser.add_argument("-o", "--output", help="Output file")
    parser.add_argument("-v", "--verbose", help="Verbose mode", action="store_true")
    parser.add_argument("-u", "--url", help="URL to Race Timing Website")
    parser.add_argument("--demo", action="store_true", help="Use dummy Website API for testing")
    parser.add_argument("--crop", nargs=4, type=int, help="Crop box: x1 y1 x2 y2", default=None)
    parser.add_argument("-t", "--token", help="API Token")
    args = parser.parse_args()

    if args.demo:
        api = website_api.WebsiteAPIDemo(args.url)
        print("[INFO] Using WebsiteAPIDemo (images will be saved locally)")
    else:
        api = website_api.WebsiteAPI(args.url, args.token)
    detector = BibDetector("best.pt", args.device)
    tracker = BibTracker(api, "top-left")
    crop_coords = tuple(args.crop) if args.crop else None
    processor = VideoProcessor(detector, tracker, args.input, args.output, args.verbose, crop_coords)
    processor.run()


if __name__ == "__main__":
    main()
