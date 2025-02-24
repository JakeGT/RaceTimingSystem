import re
from collections import defaultdict, Counter

import numpy as np
from ultralytics import YOLO
import cv2
import time
import easyocr
import argparse

device = "cpu"
OCR_CONFIDENCE_THRESHOLD = 0.7
FRAME_LEEWAY = 15
FRAME_EXPIRY_THRESHOLD = 120
MIN_BIB_WIDTH = 60
MIN_BIB_HEIGHT = 60

parser = argparse.ArgumentParser()

parser.add_argument("-d", "--device", help="Select Device")
parser.add_argument("-i", "--input", help="Input file")
parser.add_argument("-o", "--output", help="Output file")
parser.add_argument("-v", "--verbose", help="Verbose mode", action="store_true")
parser.add_argument("-dg", "--debug", help="Debug Commands")

args = parser.parse_args()
if args.device:
    device = args.device

if args.input:
    video_input = args.input
else:
    video_input = 0

if args.output:
    output_video = args.output
else:
    output_video = None

if args.verbose:
    verbose = True
else:
    verbose = False

if args.debug:
    debug = args.debug.split(',')
else:
    debug = None


model = YOLO("best.pt")
reader = easyocr.Reader(['en'], gpu=(device != "cpu"))

cap = cv2.VideoCapture(video_input)

frame_width = int(cap.get(3))
frame_height = int(cap.get(4))
fps = int(cap.get(cv2.CAP_PROP_FPS))

output_frame_width = frame_width + 300

out = None
if output_video:
    out = cv2.VideoWriter(output_video, cv2.VideoWriter_fourcc(*'mp4v'), fps, (output_frame_width, frame_height))

bib_trackers = {}
bib_ocr_history = defaultdict(list)
next_bib_id = 1

if not cap.isOpened():
    print("Video input could not be loaded")
    exit()

prev_time = time.time()
frame_count = 0
while cap.isOpened():
    frame_count += 1
    if verbose:
        print(f"FPS: {1 / (time.time() - prev_time)}")
    prev_time = time.time()
    ret, frame = cap.read()
    if not ret:
        break

    side_panel = np.ones((frame_height, 300, 3), dtype=np.uint8) * 50

    results = model(frame, device=device, verbose=verbose)

    detected_bibs = []

    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confidence = float(box.conf[0])

            bib_width = x2 - x1
            bib_height = y2 - y1
            if bib_width < MIN_BIB_WIDTH or bib_height < MIN_BIB_HEIGHT:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                continue

            bib_box = frame[y1:y2, x1:x2]
            if bib_box.size == 0:
                continue

            detected_bibs.append((x1, y1, x2, y2))
    for tracker_id in bib_trackers.keys():
        bib_trackers[tracker_id]["missed_frames"] += 1

    updated_trackers = {}
    for bib in detected_bibs:
        x1, y1, x2, y2 = bib
        matched_id = None
        highest_iou = 0

        for bib_id, data in bib_trackers.items():
            tx1, ty1, tx2, ty2 = data["box"]
            inter_area = max(0, min(x2, tx2) - max(x1, tx1)) * max(1, min(y2, ty2) - max(y1, ty1))
            bib_area = (x2 - x1) * (y2 - y1)
            tracker_area = (tx2 - tx1) * (ty2 - ty1)
            union_area = bib_area + tracker_area - inter_area
            iou = inter_area / union_area if union_area else 0

            if iou > 0.3 and iou > highest_iou:
                matched_id = bib_id
                highest_iou = iou

        if matched_id is None:
            matched_id = next_bib_id
            next_bib_id += 1

        updated_trackers[matched_id] = {
            "box": (x1, y1, x2, y2),
            "missed_frames": 0,
            "last_seen_frame": frame_count
        }

        bib_box_gray = cv2.cvtColor(bib_box, cv2.COLOR_BGR2GRAY)
        _, roi_thresh = cv2.threshold(bib_box_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        bib_result = reader.readtext(roi_thresh, detail=1)
        bib_text = ""
        largest_height = 0

        for detection in bib_result:
            bbox_points, text, conf = detection
            pts = np.array(bbox_points, dtype=np.int32)
            rx, ry, rw, rh = cv2.boundingRect(pts)
            if rh > largest_height:
                largest_height = rh
                bib_text = text.strip()
                final_confidence = conf

        if bib_text and final_confidence > OCR_CONFIDENCE_THRESHOLD:
            bib_ocr_history[matched_id].append(bib_text)

    updated_trackers = {
        bib_id: data
        for bib_id, data in updated_trackers.items()
        if frame_count - data.get("last_seen_frame", frame_count) <= FRAME_EXPIRY_THRESHOLD
    }

    bib_trackers = updated_trackers

    y_offset = 20

    for bib_id, data in bib_trackers.items():
        x1, y1, x2, y2 = data["box"]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        line_start = (x2, (y1 + y2) // 2)
        line_end = (frame_width + 10, y_offset + 5)
        cv2.line(frame, line_start, line_end, (255, 0, 0), 1)

        mode_bib_text = Counter(bib_ocr_history[bib_id]).most_common(1)[0][0] if bib_ocr_history[bib_id] else "Unknown"
        cv2.putText(side_panel, f"Tracker ID: {bib_id}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y_offset += 20
        cv2.putText(side_panel, f"Bib Number: {mode_bib_text}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 255, 0), 1)
        y_offset += 20
        cv2.putText(side_panel, "OCR Instances:", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y_offset += 20
        for instance in bib_ocr_history[bib_id][-5:]:  # Display last 5 detections
            cv2.putText(side_panel, f"- {instance}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            y_offset += 20
        y_offset += 10

    combined_frame = np.hstack((frame, side_panel))

    if output_video:
        out.write(combined_frame)

    cv2.imshow("Bib-Detector", combined_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
if output_video:
    out.release()
cv2.destroyAllWindows()
