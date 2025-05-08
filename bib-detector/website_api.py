import time
import os
import cv2
import requests
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
            data = {
                "time": timestamp,
                "bib_number": bib_number,
                "tracker_id": tracker_id,
                "num_entries": num_entries,
            }
            headers = {"Content-Type": "application/json"}
            if self.token:
                headers["Authorization"] = f"Token {self.token}"

            # Send result data with requests
            try:
                data_resp = requests.post(self.url_data, json=data, headers=headers)
                try:
                    print("Data upload response:", data_resp.json())
                except Exception:
                    print(f"Data upload failed [{data_resp.status_code}]: Invalid JSON")
            except Exception as e:
                print(f"Data upload request failed: {e}")

            # Send image with requests (NOT grequests)
            if image is not None:
                success, buffer = cv2.imencode(".jpg", image)
                if success:
                    image_bytes = buffer.tobytes()
                    files = {"image": ("image.jpg", image_bytes, "image/jpeg")}
                    form_data = {
                        "timestamp": timestamp,
                        "bib_number": str(bib_number),
                    }
                    image_headers = {"Authorization": f"Token {self.token}"} if self.token else {}

                    try:
                        img_resp = requests.post(self.url_image, data=form_data, files=files, headers=image_headers)
                        try:
                            print("Image upload response:", img_resp.json())
                        except Exception:
                            print(f"Status Code - [{img_resp.status_code}]: Invalid JSON")
                    except Exception as e:
                        print(f"Image upload request failed: {e}")
                else:
                    print("Failed to encode image to JPEG")

        threading.Thread(target=task, daemon=True).start()

