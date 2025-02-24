import re

import numpy as np
from ultralytics import YOLO
import cv2
import time
import easyocr
import argparse

device = "cpu"

parser = argparse.ArgumentParser()

parser.add_argument("-d", "--device", help="Select Device")
parser.add_argument("-i", "--input", help="Input file")
parser.add_argument("-o", "--output", help="Output file")

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


model = YOLO("best.pt")
reader = easyocr.Reader(['en'], gpu=(device != "cpu"))

cap = cv2.VideoCapture(video_input)


frame_width = int(cap.get(3))
frame_height = int(cap.get(4))
fps = int(cap.get(cv2.CAP_PROP_FPS))

out = cv2.VideoWriter(output_video, cv2.VideoWriter_fourcc(*'mp4v'), fps, (frame_width, frame_height))

if not cap.isOpened():
    print("Video input could not be loaded")
    exit()

prev_time = time.time()
while cap.isOpened():
    print(f"FPS: {1/(time.time() - prev_time)}")
    prev_time = time.time()
    ret, frame = cap.read()
    if not ret:
        break

    results = model(frame, device=device)

    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confidence = float(box.conf[0])

            bib_box = frame[y1:y2, x1:x2]
            if bib_box.size == 0:
                continue

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

            label = f"Bib: {bib_text}" if bib_text else "Bib"

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    if output_video:
        out.write(frame)

    cv2.imshow("Bib-Detector", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
if output_video:
    out.release()
cv2.destroyAllWindows()
