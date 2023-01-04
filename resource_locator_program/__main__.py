from functools import partial
import json
import logging
import os
import textwrap
import threading
import traceback
import sys

from PyQt6 import QtWidgets
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QFont
from PyQt6.QtWidgets import (
  QApplication,
  QButtonGroup,
  QFileDialog,
  QGridLayout,
  QGroupBox,
  QHBoxLayout,
  QLabel,
  QLineEdit,
  QMainWindow,
  QMessageBox,
  QPushButton,
  QRadioButton,
  QVBoxLayout,
  QWidget,
)

from pylabrobot.liquid_handling import LiquidHandler
from pylabrobot.resources import TipRack, Plate, Coordinate

logging.getLogger("pylabrobot").setLevel(logging.DEBUG)


BUTTON_SIZE = 50

lh = None # TODO: probably make this a controller object


def get_asset(name):
  return os.path.join(os.path.dirname(__file__), "assets", name)


def get_unlocated_resources():
  return [resource for resource in lh.deck.get_all_resources() if resource.location is None]


class Window(QMainWindow):
  def __init__(self):
    super().__init__()
    self.setWindowTitle("Resource Locator Program")
    self.setMinimumSize(QSize(500, 800))
    self.general_layout = QVBoxLayout()
    centralWidget = QWidget(self)

    centralWidget.setLayout(self.general_layout)

    self.setCentralWidget(centralWidget)

    self.load_widget = LoadWidget(self, callback=self._load_locator)
    self.general_layout.addWidget(self.load_widget)

    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Warning)
    msg.setText("Warning: collision risk")
    msg.setInformativeText("This tool does not check for collisions and can damage your hardware. "
      "You are responsible for checking for collisions.")
    msg.setWindowTitle("Collision risk")
    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
    # TODO: add don't show again checkbox
    # msg.setCheckBox(QMessageBox.CheckBox("Don't show again"))
    result = msg.exec()

    self.location_editor = LocationEditorWidget(parent=self)
    self.location_editor.hide()
    self.general_layout.addWidget(self.location_editor)

  def _load_locator(self):
    self.load_widget.hide()
    self.location_editor.show()
    self.location_editor.start()

  def keyPressEvent(self, event):
    # TODO: find a good pattern for this.
    self.location_editor.keyPressEvent(event)

  def keyReleaseEvent(self, event):
    # TODO: find a good pattern for this.
    self.location_editor.keyReleaseEvent(event)


def show_error_alert(title, description=None, details=None):
  msg = QMessageBox()
  msg.setIcon(QMessageBox.Icon.Critical)
  msg.setText(title)
  if description is not None:
    msg.setInformativeText(description)
  msg.setWindowTitle("Error loading file")
  if details is not None:
    msg.setDetailedText(details)
  msg.setStandardButtons(QMessageBox.StandardButton.Ok)
  msg.exec()


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

  def _setup_finished_callback(self, a):
    success, e = a
    if success:
      self.callback()
    else:
      self.loading_label.hide()
      self.setup_button.show()
      show_error_alert(
        title="Setup failed.",
        description=str(e),
        details=traceback.format_exc())

  def _file_picked_callback(self, fname):
    global lh

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
      lh = LiquidHandler.deserialize(data)
    except Exception as e:
      print(traceback.format_exc())
      show_error_alert(
        title="An error occurred while loading the file.",
        description=str(e),
        details=traceback.format_exc())
      return

    if len([x for x in lh.deck.get_all_resources() if isinstance(x, TipRack)]) == 0:
      show_error_alert(
        title="The file does not contain any tip racks.",
        description="Layouts must contain at least one tip rack for teaching.")
      return

    self.file_label.setText(f"File: {fname}")
    self.file_label.show()
    self.backend_label.setText(f"Backend: {lh.backend.__class__.__name__}")
    self.backend_label.show()
    self.deck_label.setText(f"Deck: loaded {len(lh.deck.get_all_resources())} resources")
    self.deck_label.show()

    self.setup_button.show()

  def _setup(self):
    self.loading_label.show()
    self.setup_button.hide()

    def setup():
      try:
        lh.setup()
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


