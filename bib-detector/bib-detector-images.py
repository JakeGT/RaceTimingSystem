import argparse
import math
import re
import numpy as np
from ultralytics import YOLO
import cv2
import os, glob
import easyocr

FONT_SCALE = 1e-3
THICKNESS_SCALE = 2e-3


device = "cpu"
input_folder = "2hills2024"
output_folder = "2hills_output"

parser = argparse.ArgumentParser()

parser.add_argument("-d", "--device", help="Select Device")
parser.add_argument("-i", "--input", help="Input file")
parser.add_argument("-o", "--output", help="Output file")

args = parser.parse_args()
if args.device:
    device = args.device
if args.input:
    input_folder = args.input
if args.output:
    output_folder = args.output


model = YOLO("best.pt")
reader = easyocr.Reader(['en'], gpu=(device != "cpu"))

os.makedirs(output_folder, exist_ok=True)

image_extensions = ("*.jpg", "*.jpeg", "*.png", "*.bmp")
image_files = []
for ext in image_extensions:
    image_files.extend(glob.glob(os.path.join(input_folder, ext)))


for image_path in image_files:
    image = cv2.imread(image_path)
    if image is None:
        print(f"Failed to load image {image_path}")
        continue

    results = model(image, device=device)
    img_h, img_w, _ = image.shape

    font_scale = min(img_h, img_w) * FONT_SCALE
    thickness = math.ceil(min(img_w, img_h) * THICKNESS_SCALE)

    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            bib_box = image[y1:y2, x1:x2]
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

            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(image, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 255, 0), thickness)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    output_path = os.path.join(output_folder, os.path.basename(image_path))
    cv2.imwrite(output_path, image)

cv2.destroyAllWindows()
