from ultralytics import YOLO
import cv2
import time
import sys, getopt

device = "cpu"

argument_list = sys.argv[1:]
options = "d:"
long_options = ["device"]
try:
    arguments, values = getopt.getopt(argument_list, options, long_options)

    for current_arguments, current_value in arguments:
        if current_arguments in ("-d", "--device"):
            print(f"Using device {current_value}")
            device = current_value
except getopt.error as err:
    print(str(err))
    exit()


model = YOLO("best.pt")

input_video = "drogo.mp4"
output_video = "output.mp4"

cap = cv2.VideoCapture(input_video)


frame_width = int(cap.get(3))
frame_height = int(cap.get(4))
fps = int(cap.get(cv2.CAP_PROP_FPS))

out = cv2.VideoWriter(output_video, cv2.VideoWriter_fourcc(*'mp4v'), fps, (frame_width, frame_height))

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

    results = model(frame, device=device)

    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confidence = float(box.conf[0])
            label = f"Bib"
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    out.write(frame)

    cv2.imshow("Bib-Detector", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