class TipRacksWidget(QWidget):
  def __init__(self, set_x, set_y, set_z, parent=None,
    tip_pickup_callback=None, tip_drop_callback=None):
    super().__init__(parent=parent)

    self.general_layout = QVBoxLayout()
    self.setLayout(self.general_layout)

    self.tip_pickup_callback = tip_pickup_callback
    self.tip_drop_callback = tip_drop_callback

    self.tip_racks_box = QGroupBox("Tip racks")
    self.tip_racks_box_layout = QVBoxLayout()

    self.tip_racks = {}
    self.buttons = []

    self.set_x = set_x
    self.set_y = set_y
    self.set_z = set_z

    self.tip_racks_box_layout.addStretch(1)
    self.tip_racks_box.setLayout(self.tip_racks_box_layout)
    self.general_layout.addWidget(self.tip_racks_box)

  def pick_up_tip_a1(self, button, tip_rack):
    for b in self.buttons:
      b.setEnabled(False)

    try:
      tip_spot = tip_rack.get_item("A1")
      tip = tip_spot.get_tip()
      lh.pick_up_tips([tip_spot], use_channels=[7])
    except Exception as e:
      print(traceback.format_exc())
      show_error_alert(
        title="An error occurred while picking up tip.",
        description=str(e),
        details=traceback.format_exc())

      for b in self.buttons:
        b.setEnabled(True)
    else:
      loc = tip_spot.get_absolute_location() + tip_spot.center()
      self.set_x(round(loc.x, 1))
      self.set_y(round(loc.y, 1))
      self.set_z(round(loc.z + tip.total_tip_length + 10, 1))

      button.setText("Drop tip to A1")
      button.setEnabled(True)

      self.tip_racks[tip_rack.name] = True

      if self.tip_pickup_callback is not None:
        self.tip_pickup_callback()

  def drop_tip_a1(self, button, tip_rack):
    try:
      tip_spot = tip_rack.get_item("A1")
      lh.drop_tips([tip_spot], use_channels=[7])
    except Exception as e:
      print(traceback.format_exc())
      show_error_alert(
        title="An error occurred while dropping tip.",
        description=str(e),
        details=traceback.format_exc())

      button.setEnabled(True)
    else:
      loc = tip_spot.get_absolute_location() + tip_spot.center()
      self.set_x(round(loc.x, 1))
      self.set_y(round(loc.y, 1))
      self.set_z(round(loc.z + tip_spot.get_tip().total_tip_length + 10, 1))

      button.setText("Pick up tip A1")

      for b in self.buttons:
        b.setEnabled(True)

      self.tip_racks[tip_rack.name] = False

      if self.tip_drop_callback is not None:
        self.tip_drop_callback()

  def start(self):
    for tip_rack in filter(lambda x: isinstance(x, TipRack), lh.deck.get_all_resources()):
      def make_pick_up_tip_a1(button, tip_rack): # closure
        def pick_up_tip_a1():
          has_tip = self.tip_racks.get(tip_rack.name, False)
          if has_tip:
            self.drop_tip_a1(button, tip_rack)
          else:
            self.pick_up_tip_a1(button, tip_rack)

        return pick_up_tip_a1

      row = QHBoxLayout()
      row.addWidget(QLabel(tip_rack.name))
      button = QPushButton("Pick up tip A1")
      button.clicked.connect(make_pick_up_tip_a1(button, tip_rack))
      row.addWidget(button)
      self.buttons.append(button)
      self.tip_racks_box_layout.addLayout(row)


class UnlocatedResourcesWidget(QWidget):
  def __init__(self, get_x, get_y, get_z, parent=None):
    super().__init__(parent)

    self.general_layout = QVBoxLayout()
    self.setLayout(self.general_layout)

    self.unlocated_resources_box = QGroupBox("Unlocated resources")
    self.unlocated_resources_box_layout = QVBoxLayout()

    self.unlocated_resources = {}
    self.buttons = []

    self.get_x = get_x
    self.get_y = get_y
    self.get_z = get_z

    self.unlocated_resources_box_layout.addStretch(1)
    self.unlocated_resources_box.setLayout(self.unlocated_resources_box_layout)
    self.general_layout.addWidget(self.unlocated_resources_box)

  def start(self):
    # TODO: we should handle the case where the child and parent location are unknown. In that case,
    # parent location should be identified first, which should be represented in the UI.

    for i, resource in enumerate(get_unlocated_resources()):
      def make_resource_here(i, resource): # closure
        def resource_here():
          print(f"Resource '{resource.name}' is at absolute location ({self.get_x()}, "
                f"{self.get_y()}, {self.get_z()})")

          if isinstance(resource, Plate):
            resource.location = Coordinate(self.get_x(), self.get_y(), self.get_z()) - \
              resource.get_item("A1").location - \
              resource.get_item("A1").center() - \
              resource.parent.get_absolute_location()
          else:
            resource.location = Coordinate(self.get_x(), self.get_y(), self.get_z()) - \
              Coordinate(0, 0, resource.get_size_z()) - \
              resource.parent.get_absolute_location()

          print(f"Resource '{resource.name}' is at relative location {resource.location}")

          # TODO: probably remove row, move into "known location resources" with the possibility to
          # forget location and reteach.
          self.buttons[i].setEnabled(False)

        return resource_here

      row = QHBoxLayout()
      row.addWidget(QLabel(resource.name))
      button = QPushButton("Front top left corner at tip location")
      if isinstance(resource, Plate):
        button.setText("Well A1 at tip location")
      button.clicked.connect(make_resource_here(i, resource))
      self.buttons.append(button)
      row.addWidget(button)
      self.unlocated_resources_box_layout.addLayout(row)


