import sys
import os
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QPushButton,
    QLineEdit, QFileDialog, QMessageBox, QHBoxLayout
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from datetime import datetime


class BibCorrector(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bib Number Correction Tool")
        self.setGeometry(100, 100, 800, 600)

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.bib_input = QLineEdit()
        self.bib_input.setPlaceholderText("Enter corrected BibNumber")

        self.info_label = QLabel()
        self.save_button = QPushButton("Save")
        self.next_button = QPushButton("Next")

        layout = QVBoxLayout()
        layout.addWidget(self.image_label)
        layout.addWidget(self.info_label)

        input_layout = QHBoxLayout()
        input_layout.addWidget(self.bib_input)
        input_layout.addWidget(self.save_button)
        input_layout.addWidget(self.next_button)
        layout.addLayout(input_layout)

        self.setLayout(layout)

        self.save_button.clicked.connect(self.save_correction)
        self.next_button.clicked.connect(self.next_image)

        self.load_data()

    def load_data(self):
        self.csv_path = "results/results.csv"
        self.df = pd.read_csv(self.csv_path)

        # Filter rows where BibNumber is -1 or clearly wrong
        self.unsure_entries = self.df[self.df['BibNumber'] == -1].copy()

        # Add confident bibs for review (optionally you can limit this)
        confident_path = "results/confident/"
        for _, row in self.df.iterrows():
            if row['BibNumber'] != -1:
                img_path = os.path.join(confident_path, f"{row['TrackerID']}_{self.format_time(row['Result'])}.jpg")
                if os.path.exists(img_path):
                    self.unsure_entries = pd.concat([self.unsure_entries, pd.DataFrame([row])])

        self.unsure_entries.reset_index(drop=True, inplace=True)
        self.current_index = 0
        self.load_image()

    def format_time(self, timestamp):
        return datetime.fromtimestamp(timestamp).strftime("%H%M%S")

    def load_image(self):
        if self.current_index >= len(self.unsure_entries):
            QMessageBox.information(self, "Done", "No more images to review.")
            return

        row = self.unsure_entries.iloc[self.current_index]
        tracker_id = row['TrackerID']
        timestamp = row['Result']
        bib = row['BibNumber']
        formatted_time = self.format_time(timestamp)

        unsure_path = f"results/unsure/{tracker_id}_{formatted_time}.jpg"
        confident_path = f"results/confident/{tracker_id}_{formatted_time}.jpg"
        image_path = unsure_path if os.path.exists(unsure_path) else confident_path

        if os.path.exists(image_path):
            pixmap = QPixmap(image_path).scaledToWidth(600)
            self.image_label.setPixmap(pixmap)
            self.info_label.setText(f"TrackerID: {tracker_id}, Timestamp: {formatted_time}, Bib: {bib}")
            self.bib_input.setText("" if bib == -1 else str(bib))
        else:
            self.info_label.setText("Image not found.")
            self.bib_input.setText("")
            self.image_label.clear()

    def save_correction(self):
        new_bib = self.bib_input.text().strip()
        if not new_bib.isdigit():
            QMessageBox.warning(self, "Invalid Input", "BibNumber must be an integer.")
            return

        real_index = self.unsure_entries.index[self.current_index]
        self.df.loc[real_index, 'BibNumber'] = int(new_bib)
        self.df.to_csv(self.csv_path, index=False)
        QMessageBox.information(self, "Saved", "Correction saved.")

    def next_image(self):
        self.current_index += 1
        self.load_image()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BibCorrector()
    window.show()
    sys.exit(app.exec_())
