#!/usr/bin/env python
from PyQt6 import QtWidgets, uic, QtCore
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
from pathlib import Path


import sys

from lib.Connector import Connector
from lib.scene_dict import SCENES

DEVICE_NAMES = {
    "192.168.2.22": "ledstripe",
    "192.168.2.23": "candle1",
    "192.168.2.24": "candle2",
}

BASE_DIR = Path(__file__).resolve().parent

SCENE_DICT = {name: number for number, name in SCENES.items()}
SCENE_ID_TO_NAME = {number: name for name, number in SCENE_DICT.items()}


class DeviceScannerThread(QtCore.QThread):
    scan_finished = QtCore.pyqtSignal()

    def __init__(self, connector):
        super().__init__()
        self.connector = connector

    def run(self):
        self.connector.scan_for_devices()
        self.scan_finished.emit()


class LoadingDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Loading")
        self.setModal(True)
        self.setFixedSize(300, 100)

        layout = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel("Loading lamps, please wait...")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        self.setLayout(layout)


class MainApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        uic.loadUi(BASE_DIR / "resources" / "gui" / "main_window.ui", self)

        # Use a dictionary to store lamp widgets, keyed by device IP
        self.lamp_widgets = {}
        self.layout_container = self.findChild(QtWidgets.QVBoxLayout, "mainLayout")

        if self.layout_container is None:
            raise RuntimeError("Layout 'main_stuff' not found in main_window.ui")

        # Initial load might not be necessary if _load_widget_ui handles it
        # self.load_lamp_widgets(self.layout_container, count=3)
        self._load_ui()

        self.connector = Connector()
        self.show_loading_and_scan()

        # _load_widget_ui will be called after scan, so no need here initially
        # self._load_widget_ui()

    def _load_ui(self):
        self.rescan_button = self.findChild(QtWidgets.QPushButton, "rescan_btn")
        if self.rescan_button:
            self.rescan_button.clicked.connect(self.show_loading_and_scan)
        else:
            print("Warning: 'rescan_button' not found in main_window.ui")

        self.dev_stats_label = self.findChild(QtWidgets.QLabel, "dev_status_label")

    def _load_widget_ui(self):
        def setup_rgb_controls(lamp_widget, device):
            r_input = lamp_widget.findChild(QtWidgets.QLineEdit, "lineEditR")
            g_input = lamp_widget.findChild(QtWidgets.QLineEdit, "lineEditG")
            b_input = lamp_widget.findChild(QtWidgets.QLineEdit, "lineEditB")
            rgb_set_btn = lamp_widget.findChild(QtWidgets.QPushButton, "btnSetRGB")

            if not all([r_input, g_input, b_input, rgb_set_btn]):
                return

            def apply_rgb_style():
                try:
                    r = int(r_input.text())
                    g = int(g_input.text())
                    b = int(b_input.text())
                except ValueError:
                    return

                r, g, b = max(0, min(r, 255)), max(0, min(g, 255)), max(0, min(b, 255))
                luminance = 0.299 * r + 0.587 * g + 0.114 * b
                text_color = "black" if luminance > 186 else "white"
                rgb_set_btn.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); color: {text_color};")


            apply_rgb_style()

            r_input.textChanged.connect(apply_rgb_style)
            g_input.textChanged.connect(apply_rgb_style)
            b_input.textChanged.connect(apply_rgb_style)

            # Disconnect previous signals to prevent multiple connections on update
            try:
                rgb_set_btn.clicked.disconnect()
            except TypeError:
                pass # No existing connection

            rgb_set_btn.clicked.connect(lambda: self.connector.rgb_color_light(device.ip, int(r_input.text()), int(g_input.text()), int(b_input.text())))

        # Keep track of devices found in the current scan
        current_scan_ips = {device.ip for device in self.connector.devices if device}

        # Remove widgets for devices no longer found
        ips_to_remove = [ip for ip in self.lamp_widgets if ip not in current_scan_ips]
        for ip in ips_to_remove:
            widget = self.lamp_widgets.pop(ip)
            self.layout_container.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()

        for device in self.connector.devices:
            if not device:
                continue

            lamp_widget = self.lamp_widgets.get(device.ip)

            if lamp_widget is None:
                # Device not in GUI, create new widget
                lamp_widget = uic.loadUi(BASE_DIR / "resources" / "gui" / "light_widget.ui")
                self.layout_container.addWidget(lamp_widget)
                self.lamp_widgets[device.ip] = lamp_widget

            # Update existing widget properties
            status_label = lamp_widget.findChild(QtWidgets.QLabel, "labelStatus")
            brightness_label = lamp_widget.findChild(QtWidgets.QLabel, "labelBrightness")
            if status_label and brightness_label:
                device_name = DEVICE_NAMES.get(device.ip, "Unknown host")
                status_label.setText(f"{device_name} {'ON' if device.state else 'OFF'}")
                brightness_label.setText(f"Brightness [{device.dimming}%]")

            slider = lamp_widget.findChild(QtWidgets.QSlider, "sliderBrightness")
            if slider:
                slider.setMinimum(10)
                slider.setMaximum(100)
                slider.setValue(device.dimming or 0)
                # Disconnect previous signals to prevent multiple connections on update
                try:
                    slider.valueChanged.disconnect()
                except TypeError:
                    pass
                slider.valueChanged.connect(
                    lambda value, ip=device.ip, label=brightness_label:
                        (label.setText(f"Brightness [{value}%]"), self.connector.dimm_light(ip, value))
                )

            comboBoxScenes = lamp_widget.findChild(QtWidgets.QComboBox, "comboBoxScenes")
            if comboBoxScenes is not None:
                # Only clear and re-populate if it's a new widget or scenes changed
                if comboBoxScenes.count() == 0: # Check if empty, assumes scenes are static
                    comboBoxScenes.clear()
                    comboBoxScenes.setView(QtWidgets.QListView())
                    for scene_name in SCENE_DICT.keys():
                        comboBoxScenes.addItem(scene_name)

                scene_name = SCENE_ID_TO_NAME.get(device.sceneId, None)
                if scene_name:
                    index = comboBoxScenes.findText(scene_name)
                    if index != -1:
                        comboBoxScenes.setCurrentIndex(index)
                else:
                    comboBoxScenes.setCurrentIndex(0) # Default to first item if no scene found

                # Disconnect previous signals
                try:
                    comboBoxScenes.currentIndexChanged.disconnect()
                except TypeError:
                    pass

                # Reconnect signal if needed (though btnSetScene handles the action)

            label_scene = lamp_widget.findChild(QtWidgets.QLabel, "labelScene")
            if label_scene:
                scene_name = SCENE_ID_TO_NAME.get(device.sceneId, "Unknown")
                label_scene.setText(f"Light Mode [{scene_name}]")

            btnSetScene = lamp_widget.findChild(QtWidgets.QPushButton, "btnSetScene")
            if btnSetScene and comboBoxScenes:
                # Disconnect previous signals
                try:
                    btnSetScene.clicked.disconnect()
                except TypeError:
                    pass
                btnSetScene.clicked.connect(lambda _, ip=device.ip, combo=comboBoxScenes, label=label_scene: (
                    self.connector.change_scene(device=ip, scene=combo.currentText()),
                    label.setText(f"Light Mode [{combo.currentText()}]")
                ))

            btn_on = lamp_widget.findChild(QtWidgets.QPushButton, "btnTurnOn")
            btn_off = lamp_widget.findChild(QtWidgets.QPushButton, "btnTurnOff")

            if btn_on:
                # Disconnect previous signals
                try:
                    btn_on.clicked.disconnect()
                except TypeError:
                    pass
                btn_on.clicked.connect(lambda _, ip=device.ip, status=status_label: (
                    self.connector.turn_on_light(ip),
                    status.setText(f"{DEVICE_NAMES.get(ip, 'Unknown host')} ON")
                ))
            if btn_off:
                # Disconnect previous signals
                try:
                    btn_off.clicked.disconnect()
                except TypeError:
                    pass
                btn_off.clicked.connect(lambda _, ip=device.ip, status=status_label: (
                    self.connector.turn_off_light(ip),
                    status.setText(f"{DEVICE_NAMES.get(ip, 'Unknown host')} OFF")
                ))

            setup_rgb_controls(lamp_widget, device)


    def load_lamp_widgets(self, layout, count=3):
        # This method can be removed or adapted if _load_widget_ui handles initial population
        # For persistence, we ideally don't pre-load empty widgets.
        pass


    def show_loading_and_scan(self):
        self.setEnabled(False)
        self.loading_dialog = LoadingDialog(self)
        self.loading_dialog.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.loading_dialog.setWindowFlags(self.loading_dialog.windowFlags() | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self.loading_dialog.show()
        self.loading_dialog.repaint()

        self_center = self.geometry().center()
        dialog_geom = self.loading_dialog.frameGeometry()
        dialog_geom.moveCenter(self_center)
        self.loading_dialog.move(dialog_geom.topLeft())

        self.scanner_thread = DeviceScannerThread(self.connector)
        self.scanner_thread.scan_finished.connect(self.on_scan_complete)
        self.scanner_thread.start()

    def on_scan_complete(self):
        self.loading_dialog.close()
        self.setEnabled(True)
        self.loading_dialog = None
        self.scanner_thread = None
        self.dev_stats_label.setText(f"Found {len(self.connector.devices)} Devices")
        self._load_widget_ui()


    def closeEvent(self, event):
        if hasattr(self, 'scanner_thread') and self.scanner_thread is not None:
            self.scanner_thread.quit()
            self.scanner_thread.wait()
        event.accept()


if __name__ == "__main__":
    import traceback
    try:
        app = QtWidgets.QApplication(sys.argv)
        window = MainApp()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print("An error occurred:")
        traceback.print_exc()