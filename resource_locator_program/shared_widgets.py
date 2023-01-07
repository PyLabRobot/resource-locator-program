from functools import partial
import os

from PyQt6 import QtWidgets
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
  QButtonGroup,
  QGridLayout,
  QGroupBox,
  QHBoxLayout,
  QLabel,
  QLineEdit,
  QMessageBox,
  QPushButton,
  QRadioButton,
  QVBoxLayout,
  QWidget,
)

from pylabrobot.resources import Coordinate


BUTTON_SIZE = 50


def get_asset(name):
  return os.path.join(os.path.dirname(__file__), "assets", name)


class RadioButtonsWidget(QWidget):
  def __init__(self, default: str, options: list, parent=None, callback=None):
    super().__init__(parent)
    self.general_layout = QHBoxLayout()
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


class LocationDisplay(QWidget):
  class LocationDisplayLine(QWidget):
    def __init__(self, label: str, parent=None):
      super().__init__(parent)
      self.general_layout = QHBoxLayout()
      self.setLayout(self.general_layout)
      self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
      self.line_edit = QLineEdit()
      self.textChanged = self.line_edit.textChanged
      self.line_edit.focusOutEvent = partial(self._sanitize_float_value)
      self.general_layout.addWidget(QLabel(f"{label}:"))
      self.general_layout.addWidget(self.line_edit)
      self.general_layout.addWidget(QLabel("mm"))
      self.value = None

    def _sanitize_float_value(self, elem):
      self.set_value(self.get_field_value() or self.value)

    def set_value(self, value):
      self.value = value
      self.line_edit.setText(str(round(value, 1)))

    def get_field_value(self):
      try:
        return float(self.line_edit.text())
      except ValueError:
        return None

    def has_changed(self):
      val = self.get_field_value()
      return val is not None and abs(val - self.value) > 1e-4

  def __init__(self, parent, set_location=None):
    super().__init__(parent)
    self.set_location = set_location

    self.general_layout = QHBoxLayout()
    self.setLayout(self.general_layout)

    self.display_x = LocationDisplay.LocationDisplayLine("X")
    self.display_x.textChanged.connect(self.display_label_updated)
    self.general_layout.addWidget(self.display_x)

    self.display_y = LocationDisplay.LocationDisplayLine("Y")
    self.display_y.textChanged.connect(self.display_label_updated)
    self.general_layout.addWidget(self.display_y)

    self.display_z = LocationDisplay.LocationDisplayLine("Z")
    self.display_z.textChanged.connect(self.display_label_updated)
    self.general_layout.addWidget(self.display_z)

    self.move_button = QPushButton("Move")
    self.general_layout.addWidget(self.move_button)
    self.move_button.setDisabled(True)

    self.move_button.clicked.connect(self.move)

    self.display_label_updated()

  def move(self):
    self.set_location(
      x=self.display_x.get_field_value(),
      y=self.display_y.get_field_value(),
      z=self.display_z.get_field_value())

  def display_label_updated(self):
    self.move_button.setEnabled(self.display_x.has_changed() or self.display_y.has_changed() or \
      self.display_z.has_changed())

  def set_x(self, x):
    self.display_x.set_value(x)

  def set_y(self, y):
    self.display_y.set_value(y)

  def set_z(self, z):
    self.display_z.set_value(z)


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

    self.radios = RadioButtonsWidget(options=["0.1mm", "1mm", "10mm", "100mm"],
      default="10mm", callback=set_d_callback_wrapper)
    self.general_layout.addWidget(self.radios)


def show_error_alert(title, description=None, details=None):
  msg = QMessageBox()
  msg.setIcon(QMessageBox.Icon.Critical)
  msg.setText(title)
  if description is not None:
    msg.setInformativeText(description)
  msg.setWindowTitle(title)
  if details is not None:
    msg.setDetailedText(details)
  msg.setStandardButtons(QMessageBox.StandardButton.Ok)
  msg.exec()


class LocationEditor(QWidget):
  def __init__(self, enable_all_tabs, lock_tab, lh, parent=None):
    super().__init__(parent)
    self.enable_all_tabs = enable_all_tabs
    self.lock_tab = lock_tab
    self.lh = lh

    self.general_layout = QVBoxLayout()
    self.setLayout(self.general_layout)

    self._location = None
    self._d = 10

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

    self.display = LocationDisplay(self, set_location=self.set_location)
    self.display.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
    self.display.clearFocus()
    self.mover_group_layout.addWidget(self.display)

    self.controller_disabled = False
    self.enable_all_tabs()

  def get_location(self):
    return self._location

  def set_location(self, x=None, y=None, z=None):
    if self._location is None:
      if any([x is None, y is None, z is None]):
        raise ValueError("When setting location for the first time, all coordinates must be set.")
      self._location = Coordinate(x, y, z)
    else:
      if x is not None:
        self._location.x = x
      if y is not None:
        self._location.y = y
      if z is not None:
        self._location.z = z

  def build_ui(self):
    self.pad.setDisabled(True)
    self.display.setDisabled(True)
    self.controller_disabled = True
    self.enable_all_tabs()

  def set_d(self, d):
    self._d = d

  def move_left(self):
    self.set_location(x=self._location.x - self._d)

  def move_right(self):
    self.set_location(x=self._location.x + self._d)

  def move_back(self):
    self.set_location(y=self._location.y + self._d)

  def move_forward(self):
    self.set_location(y=self._location.y - self._d)

  def move_down(self):
    self.set_location(z=self._location.z - self._d)

  def move_up(self):
    self.set_location(z=self._location.z + self._d)

  def get_controller_disabled(self):
    return self.controller_disabled

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
