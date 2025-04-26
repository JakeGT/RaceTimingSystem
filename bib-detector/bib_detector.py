import re
import time
import cv2
import numpy as np
import argparse
from collections import defaultdict, Counter
from ultralytics import YOLO
import easyocr
import website_api


# Custom VideoCapture class to set resolution to 1080x1920
class CustomVideoCapture(cv2.VideoCapture):
    def __init__(self, src, apiPreference=cv2.CAP_ANY):
        super().__init__(src, apiPreference)
        self.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)


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

    def __init__(self, api):
        self.ocr_history = defaultdict(list)
        self.api = api
        self.best_frames = {}

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
        frame_h, frame_w, _ = frame.shape
        bib_h, bib_w, _ = bib_box.shape

        # Target size for the inset
        target_inset_w = int(frame_w * inset_fraction)
        aspect_ratio = bib_h / bib_w
        target_inset_h = int(target_inset_w * aspect_ratio)

        # Avoid the inset being larger than frame dimensions
        if target_inset_h + 2 * margin > frame_h or target_inset_w + 2 * margin > frame_w:
            return frame  # Skip if it won't fit

        # Resize the bib_box
        resized_bib = cv2.resize(bib_box, (target_inset_w, target_inset_h))

        # Copy the frame so we don't overwrite
        frame_copy = frame.copy()

        # Define top-right placement
        paste_x1 = frame_w - target_inset_w - margin
        paste_y1 = margin
        paste_x2 = frame_w - margin
        paste_y2 = margin + target_inset_h

        # Paste the resized bib_box
        frame_copy[paste_y1:paste_y2, paste_x1:paste_x2] = resized_bib

        # Draw a border rectangle
        cv2.rectangle(frame_copy, (paste_x1, paste_y1), (paste_x2, paste_y2), border_color, border_thickness)

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
    def __init__(self, detector, tracker, input_source, output_file=None, verbose=False):
        self.detector = detector
        self.tracker = tracker
        self.input_source = input_source
        self.output_file = output_file
        self.verbose = verbose
        self.out = None

    def run(self):
        results = self.detector.detect(source=self.input_source, verbose=self.verbose)
        for result in results:
            frame = result.orig_img
            frame_h, frame_w, _ = frame.shape
            side_panel = np.ones((frame_h, 300, 3), dtype=np.uint8) * 50
            combined_w = frame_w + 300

            if self.output_file and self.out is None:
                self.out = cv2.VideoWriter(self.output_file, cv2.VideoWriter_fourcc(*'mp4v'), 30, (combined_w, frame_h))

            tracked_bibs = {}

            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
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
    args = parser.parse_args()

    if args.demo:
        api = website_api.WebsiteAPIDemo(args.url)
        print("[INFO] Using WebsiteAPIDemo (images will be saved locally)")
    else:
        api = website_api.WebsiteAPI(args.url)
    detector = BibDetector("best.pt", args.device)
    tracker = BibTracker(api)
    processor = VideoProcessor(detector, tracker, args.input, args.output, args.verbose)
    processor.run()


if __name__ == "__main__":
    main()
