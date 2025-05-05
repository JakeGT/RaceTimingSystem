import os, csv, cv2, time


class BibCSV:
    def __init__(self, filename):
        self.save_dir = filename
        os.makedirs(self.save_dir, exist_ok=True)
        self.confident_dir = os.path.join(self.save_dir, "confident")
        os.makedirs(self.confident_dir, exist_ok=True)
        self.unsure_dir = os.path.join(self.save_dir, "unsure")
        os.makedirs(self.unsure_dir, exist_ok=True)
        self.csv_filename = f"{filename}\\results.csv"
        self._initialize_csv()

    def _initialize_csv(self):
        if not os.path.exists(self.csv_filename):
            with open(self.csv_filename, mode="w", newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['Result', 'BibNumber', 'TrackerID'])

    def add_entry(self, timestamp, bib_number, tracker_id, image=None):
        with open(self.csv_filename, mode="a", newline='') as file:
            writer = csv.writer(file)
            writer.writerow([timestamp, bib_number, tracker_id])

        if image is not None:
            formatted_time = time.strftime("%H%M%S", time.gmtime(timestamp))
            if bib_number == -1:
                filename = f"{self.unsure_dir}/{tracker_id}_{formatted_time}.jpg"
            else:
                filename = f"{self.confident_dir}/{tracker_id}_{formatted_time}.jpg"
            cv2.imwrite(filename, image)
            print(f"Saved image: {filename}")