class LocationEditorWidget(QWidget):
  def __init__(self, parent=None):
    super().__init__(parent)

    self.general_layout = QVBoxLayout()
    self.setLayout(self.general_layout)

    self._x = 0
    self._y = 0
    self._z = 0

    self._d = 10

    self.tip_racks_widget = TipRacksWidget(
      set_x=self.set_x,
      set_y=self.set_y,
      set_z=self.set_z,
      tip_pickup_callback=self.tip_pickup_callback,
      tip_drop_callback=self.tip_drop_callback)
    self.general_layout.addWidget(self.tip_racks_widget)

    self.mover_group = QGroupBox("Locator")
    self.mover_group_layout = QVBoxLayout()
    self.mover_group.setLayout(self.mover_group_layout)

    self.pad = DirectionPadWidget(
      move_left=self.move_left,
      move_right=self.move_right,
      move_back=self.move_back,
      move_forward=self.move_forward,
      move_down=self.move_down,
      move_up=self.move_up,
      set_d_callback=self.set_d)
    self.mover_group_layout.addWidget(self.pad)

    self.display = LocationDisplay(self, callback=self.location_display_updated)
    self.display.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
    self.display.clearFocus()
    self.mover_group_layout.addWidget(self.display)

    self.general_layout.addWidget(self.mover_group)

    self.unlocated_resources_widget = UnlocatedResourcesWidget(
      get_x=self.get_x, get_y=self.get_y, get_z=self.get_z)
    self.general_layout.addWidget(self.unlocated_resources_widget)

    self.save_button = QPushButton("Save to file")
    self.save_button.clicked.connect(self.save)
    self.general_layout.addWidget(self.save_button)

    self.controller_disabled = False

  def get_x(self):
    return self._x

  def get_y(self):
    return self._y

  def get_z(self):
    return self._z

  def location_display_updated(self, x, y, z):
    move_z_first = z > self._z

    if move_z_first and self._z != z:
      self.set_z(z)

    if self._x != x:
      self.set_x(x)

    if self._y != y:
      self.set_y(y)

    if self._z != z:
      self.set_z(z)

  def start(self):
    self.set_x(350)
    self.set_y(100)
    try:
      lh.backend.prepare_for_manual_operation()
    except Exception as e:
      traceback.print_exc()
      show_error_alert(
        title="Error moving channels",
        description=str(e),
        details=traceback.format_exc())
    self.set_z(300)

    self.tip_racks_widget.start()
    self.unlocated_resources_widget.start()

    # Disable widgets until a tip is picked up.
    self.pad.setDisabled(True)
    self.display.setDisabled(True)
    self.unlocated_resources_widget.setDisabled(True)
    self.controller_disabled = True

  def save(self):
    name = QFileDialog.getSaveFileName(self, "Save file", "lh.json", filter="JSON files (*.json)")

    if name[0] == "":
      return

    lh.save(name[0])

  def tip_pickup_callback(self):
    self.pad.setDisabled(False)
    self.display.setDisabled(False)
    self.unlocated_resources_widget.setDisabled(False)
    self.controller_disabled = False

  def tip_drop_callback(self):
    self.pad.setDisabled(True)
    self.display.setDisabled(True)
    self.unlocated_resources_widget.setDisabled(True)
    self.controller_disabled = True

  def set_d(self, d):
    self._d = d

  def set_x(self, x):
    self._x = x

    try:
      lh.backend.move_channel_x(lh.backend.num_channels - 1, x)
    except Exception as e:
      traceback.print_exc()
      show_error_alert(
        title="Error while moving x axis",
        description=str(e),
        details=traceback.format_exc())
      return

    self.display.set_x(x)

  def set_y(self, y):
    self._y = y

    try:
      lh.backend.move_channel_y(lh.backend.num_channels - 1, y)
    except Exception as e:
      traceback.print_exc()
      show_error_alert(
        title="Error while moving y axis",
        description=str(e),
        details=traceback.format_exc())
      return

    self.display.set_y(y)

  def set_z(self, z):
    self._z = z

    try:
      lh.backend.move_channel_z(lh.backend.num_channels - 1, z)
    except Exception as e:
      traceback.print_exc()
      show_error_alert(
        title="Error while moving z axis",
        description=str(e),
        details=traceback.format_exc())
      return

    self.display.set_z(z)

  def move_left(self):
    self.set_x(self._x - self._d)

  def move_right(self):
    self.set_x(self._x + self._d)

  def move_back(self):
    self.set_y(self._y + self._d)

  def move_forward(self):
    self.set_y(self._y - self._d)

  def move_down(self):
    self.set_z(self._z - self._d)

  def move_up(self):
    self.set_z(self._z + self._d)

  def keyPressEvent(self, event):
    if self.controller_disabled:
      return

    if QtWidgets.QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier and \
        event.key() == Qt.Key.Key_Up:
      self.move_up()
    elif QtWidgets.QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier and \
        event.key() == Qt.Key.Key_Down:
      self.move_down()
    elif event.key() == Qt.Key.Key_Up or event.key() == Qt.Key.Key_W:
      self.pad.button_top.setDown(True)
      self.move_back()
    elif event.key() == Qt.Key.Key_Down or event.key() == Qt.Key.Key_S:
      self.pad.button_bottom.setDown(True)
      self.move_forward()
    elif event.key() == Qt.Key.Key_Left or event.key() == Qt.Key.Key_A:
      self.pad.button_left.setDown(True)
      self.move_left()
    elif event.key() == Qt.Key.Key_Right or event.key() == Qt.Key.Key_D:
      self.pad.button_right.setDown(True)
      self.move_right()

  def keyReleaseEvent(self, event):
    if self.controller_disabled:
      return

    if event.key() == Qt.Key.Key_Up or event.key() == Qt.Key.Key_W:
      self.pad.button_top.setDown(False)
    elif event.key() == Qt.Key.Key_Down or event.key() == Qt.Key.Key_S:
      self.pad.button_bottom.setDown(False)
    elif event.key() == Qt.Key.Key_Left or event.key() == Qt.Key.Key_A:
      self.pad.button_left.setDown(False)
    elif event.key() == Qt.Key.Key_Right or event.key() == Qt.Key.Key_D:
      self.pad.button_right.setDown(False)


