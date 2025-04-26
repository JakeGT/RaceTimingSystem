import sys
import threading
import torch
import re
import cv2
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QFileDialog, QComboBox, QCheckBox, QVBoxLayout, QHBoxLayout, QMessageBox,
    QStackedLayout, QInputDialog
)
from PyQt5.QtMultimedia import QCameraInfo, QCamera
from PyQt5.QtMultimediaWidgets import QCameraViewfinder
import website_api
from bib_detector import BibDetector, BibTracker, VideoProcessor


class BibDetectorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.camera = None
        self.ip_camera_url = None
        self.setWindowTitle("Bib Detector GUI")

        self.device_label = QLabel("Device:")
        self.device_combo = QComboBox()
        self.populate_device_list()

        self.camera_label = QLabel("Camera Input:")
        self.camera_combo = QComboBox()
        self.camera_combo.setEditable(True)
        self.camera_combo.setPlaceholderText("Select camera or enter IP address...")
        self.camera_combo.currentIndexChanged.connect(self.change_camera_preview)

        self.refresh_button = QPushButton("Refresh Cameras")
        self.refresh_button.clicked.connect(self.populate_camera_inputs)

        self.connect_ip_button = QPushButton("Connect IP Camera")
        self.connect_ip_button.clicked.connect(self.connect_ip_camera)

        self.output_label = QLabel("Output File:")
        self.output_line = QLineEdit()
        self.output_browse = QPushButton("Browse")
        self.output_browse.clicked.connect(self.browse_output)

        self.url_label = QLabel("Race Timing URL:")
        self.url_line = QLineEdit()

        self.token_label = QLabel("API Token:")
        self.token_line = QLineEdit()

        self.load_config_button = QPushButton("Load Config")
        self.load_config_button.clicked.connect(self.load_config)

        self.verbose_check = QCheckBox("Verbose")
        self.start_button = QPushButton("Start Detection")
        self.start_button.clicked.connect(self.start_detection)

        self.preview_label = QLabel("Camera Preview")

        # Stacked layout for previews
        self.preview_widget = QWidget()
        self.preview_stack = QStackedLayout()

        self.viewfinder = QCameraViewfinder()
        self.blank_label = QLabel()
        self.blank_label.setFixedSize(640, 360)
        self.blank_label.setAlignment(Qt.AlignCenter)
        self.blank_label.setStyleSheet("background-color: black;")

        self.preview_stack.addWidget(self.viewfinder)  # index 0
        self.preview_stack.addWidget(self.blank_label) # index 1
        self.preview_widget.setLayout(self.preview_stack)

        self.populate_camera_inputs()

        self.layout = QVBoxLayout()
        self.add_widgets()
        self.setLayout(self.layout)

    def add_widgets(self):
        self.layout.addLayout(self.row(self.device_label, self.device_combo))
        self.layout.addLayout(self.row(self.camera_label, self.camera_combo, self.refresh_button, self.connect_ip_button))
        self.layout.addLayout(self.row(self.output_label, self.output_line, self.output_browse))
        self.layout.addLayout(self.row(self.url_label, self.url_line))
        self.layout.addLayout(self.row(self.token_label, self.token_line))
        self.layout.addWidget(self.load_config_button)
        self.layout.addWidget(self.verbose_check)
        self.layout.addWidget(self.preview_label)
        self.layout.addWidget(self.preview_widget)
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
        self.available_cameras = QCameraInfo.availableCameras()
        for cam in self.available_cameras:
            self.camera_combo.addItem(cam.description(), cam)

        if self.camera_combo.count() > 0:
            self.change_camera_preview()

    def load_config(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Config File", filter="INI files (*.ini);;All files (*)")
        if filename:
            try:
                with open(filename, 'r') as f:
                    lines = f.readlines()
                config = {}
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#"):  # Skip comments
                        if '=' in line:
                            key, value = line.split('=', 1)
                            config[key.strip().upper()] = value.strip()

                token = config.get('TOKEN')
                url = config.get('URL')

                if token:
                    self.token_line.setText(token)

                if url:
                    if url.startswith('/'):
                        # Prompt for IP base if relative URL
                        base_ip, ok = QInputDialog.getText(self, "Enter IP Address",
                                                           "Enter IP address for Race Timing Server (e.g., 192.168.1.100):")
                        if ok and base_ip:
                            full_url = f"http://{base_ip}{url}"
                            self.url_line.setText(full_url)
                        else:
                            QMessageBox.warning(self, "Missing IP", "No IP address entered. URL will not be updated.")
                    else:
                        self.url_line.setText(url)

                QMessageBox.information(self, "Config Loaded", "Configuration loaded successfully.")

            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Failed to load config file.\n{e}")

    def browse_output(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Select Output File", filter="MP4 files (*.mp4)")
        if filename:
            self.output_line.setText(filename)

    def change_camera_preview(self):
        camera_info = self.camera_combo.currentData()
        if camera_info:
            self.stop_all_cameras()

            self.preview_stack.setCurrentIndex(0)  # Show viewfinder

            self.camera = QCamera(camera_info)
            self.camera.setViewfinder(self.viewfinder)
            self.camera.start()

    def connect_ip_camera(self):
        ip_address = self.camera_combo.currentText().strip()
        if not ip_address:
            QMessageBox.critical(self, "Missing IP", "Please enter an IP address.")
            return

        # Auto-add http:// if missing
        if not ip_address.startswith('http'):
            ip_address = 'http://' + ip_address

        # Ensure /video is present
        if '/video' not in ip_address:
            if ip_address.endswith('/'):
                ip_address += 'video'
            else:
                ip_address += '/video'

        if '?' in ip_address:
            ip_address += '&1920x1080'
        else:
            ip_address += '?1920x1080'

        if not self.is_valid_ip_or_url(ip_address):
            QMessageBox.critical(self, "Invalid IP", f"The entered address '{ip_address}' is not a valid IP or URL.")
            return

        # Use OpenCV to trigger DroidCam stream
        cap = cv2.VideoCapture(ip_address)
        if not cap.isOpened():
            QMessageBox.critical(self, "Connection Failed", f"Could not connect to DroidCam feed at {ip_address}")
            cap.release()
            return
        cap.release()

        QMessageBox.information(self, "IP Camera Connected", f"Successfully connected to {ip_address}")

        self.stop_all_cameras()
        self.preview_stack.setCurrentIndex(1)  # Show blank screen
        self.ip_camera_url = ip_address

    def is_valid_ip_or_url(self, text):
        ip_regex = r'^((http|https|rtsp)://)?(\d{1,3}\.){3}\d{1,3}(:\d+)?(/.*)?$'
        url_regex = r'^((http|https|rtsp)://)?[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,6}(:\d+)?(/.*)?$'
        return re.match(ip_regex, text) or re.match(url_regex, text)

    def stop_all_cameras(self):
        if self.camera:
            self.camera.stop()
            self.camera.setViewfinder(None)
            self.camera.deleteLater()
            self.camera = None

    def start_detection(self):
        device = self.device_combo.currentText()
        camera_text = self.camera_combo.currentText().strip()
        selected_camera_info = self.camera_combo.currentData()
        output_file = self.output_line.text() or None
        url = self.url_line.text()
        verbose = self.verbose_check.isChecked()

        if not url:
            QMessageBox.critical(self, "Missing URL", "Please enter the Race Timing Website URL.")
            return

        self.stop_all_cameras()

        if selected_camera_info:
            # Selected a physical camera
            input_source = self.available_cameras.index(selected_camera_info)
        else:
            # Using IP camera URL
            input_source = self.ip_camera_url

        token = self.token_line.text() or None
        api = website_api.WebsiteAPI(url, token)
        detector = BibDetector("best.pt", device)
        tracker = BibTracker(api)
        processor = VideoProcessor(detector, tracker, input_source, output_file, verbose)

        self.hide()
        threading.Thread(target=lambda: self.run_processor(processor), daemon=True).start()

    def run_processor(self, processor):
        processor.run()
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BibDetectorApp()
    window.show()
    sys.exit(app.exec_())
