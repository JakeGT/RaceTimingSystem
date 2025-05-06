import sys
import os
import shutil
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QPushButton,
    QLineEdit, QFileDialog, QMessageBox, QHBoxLayout
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

class BibCorrector(QWidget):
    def __init__(self, results_dir):
        super().__init__()
        self.setWindowTitle("Bib Number Correction Tool")
        self.setGeometry(100, 100, 800, 600)

        self.results_dir = results_dir
        self.unsure_dir = os.path.join(results_dir, "unsure")
        self.confident_dir = os.path.join(results_dir, "confident")
        self.reviewed_dir = os.path.join(results_dir, "reviewed")

        os.makedirs(self.reviewed_dir, exist_ok=True)

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
        self.csv_path = os.path.join(self.results_dir, "results.csv")
        self.df = pd.read_csv(self.csv_path)

        self.unsure_entries = self.df[self.df['BibNumber'] == -1].copy()

        # Optional: Include confident bibs as well (if you want to review all)
        for _, row in self.df.iterrows():
            if row['BibNumber'] != -1:
                full_path = os.path.join(self.results_dir, row['filename'])
                if os.path.exists(full_path):
                    self.unsure_entries = pd.concat([self.unsure_entries, pd.DataFrame([row])])

        self.unsure_entries.reset_index(drop=True, inplace=True)
        self.current_index = 0
        self.load_image()

    def get_current_image_path(self, row):
        return os.path.join(self.results_dir, "unsure", (row['filename'] + '.jpg'))

    def load_image(self):
        if self.current_index >= len(self.unsure_entries):
            QMessageBox.information(self, "Done", "No more images to review.")
            return

        row = self.unsure_entries.iloc[self.current_index]
        self.current_row = row
        image_path = self.get_current_image_path(row)

        if os.path.exists(image_path):
            pixmap = QPixmap(image_path).scaledToWidth(600)
            self.image_label.setPixmap(pixmap)
            self.info_label.setText(
                f"Filename: {row['filename']} | TrackerID: {row['TrackerID']} | Bib: {row['BibNumber']}")
            self.bib_input.setText("" if row['BibNumber'] == -1 else str(row['BibNumber']))
        else:
            print(image_path)
            self.info_label.setText("Image not found.")
            self.bib_input.setText("")
            self.image_label.clear()

    def save_correction(self):
        new_bib = self.bib_input.text().strip()
        if not new_bib.isdigit():
            QMessageBox.warning(self, "Invalid Input", "BibNumber must be an integer.")
            return

        # Save correction to main CSV
        real_index = self.df[self.df['filename'] == self.current_row['filename']].index
        self.df.loc[real_index, 'BibNumber'] = int(new_bib)
        self.df.to_csv(self.csv_path, index=False)

        # Move image to reviewed/
        image_path = self.get_current_image_path(self.current_row)
        if os.path.exists(image_path):
            reviewed_path = os.path.join(self.reviewed_dir, os.path.basename(image_path))
            shutil.move(image_path, reviewed_path)

        QMessageBox.information(self, "Saved", "Correction saved and image moved.")
        self.next_image()

    def next_image(self):
        self.current_index += 1
        self.load_image()

def select_results_folder():
    app = QApplication(sys.argv)
    folder = QFileDialog.getExistingDirectory(None, "Select Results Folder")
    if folder:
        window = BibCorrector(folder)
        window.show()
        sys.exit(app.exec_())
    else:
        QMessageBox.warning(None, "No Folder", "You must select a results folder to continue.")
        sys.exit()

if __name__ == "__main__":
    select_results_folder()