class LocationDisplay(QWidget):
  def __init__(self, parent, callback=None):
    super().__init__(parent)

    self.general_layout = QHBoxLayout()
    self.setLayout(self.general_layout)

    self._x = 0
    self._y = 0
    self._z = 0

    def fix_float_value(elem, e):
      try:
        _ = float(elem.text())
      except ValueError:
        elem.setText(str(self._x))

    self.display_x = QLineEdit()
    self.display_x.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
    self.display_x.textChanged.connect(self.display_label_updated)
    self.display_x.focusOutEvent = partial(fix_float_value, self.display_x)
    self.general_layout.addWidget(QLabel("X:"))
    self.general_layout.addWidget(self.display_x)
    self.general_layout.addWidget(QLabel("mm"))

    self.display_y = QLineEdit()
    self.display_y.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
    self.display_y.textChanged.connect(self.display_label_updated)
    self.display_y.focusOutEvent = partial(fix_float_value, self.display_y)
    self.general_layout.addWidget(QLabel("Y:"))
    self.general_layout.addWidget(self.display_y)
    self.general_layout.addWidget(QLabel("mm"))

    self.display_z = QLineEdit()
    self.display_z.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
    self.display_z.textChanged.connect(self.display_label_updated)
    self.display_z.focusOutEvent = partial(fix_float_value, self.display_z)
    self.general_layout.addWidget(QLabel("Z:"))
    self.general_layout.addWidget(self.display_z)
    self.general_layout.addWidget(QLabel("mm"))

    self.move_button = QPushButton("Move")
    self.general_layout.addWidget(self.move_button)
    self.move_button.setDisabled(True)

    def move():
      try:
        x = float(self.display_x.text())
        self.set_x(x)
      except ValueError:
        pass

      try:
        y = float(self.display_y.text())
        self.set_y(y)
      except ValueError:
        pass

      try:
        z = float(self.display_z.text())
        self.set_z(z)
      except ValueError:
        pass

      self.location_updated_callback(x=self._x, y=self._y, z=self._z)

    self.move_button.clicked.connect(move)

    self.set_location_updated_callback(callback)

  def display_label_updated(self):
    small_value = 0.0001

    try:
      x_same = abs(float(self.display_x.text()) - self._x) < small_value
    except ValueError:
      x_same = True

    try:
      y_same = abs(float(self.display_y.text()) - self._y) < small_value
    except ValueError:
      y_same = True

    try:
      z_same = abs(float(self.display_z.text()) - self._z) < small_value
    except ValueError:
      z_same = True

    # disable move button if the entered values are the same as the current values
    self.move_button.setDisabled(x_same and y_same and z_same)

  def set_location_updated_callback(self, callback):
    self.location_updated_callback = callback

  def set_x(self, x):
    self._x = x
    self.display_x.setText(str(round(x, 1)))
    self.display_label_updated()

  def set_y(self, y):
    self._y = y
    self.display_y.setText(str(round(y, 1)))
    self.display_label_updated()

  def set_z(self, z):
    self._z = z
    self.display_z.setText(str(round(z, 1)))
    self.display_label_updated()


