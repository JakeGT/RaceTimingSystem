import time

import cv2
import grequests
import threading


class WebsiteAPIDemo:
    def __init__(self, url, token=None):
        self.url = url
        self.token = token

    def send_result(timestamp, bib_number, tracker_id, num_entries):
        print("---------------------------------------------------------")
        print("Good confidence bib:")
        print(f"Timestamp: {timestamp}, bib_number: {bib_number}, tracker_id: {tracker_id}, num_entries: {num_entries}")
        print("---------------------------------------------------------\n")

    def send_unsure_result(timestamp, tracker_id, num_entries):
        print("---------------------------------------------------------")
        print(f"Low confidence bib")
        print(f"Timestamp: {timestamp}, tracker_id: {tracker_id}, num_entries: {num_entries}")
        print("---------------------------------------------------------\n")


class WebsiteAPI:
    def __init__(self, url, token=None):
        self.url = url + "/upload"
        print(self.url)
        self.token = token

    def send_result(self, timestamp, bib_number, tracker_id, num_entries, image):
        def task():
            formatted_time = time.strftime("%H:%M:%S", time.gmtime(timestamp))
            data = {
                "time": formatted_time,
                "bib_number": bib_number,
                "tracker_id": tracker_id,
                "num_entries": num_entries,
            }
            if image is not None:
                success, buffer = cv2.imencode(".jpg", image)
            else:
                success = False
            if not success:
                print("Failed to encode image as JPEG")
                files = {}
            else:
                image_bytes = buffer.tobytes()
                files = {"image.jpg", image_bytes, "image/jpeg"}
            headers = {"Content-Type": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            req = grequests.post(self.url, json=data, files=files, headers=headers)
            responses = grequests.map([req], size=1)
            if responses and responses[0]:
                if responses[0].status_code != 200:
                    print(f"Error sending result: {responses[0].status_code}")
            else:
                print("No response from server")

        threading.Thread(target=task, daemon=True).start()
