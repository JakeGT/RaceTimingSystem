#  scripts/image-upload.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
import requests
import datetime


# -------------------------------------------------- Main Code Execution -----------------------------------------------
url = "http://127.0.0.1:8000/upload-image/"

files = {'image': open('running_man.jpg', 'rb')}

time_str = '12:30:00'

today_date = datetime.datetime.today().strftime('%Y-%m-%d')
timestamp = f"{today_date} {time_str}"   # YYYY-MM-DD HH:MM:SS

data = {
    'timestamp': timestamp,
    'race_id': 1
}

response = requests.post(url, files=files, data=data)

print("Response Status Code:", response.status_code)
print("Response Text:", response.text)

try:
    response_json = response.json()
    print(response_json)
except requests.exceptions.JSONDecodeError:
    print("Error: Response is not JSON")
