import re
from collections import defaultdict, Counter

import numpy as np
from ultralytics import YOLO
import cv2
import time
import easyocr
import argparse

# Config
device = "cpu"
OCR_CONFIDENCE_THRESHOLD = 0.7
MIN_BIB_WIDTH = 60
MIN_BIB_HEIGHT = 60

# CLI Arguments
parser = argparse.ArgumentParser()
parser.add_argument("-d", "--device", help="Select Device")
parser.add_argument("-i", "--input", help="Input file")
parser.add_argument("-o", "--output", help="Output file")
parser.add_argument("-v", "--verbose", help="Verbose mode", action="store_true")
parser.add_argument("-dg", "--debug", help="Debug Commands")
args = parser.parse_args()

if args.device:
    device = args.device
video_input = args.input if args.input else 0
output_video = args.output if args.output else None
verbose = args.verbose
debug = args.debug.split(',') if args.debug else None

# Load YOLO model and OCR reader
model = YOLO("best.pt")
reader = easyocr.Reader(['en'], gpu=(device != "cpu"))

# For output video settings we need to know frame dimensions;
# so we open the video capture momentarily.
cap = cv2.VideoCapture(video_input)
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = int(cap.get(cv2.CAP_PROP_FPS))
cap.release()

output_frame_width = frame_width + 300
out = None
if output_video:
    out = cv2.VideoWriter(output_video, cv2.VideoWriter_fourcc(*'mp4v'), fps, (output_frame_width, frame_height))

# Dictionary to hold OCR history for each tracker ID
bib_ocr_history = defaultdict(list)

# Use YOLO's Tracking with ByteTrack
# The track() method automatically assigns a unique ID to each detected object.
results = model.track(source=video_input, device=device, stream=True, verbose=verbose, tracker="bytetrack.yaml")

prev_time = time.time()
frame_count = 0

for result in results:
    frame_count += 1
    frame = result.orig_img  # original frame from the tracker result
    side_panel = np.ones((frame_height, 300, 3), dtype=np.uint8) * 50

    # Dictionary to keep track of bib boxes using their tracker IDs
    tracked_bibs = {}

    # Iterate over all detected boxes in the current frame
    for box in result.boxes:
        # Get box coordinates and confidence
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        confidence = float(box.conf[0])
        # Retrieve tracker ID (assumes the tracker returns an 'id' attribute)
        track_id = int(box.id[0]) if hasattr(box, "id") and box.id is not None else None

        # Check that the detected region meets minimum size requirements
        bib_width = x2 - x1
        bib_height = y2 - y1
        if bib_width < MIN_BIB_WIDTH or bib_height < MIN_BIB_HEIGHT:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            continue

        # Draw a bounding box around the detected bib
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        tracked_bibs[track_id] = (x1, y1, x2, y2)

        # Extract the bib region for OCR processing
        bib_box = frame[y1:y2, x1:x2]
        if bib_box.size == 0:
            continue
        bib_box_gray = cv2.cvtColor(bib_box, cv2.COLOR_BGR2GRAY)
        _, roi_thresh = cv2.threshold(bib_box_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        bib_result = reader.readtext(roi_thresh, detail=1)

        # Process OCR results: choose the text detection with the largest height (as a proxy for clarity)
        bib_text = ""
        largest_height = 0
        final_confidence = 0
        for detection in bib_result:
            bbox_points, text, conf = detection
            pts = np.array(bbox_points, dtype=np.int32)
            rx, ry, rw, rh = cv2.boundingRect(pts)
            if rh > largest_height:
                largest_height = rh
                bib_text = text.strip()
                final_confidence = conf

        # If a confident OCR result is obtained, store it in the history for this tracker
        if bib_text and final_confidence > OCR_CONFIDENCE_THRESHOLD:
            bib_ocr_history[track_id].append(bib_text)

    # Draw side panel with tracker and OCR information
    y_offset = 20
    for track_id, box in tracked_bibs.items():
        x1, y1, x2, y2 = box
        # Draw a line connecting the detection to its info on the side panel
        line_start = (x2, (y1 + y2) // 2)
        line_end = (frame_width + 10, y_offset + 5)
        cv2.line(frame, line_start, line_end, (255, 0, 0), 1)

        # Choose the most common OCR reading for this tracker ID
        mode_bib_text = Counter(bib_ocr_history[track_id]).most_common(1)[0][0] if bib_ocr_history[track_id] else "Unknown"
        cv2.putText(side_panel, f"Tracker ID: {track_id}", (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y_offset += 20
        cv2.putText(side_panel, f"Bib Number: {mode_bib_text}", (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y_offset += 20
        cv2.putText(side_panel, "OCR Instances:", (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y_offset += 20
        for instance in bib_ocr_history[track_id][-5:]:
            cv2.putText(side_panel, f"- {instance}", (10, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            y_offset += 20
        y_offset += 10

    # Combine the main frame and side panel
    combined_frame = np.hstack((frame, side_panel))
    if output_video:
        out.write(combined_frame)

    cv2.imshow("Bib-Detector", combined_frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

if output_video:
    out.release()
cv2.destroyAllWindows()