class DirectionPadWidget(QWidget):
  def __init__(
    self,
    move_left, move_right, move_back, move_forward, move_down, move_up, set_d_callback,
    parent=None):
    super().__init__(parent)

    self.move_left = move_left
    self.move_right = move_right
    self.move_back = move_back
    self.move_forward = move_forward
    self.move_down = move_down
    self.move_up = move_up

    self.general_layout = QVBoxLayout()
    self.setLayout(self.general_layout)

    self.button_layout = QGridLayout()

    def move_back_or_up():
      if QtWidgets.QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
        self.move_up()
      else:
        self.move_back()

    def move_forward_or_down():
      if QtWidgets.QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
        self.move_down()
      else:
        self.move_forward()

    self.button_top = QPushButton()
    self.button_layout.addWidget(self.button_top, 0, 1)
    self.button_top.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
    self.button_top.setIcon(QIcon(get_asset("arrow-up.svg")))
    self.button_top.setIconSize(QSize(BUTTON_SIZE, BUTTON_SIZE))
    self.button_top.clicked.connect(move_back_or_up)

    self.button_right = QPushButton()
    self.button_layout.addWidget(self.button_right, 1, 2)
    self.button_right.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
    self.button_right.setIcon(QIcon(get_asset("arrow-right.svg")))
    self.button_right.setIconSize(QSize(BUTTON_SIZE, BUTTON_SIZE))
    self.button_right.clicked.connect(self.move_right)

    self.button_bottom = QPushButton()
    self.button_layout.addWidget(self.button_bottom, 2, 1)
    self.button_bottom.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
    self.button_bottom.setIcon(QIcon(get_asset("arrow-down.svg")))
    self.button_bottom.setIconSize(QSize(BUTTON_SIZE, BUTTON_SIZE))
    self.button_bottom.clicked.connect(move_forward_or_down)

    self.button_left = QPushButton()
    self.button_layout.addWidget(self.button_left, 1, 0)
    self.button_left.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
    self.button_left.setIcon(QIcon(get_asset("arrow-left.svg")))
    self.button_left.setIconSize(QSize(BUTTON_SIZE, BUTTON_SIZE))
    self.button_left.clicked.connect(self.move_left)

    self.general_layout.addLayout(self.button_layout)

    def set_d_callback_wrapper(d):
      set_d_callback(float(d[:-2]))

    self.radios = RadioButtonsWidget(options=["100mm", "10mm", "1mm", "0.1mm"],
      default="10mm", callback=set_d_callback_wrapper)
    self.general_layout.addWidget(self.radios)


class RadioButtonsWidget(QWidget):
  def __init__(self, parent=None, options: list = [], default: str = None, callback=None):
    super().__init__(parent)
    self.general_layout = QVBoxLayout()
    self.setLayout(self.general_layout)
    self.buttons = []

    self.options = options

    self.group = QButtonGroup(self)

    for i, option in enumerate(options):
      button = QRadioButton(option)
      self.buttons.append(button)
      self.group.addButton(button, i)
      self.general_layout.addWidget(button)

      if option == default:
        button.setChecked(True)

    self.group.setExclusive(True)

    self.set_option_changed_callback(callback)

  def set_option_changed_callback(self, callback):
    if callback is None:
      return

    def callback_wrapper():
      callback(self.get_current_option())
    self.group.buttonClicked.connect(callback_wrapper)

  def get_current_option(self):
    for i, button in enumerate(self.buttons):
      if button.isChecked():
        return self.options[i]
    return None

  def set_option(self, option):
    for i, button in enumerate(self.buttons):
      if self.options[i] == option:
        button.setChecked(True)
        return
    raise ValueError("option not found")


def main():
  app = QApplication([])
  window = Window()
  window.show()
  sys.exit(app.exec())


if __name__ == "__main__":
  main()
