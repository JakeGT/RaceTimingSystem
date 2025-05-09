import sys
import threading
import torch
import re
import cv2
from PyQt5.QtCore import Qt, QRect, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QFileDialog, QComboBox, QCheckBox, QVBoxLayout, QHBoxLayout, QMessageBox,
    QStackedLayout, QInputDialog, QGroupBox
)
from PyQt5.QtMultimedia import QCameraInfo, QCamera
from PyQt5.QtMultimediaWidgets import QCameraViewfinder
from PyQt5.QtGui import QPainter, QPen, QColor
from bib_detector import BibDetector, BibTracker, VideoProcessor
import website_api
from bib_csv import BibCSV


class BibInsetSelector(QWidget):
    locationSelected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 120)
        self.selected = "top-left"

    def mousePressEvent(self, event):
        x, y = event.x(), event.y()
        w, h = self.width() // 2, self.height() // 2

        if x < w and y < h:
            self.selected = "top-left"
        elif x >= w and y < h:
            self.selected = "top-right"
        elif x < w and y >= h:
            self.selected = "bottom-left"
        else:
            self.selected = "bottom-right"

        self.locationSelected.emit(self.selected)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(Qt.black, 2))

        # 4 rectangles
        rects = {
            "top-left": QRect(0, 0, 60, 60),
            "top-right": QRect(60, 0, 60, 60),
            "bottom-left": QRect(0, 60, 60, 60),
            "bottom-right": QRect(60, 60, 60, 60),
        }

        for key, rect in rects.items():
            if key == self.selected:
                painter.setBrush(QColor(0, 150, 255, 100))  # highlight selected
            else:
                painter.setBrush(QColor(200, 200, 200, 50))
            painter.drawRect(rect)


class CropWindow(QWidget):
    def __init__(self, pixmap, parent_app):
        super().__init__()
        self.setWindowTitle("Select Crop Area")
        self.parent_app = parent_app
        self.pixmap = pixmap
        self.start_pos = None
        self.end_pos = None
        self.is_selecting = False
        self.is_paused = False
        self.setFixedSize(pixmap.size())
        self.setMouseTracking(True)

        # Button Layout (bottom-right corner)
        self.confirm_button = QPushButton("Confirm", self)
        self.confirm_button.clicked.connect(self.confirm_crop)

        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.close)

        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.confirm_button)
        self.button_layout.addWidget(self.cancel_button)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.addStretch()
        self.main_layout.addLayout(self.button_layout)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self.is_paused:
                # Start or continue drawing
                self.start_pos = event.pos()
                self.end_pos = self.start_pos
                self.is_selecting = True
                self.update()
            else:
                # If paused and clicked again, reset selection
                self.start_pos = None
                self.end_pos = None
                self.is_paused = False
                self.update()

    def mouseMoveEvent(self, event):
        if self.is_selecting and not self.is_paused:
            self.end_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.is_selecting and not self.is_paused:
            self.end_pos = event.pos()
            self.is_selecting = False
            self.is_paused = True  # Freeze the box after releasing
            self.update()

    def confirm_crop(self):
        if self.start_pos and self.end_pos and self.is_paused:
            rect = QRect(self.start_pos, self.end_pos).normalized()
            x1, y1, x2, y2 = rect.left(), rect.top(), rect.right(), rect.bottom()
            self.parent_app.x1_line.setText(str(x1))
            self.parent_app.y1_line.setText(str(y1))
            self.parent_app.x2_line.setText(str(x2))
            self.parent_app.y2_line.setText(str(y2))
            self.close()

    def paintEvent(self, event):
        painter = QPainter(self)

        # Draw the snapshot
        painter.drawPixmap(0, 0, self.pixmap)

        if self.start_pos and self.end_pos:
            rect = QRect(self.start_pos, self.end_pos).normalized()

            # Dim outside
            painter.setBrush(QColor(0, 0, 0, 100))
            painter.setPen(Qt.NoPen)

            # Top
            painter.drawRect(0, 0, self.width(), rect.top())
            # Bottom
            painter.drawRect(0, rect.bottom(), self.width(), self.height() - rect.bottom())
            # Left
            painter.drawRect(0, rect.top(), rect.left(), rect.height())
            # Right
            painter.drawRect(rect.right(), rect.top(), self.width() - rect.right(), rect.height())

            # Draw transparent red crop area
            painter.setBrush(QColor(255, 0, 0, 50))
            painter.setPen(QPen(Qt.red, 2, Qt.DashLine))
            painter.drawRect(rect)


class BibDetectorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("MainWindow")
        self.crop_window = None
        self.available_cameras = None
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

        self.results_label = QLabel("Results Folder:")
        self.results_line = QLineEdit()
        self.results_browse = QPushButton("Browse")
        self.results_browse.clicked.connect(self.browse_results_folder)

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
        self.preview_stack.addWidget(self.blank_label)  # index 1
        self.preview_widget.setLayout(self.preview_stack)

        self.populate_camera_inputs()

        self.x1_line = QLineEdit()
        self.y1_line = QLineEdit()
        self.x2_line = QLineEdit()
        self.y2_line = QLineEdit()
        self.x1_line.setPlaceholderText("X1")
        self.y1_line.setPlaceholderText("Y1")
        self.x2_line.setPlaceholderText("X2")
        self.y2_line.setPlaceholderText("Y2")

        self.select_crop_button = QPushButton("Select Crop")
        self.select_crop_button.clicked.connect(self.open_crop_window)

        self.inset_selector = BibInsetSelector()
        self.inset_selector.locationSelected.connect(self.set_bib_inset_location)
        self.bib_inset_location = "top-left"

        self.layout = QVBoxLayout()
        self.add_widgets()
        self.setLayout(self.layout)

    from PyQt5.QtWidgets import QGroupBox

    def add_widgets(self):
        # Group 1: Device & Camera
        device_camera_group = QGroupBox("Hardware Settings")
        device_camera_layout = QVBoxLayout()
        device_camera_layout.addLayout(self.row(self.device_label, self.device_combo))
        device_camera_layout.addLayout(
            self.row(self.camera_label, self.camera_combo, self.refresh_button, self.connect_ip_button))
        device_camera_group.setLayout(device_camera_layout)

        # Group 2: Output & API
        output_api_group = QGroupBox("Output Settings")
        output_api_layout = QVBoxLayout()
        output_api_layout.addLayout(self.row(self.output_label, self.output_line, self.output_browse))
        output_api_layout.addLayout(self.row(self.results_label, self.results_line, self.results_browse))
        output_api_layout.addLayout(self.row(self.url_label, self.url_line))
        output_api_layout.addLayout(self.row(self.token_label, self.token_line))
        output_api_layout.addWidget(self.load_config_button)
        output_api_group.setLayout(output_api_layout)

        # Group 3: Crop Settings
        crop_group = QGroupBox("Crop Area Selection")
        crop_layout = QVBoxLayout()
        crop_layout.addWidget(self.select_crop_button)
        crop_layout.addLayout(self.row(self.x1_line, QLabel("Y1:"), self.y1_line))
        crop_layout.addLayout(self.row(self.x2_line, QLabel("Y2:"), self.y2_line))
        crop_group.setLayout(crop_layout)

        # Group 4: Bib Inset Settings
        inset_group = QGroupBox("Bib Overlay Position")
        inset_layout = QVBoxLayout()
        inset_layout.addWidget(self.inset_selector)
        inset_group.setLayout(inset_layout)

        # Assemble the main layout
        self.layout.addWidget(device_camera_group)
        self.layout.addWidget(output_api_group)
        self.layout.addWidget(crop_group)
        self.layout.addWidget(inset_group)
        self.layout.addWidget(self.verbose_check)
        self.layout.addWidget(self.preview_label)
        self.layout.addWidget(self.preview_widget)
        self.layout.addWidget(self.start_button)

        # Set margins and spacing
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(12)

    def row(self, *widgets):
        h = QHBoxLayout()
        for w in widgets:
            h.addWidget(w)
        return h

    def populate_device_list(self):
        self.device_combo.clear()
        default_device = "cpu"
        self.device_combo.addItem("cpu")
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                self.device_combo.addItem(f"cuda:{i}")
            default_device = "cude:0"
        if torch.backends.mps.is_available():
            self.device_combo.addItem("mps")
            default_device = "mps"
        else:
            if not torch.backends.mps.is_built():
                print("MPS not available because the current PyTorch install was not "
                      "built with MPS enabled.")
            else:
                print("MPS not available because the current MacOS version is not 12.3+ "
                      "and/or you do not have an MPS-enabled device on this machine.")

        index = self.device_combo.findText(default_device)
        if index >= 0:
            self.device_combo.setCurrentIndex(index)

    def populate_camera_inputs(self):
        self.camera_combo.clear()
        self.available_cameras = QCameraInfo.availableCameras()
        for cam in self.available_cameras:
            self.camera_combo.addItem(cam.description(), cam)

        if self.camera_combo.count() > 0:
            self.change_camera_preview()

    def set_bib_inset_location(self, location):
        self.bib_inset_location = location

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

    def open_crop_window(self):
        if self.viewfinder:
            # Take a snapshot of the viewfinder
            pixmap = self.viewfinder.grab()
            if pixmap.isNull():
                QMessageBox.warning(self, "Error", "Failed to capture snapshot.")
                return

            self.crop_window = CropWindow(pixmap, self)
            self.crop_window.show()
        else:
            QMessageBox.warning(self, "Error", "No camera preview available.")

    def browse_output(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Select Output File", filter="MP4 files (*.mp4)")
        if filename:
            self.output_line.setText(filename)

    def browse_results_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Results Folder")
        if folder:
            self.results_line.setText(folder)

    def change_camera_preview(self):
        camera_info = self.camera_combo.currentData()
        if camera_info:
            self.stop_all_cameras()

            self.preview_stack.setCurrentIndex(0)  # Show viewfinder
            self.blank_label.setText("")  # Clear any IP camera message

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
        self.blank_label.setText("Using IP Camera Stream\n(Preview not available)")
        self.blank_label.setStyleSheet("color: white; font-size: 18px;")
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
        input_index = self.available_cameras.index(
            selected_camera_info) if selected_camera_info in self.available_cameras else 0
        output_file = self.output_line.text() or None
        results_folder = self.results_line.text() or None
        url = self.url_line.text()
        verbose = self.verbose_check.isChecked()

        try:
            x1 = int(self.x1_line.text())
            y1 = int(self.y1_line.text())
            x2 = int(self.x2_line.text())
            y2 = int(self.y2_line.text())
            crop_coords = (x1, y1, x2, y2)
            if x2 <= x1 or y2 <= y1:
                QMessageBox.critical(self, "Invalid Coordinates",
                                     f"Invalid crop coordinates: ({x1}, {y1}), ({x2}, {y2}) — x2/y2 must be greater than x1/y1")
                return
        except ValueError:
            crop_coords = None  # If fields are empty or invalid

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

        if results_folder:
            bib_csv = BibCSV(results_folder)
        else:
            bib_csv = None

        token = self.token_line.text() or None
        api = website_api.WebsiteAPI(url, token)
        detector = BibDetector("best.pt", device)
        tracker = BibTracker(api, bib_inset_location=self.bib_inset_location, bib_csv=bib_csv)
        processor = VideoProcessor(detector, tracker, input_source, output_file, verbose)

        self.hide()
        threading.Thread(target=lambda: self.run_processor(processor), daemon=True).start()

    def run_processor(self, processor):
        processor.run()
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Load external stylesheet
    try:
        with open("style.qss", "r") as f:
            app.setStyleSheet(f.read())
    except Exception as e:
        print(f"Failed to load stylesheet: {e}")

    window = BibDetectorApp()
    window.show()
    sys.exit(app.exec_())
