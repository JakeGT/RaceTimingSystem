import sys
import cv2
import threading
import torch
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QFileDialog, QComboBox, QCheckBox, QVBoxLayout, QHBoxLayout, QMessageBox
)
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QTimer
from bib_detector import BibDetector, BibTracker, VideoProcessor
import website_api


class BibDetectorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bib Detector GUI")

        self.device_label = QLabel("Device:")
        self.device_combo = QComboBox()
        self.populate_device_list()

        self.camera_label = QLabel("Camera Input:")
        self.camera_combo = QComboBox()
        self.populate_camera_inputs()
        self.camera_combo.currentIndexChanged.connect(self.change_camera_preview)

        self.refresh_button = QPushButton("Refresh Cameras")
        self.refresh_button.clicked.connect(self.populate_camera_inputs)

        self.output_label = QLabel("Output File:")
        self.output_line = QLineEdit()
        self.output_browse = QPushButton("Browse")
        self.output_browse.clicked.connect(self.browse_output)

        self.url_label = QLabel("Race Timing URL:")
        self.url_line = QLineEdit()

        self.verbose_check = QCheckBox("Verbose")
        self.start_button = QPushButton("Start Detection")
        self.start_button.clicked.connect(self.start_detection)

        self.preview_label = QLabel("Camera Preview")
        self.preview_label.setFixedSize(640, 360)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_preview)
        self.cap = None

        self.layout = QVBoxLayout()
        self.add_widgets()
        self.setLayout(self.layout)

        self.timer.start(30)

    def add_widgets(self):
        self.layout.addLayout(self.row(self.device_label, self.device_combo))
        self.layout.addLayout(self.row(self.camera_label, self.camera_combo, self.refresh_button))
        self.layout.addLayout(self.row(self.output_label, self.output_line, self.output_browse))
        self.layout.addLayout(self.row(self.url_label, self.url_line))
        self.layout.addWidget(self.verbose_check)
        self.layout.addWidget(self.preview_label)
        self.layout.addWidget(self.start_button)

    def row(self, *widgets):
        h = QHBoxLayout()
        for w in widgets:
            h.addWidget(w)
        return h

    def populate_device_list(self):
        self.device_combo.clear()
        self.device_combo.addItem("cpu")
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                self.device_combo.addItem(f"cuda:{i}")

    def populate_camera_inputs(self):
        self.camera_combo.clear()
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    self.camera_combo.addItem(f"Camera {i}", i)
                cap.release()

        if self.camera_combo.count() > 0:
            self.change_camera_preview()

    def browse_output(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Select Output File", filter="MP4 files (*.mp4)")
        if filename:
            self.output_line.setText(filename)

    def change_camera_preview(self):
        index = self.camera_combo.currentData()
        if self.cap:
            self.cap.release()
        if index is not None:
            self.cap = cv2.VideoCapture(index)
            if not self.cap.isOpened():
                QMessageBox.critical(self, "Camera Error", f"Could not open camera {index}.")
                self.cap = None

    def update_preview(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                return
            frame = cv2.resize(frame, (640, 360))
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            qt_img = QImage(rgb_image.data, rgb_image.shape[1], rgb_image.shape[0],
                            rgb_image.strides[0], QImage.Format_RGB888)
            self.preview_label.setPixmap(QPixmap.fromImage(qt_img))

    def start_detection(self):
        device = self.device_combo.currentText()
        input_source = self.camera_combo.currentData()
        output_file = self.output_line.text() or None
        url = self.url_line.text()
        verbose = self.verbose_check.isChecked()

        if not url:
            QMessageBox.critical(self, "Missing URL", "Please enter the Race Timing Website URL.")
            return

        if self.cap:
            self.cap.release()
            self.cap = None
        self.timer.stop()

        api = website_api.WebsiteAPI(url)
        detector = BibDetector("best.pt", device)
        tracker = BibTracker(api)
        processor = VideoProcessor(detector, tracker, input_source, output_file, verbose)

        self.hide()
        threading.Thread(target=lambda: self.run_processor(processor), daemon=True).start()

    def run_processor(self, processor):
        processor.run()
        self.show()
        self.timer.start(30)
        self.change_camera_preview()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BibDetectorApp()
    window.show()
    sys.exit(app.exec_())
