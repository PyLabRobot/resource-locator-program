import json
import os
import threading
import textwrap
import traceback

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
  QFileDialog,
  QLabel,
  QPushButton,
  QVBoxLayout,
  QWidget,
)

from pylabrobot.liquid_handling import LiquidHandler

from resource_locator_program.shared_widgets import show_error_alert


class LoadWidget(QWidget):
  setup_finished_signal = pyqtSignal(object)

  def __init__(self, parent=None, callback=None):
    super().__init__(parent=parent)
    self.general_layout = QVBoxLayout()
    self.setLayout(self.general_layout)

    self.load_layout = QVBoxLayout()

    self.load_layout.addWidget(QLabel("Generate a layout.json file with the following code:"))
    self.instruction_code = QLabel(textwrap.dedent("""
    lh.deck.assign_child_resource(unknown_resource, location=None)
    lh.save("layout.json")
    """))
    self.instruction_code.setFont(QFont("Courier New"))
    self.instruction_code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    self.instruction_code.setWordWrap(True)
    self.load_layout.addWidget(self.instruction_code)

    self.file_picker = FilePickerWidget(callback=self._file_picked_callback)
    self.load_layout.addWidget(self.file_picker)

    self.general_layout.addLayout(self.load_layout)

    self.callback = callback

    # add a setup button that's hidden initially
    self.setup_layout = QVBoxLayout()

    self.file_label = QLabel("File: ")
    self.file_label.sizePolicy().setRetainSizeWhenHidden(True)
    self.file_label.hide()
    self.setup_layout.addWidget(self.file_label)
    self.backend_label = QLabel("Backend: ")
    self.backend_label.sizePolicy().setRetainSizeWhenHidden(True)
    self.backend_label.hide()
    self.setup_layout.addWidget(self.backend_label)
    self.deck_label = QLabel("Deck: ")
    self.deck_label.sizePolicy().setRetainSizeWhenHidden(True)
    self.deck_label.hide()
    self.setup_layout.addWidget(self.deck_label)

    self.setup_button = QPushButton("Setup")
    self.setup_button.clicked.connect(self._setup)
    # retain the original size
    self.setup_button.sizePolicy().setRetainSizeWhenHidden(True)
    self.setup_button.hide()
    self.setup_layout.addWidget(self.setup_button)

    self.general_layout.addLayout(self.setup_layout)

    self.setup_finished_signal.connect(self._setup_finished_callback)

    # Should be a spinner, but qt has none and it's hard to find a good one online (so much trash)
    self.loading_label = QLabel("Setting up robot...")
    self.loading_label.hide()
    self.general_layout.addWidget(self.loading_label)

    self.lh = None

  def _setup_finished_callback(self, a):
    success, e = a
    if success:
      self.callback(self.lh)
    else:
      self.loading_label.hide()
      self.setup_button.show()
      self.file_picker.setEnabled(True)
      show_error_alert(
        title="Setup failed.",
        description=str(e),
        details=traceback.format_exc())

  def _file_picked_callback(self, fname):
    with open(fname, "r", encoding="utf-8") as f:
      try:
        data = json.load(f)
      except Exception as e:
        print(traceback.format_exc())

        show_error_alert(
          title="An error occurred while loading the file.",
          description=str(e),
          details=traceback.format_exc())

        return

    try:
      self.lh = LiquidHandler.deserialize(data)
    except Exception as e:
      print(traceback.format_exc())
      show_error_alert(
        title="An error occurred while loading the file.",
        description=str(e),
        details=traceback.format_exc())
      return

    self.file_label.setText(f"File: {fname}")
    self.file_label.show()
    self.backend_label.setText(f"Backend: {self.lh.backend.__class__.__name__}")
    self.backend_label.show()
    self.deck_label.setText(f"Deck: loaded {len(self.lh.deck.get_all_resources())} resources")
    self.deck_label.show()

    self.setup_button.show()

  def _setup(self):
    self.loading_label.show()
    self.setup_button.hide()
    self.file_picker.setEnabled(False)

    def setup():
      try:
        self.lh.setup()
      except Exception as e:
        print(traceback.format_exc())

        self.setup_finished_signal.emit((False, e))
      else:
        self.setup_finished_signal.emit((True, None))

    self.setup_thread = threading.Thread(target=setup, daemon=True)
    self.setup_thread.start()


class FilePickerWidget(QWidget):
  def __init__(self, parent=None, callback=None):
    super().__init__(parent)

    self.general_layout = QVBoxLayout()
    self.setLayout(self.general_layout)

    # TODO: make this a parameter
    self.general_layout.addWidget(QLabel("Select a PyLabRobot layout file:"))
    self.file_picker = QPushButton("Select file")
    self.file_picker.clicked.connect(self.show_dialog)
    self.general_layout.addWidget(self.file_picker)

    self.set_file_picked_callback(callback)

  def set_file_picked_callback(self, callback):
    self.file_picked_callback = callback

  def show_dialog(self):
    home_dir = os.path.expanduser("~")
    fname = QFileDialog.getOpenFileName(self, "Open file", home_dir, filter="*.json")

    if fname[0]:
      if self.file_picked_callback is not None:
        self.file_picked_callback(fname[0])

