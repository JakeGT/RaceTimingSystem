import time
import os
import cv2
import grequests
import threading


class WebsiteAPIDemo:
    def __init__(self, url, token=None):
        self.url = url
        self.token = token
        self.save_dir = "debug_images"
        os.makedirs(self.save_dir, exist_ok=True)

    def send_result(self, timestamp, bib_number, tracker_id, num_entries, image):
        print("---------------------------------------------------------")
        if bib_number != "":
            print("Good confidence bib:")
            print(f"Timestamp: {timestamp}, bib_number: {bib_number}, tracker_id: {tracker_id}, num_entries: {num_entries}")
        else:
            print(f"Low confidence bib")
            print(f"Timestamp: {timestamp}, tracker_id: {tracker_id}, num_entries: {num_entries}")
        print("---------------------------------------------------------\n")

        if image is not None:
            formatted_time = time.strftime("%Y%m%d_%H%M%S", time.gmtime(timestamp))
            filename = f"{self.save_dir}/bib_{tracker_id}_{formatted_time}.jpg"
            cv2.imwrite(filename, image)
            print(f"Saved debug image: {filename}")

class WebsiteAPI:
    def __init__(self, base_url, token=None):
        self.url_data = f"{base_url}/upload"
        self.url_image = f"{base_url}/upload_image"
        print(f"Data URL: {self.url_data}")
        print(f"Image URL: {self.url_image}")
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
            headers = {"Content-Type": "application/json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            data_req = grequests.post(self.url_data, json=data, headers=headers)
            data_responses = grequests.map([data_req], size=1)
            if data_responses and data_responses[0]:
                if data_responses[0].status_code != 200:
                    print(f"Error sending data: {data_responses[0].status_code}")
            else:
                print("No response from server")

            if image is not None:
                success, buffer = cv2.imencode(".jpg", image)
                if success:
                    image_bytes = buffer.tobytes()
                    files = {"image": ("image.jpg", image_bytes, "image/jpeg")}
                    image_req = grequests.post(self.url_image, files=files, headers=headers)
                    image_responses = grequests.map([image_req], size=1)
                    if image_responses and image_responses[0] and image_responses[0].status_code != 200:
                        print(f"Error sending image: {image_responses[0].status_code}")
                else:
                    print("Failed to encode image to JPEG")

        threading.Thread(target=task, daemon=True).start()
