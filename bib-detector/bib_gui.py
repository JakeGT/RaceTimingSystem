import sys
import threading
import torch
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QFileDialog, QComboBox, QCheckBox, QVBoxLayout, QHBoxLayout, QMessageBox
)
from PyQt5.QtMultimedia import QCameraInfo, QCamera
from PyQt5.QtMultimediaWidgets import QCameraViewfinder
from PyQt5.QtGui import QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QRect
from bib_detector import BibDetector, BibTracker, VideoProcessor
import website_api

class CropWindow(QWidget):
    def __init__(self, pixmap, parent_app):
        super().__init__()
        self.setWindowTitle("Select Crop Area")
        self.parent_app = parent_app
        self.pixmap = pixmap
        self.start_pos = None
        self.end_pos = None
        self.is_selecting = False  # New: whether currently selecting
        self.is_paused = False     # New: whether box is frozen
        self.setFixedSize(pixmap.size())
        self.setMouseTracking(True)

        # Confirm and Cancel buttons
        self.confirm_button = QPushButton("Confirm", self)
        self.confirm_button.move(10, 10)
        self.confirm_button.clicked.connect(self.confirm_crop)

        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.move(110, 10)
        self.cancel_button.clicked.connect(self.close)

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
        self.camera = None
        self.setWindowTitle("Bib Detector GUI")

        self.device_label = QLabel("Device:")
        self.device_combo = QComboBox()
        self.populate_device_list()

        self.camera_label = QLabel("Camera Input:")
        self.camera_combo = QComboBox()
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
        self.viewfinder = QCameraViewfinder()
        self.viewfinder.setFixedSize(640, 360)
        self.populate_camera_inputs()

        self.x1_line = QLineEdit()
        self.y1_line = QLineEdit()
        self.x2_line = QLineEdit()
        self.y2_line = QLineEdit()

        self.select_crop_button = QPushButton("Select Crop")
        self.select_crop_button.clicked.connect(self.open_crop_window)

        self.layout = QVBoxLayout()
        self.add_widgets()
        self.setLayout(self.layout)

    def add_widgets(self):
        self.layout.addLayout(self.row(self.device_label, self.device_combo))
        self.layout.addLayout(self.row(self.camera_label, self.camera_combo, self.refresh_button))
        self.layout.addLayout(self.row(self.output_label, self.output_line, self.output_browse))
        self.layout.addLayout(self.row(self.url_label, self.url_line))
        self.layout.addWidget(self.verbose_check)
        self.layout.addWidget(self.preview_label)
        self.layout.addWidget(self.viewfinder)
        self.layout.addWidget(self.select_crop_button)
        self.layout.addLayout(self.row(QLabel("Crop X1:"), self.x1_line, QLabel("Y1:"), self.y1_line))
        self.layout.addLayout(self.row(QLabel("Crop X2:"), self.x2_line, QLabel("Y2:"), self.y2_line))
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

    def change_camera_preview(self):
        if self.camera:
            self.camera.stop()
            self.camera.setViewfinder(None)
            self.camera.deleteLater()

        selected_camera_info = self.camera_combo.currentData()
        if selected_camera_info:
            self.camera = QCamera(selected_camera_info)
            self.camera.setViewfinder(self.viewfinder)
            self.camera.start()

    def start_detection(self):
        device = self.device_combo.currentText()
        selected_camera_info = self.camera_combo.currentData()
        input_index = self.available_cameras.index(selected_camera_info) if selected_camera_info in self.available_cameras else 0
        output_file = self.output_line.text() or None
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

        if self.camera:
            self.camera.stop()
            self.camera.setViewfinder(None)
            self.camera.deleteLater()
            self.camera = None

        api = website_api.WebsiteAPI(url)
        detector = BibDetector("best.pt", device)
        tracker = BibTracker(api)
        processor = VideoProcessor(detector, tracker, input_index, output_file, verbose, crop_coords)

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
