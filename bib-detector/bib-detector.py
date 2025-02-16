from ultralytics import YOLO
import cv2
import time

model = YOLO("best.pt")

input_video = "drogo.mp4"

cap = cv2.VideoCapture(input_video)

if not cap.isOpened():
    print("File cound not be found")
    exit()

prev_time = time.time()
while cap.isOpened():
    print(f"FPS: {1/(time.time() - prev_time)}")
    prev_time = time.time()
    ret, frame = cap.read()
    if not ret:
        break

    results = model(frame)

    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confidence = float(box.conf[0])
            label = f"Bib"
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    cv2.imshow("Bib-Detector", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
