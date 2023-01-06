from functools import partial
import logging
import sys

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import (
  QApplication,
  QMainWindow,
  QMessageBox,
  QTabWidget,
  QVBoxLayout,
  QWidget,
)

from resource_locator_program.setup_screen import LoadWidget
from resource_locator_program.resource_locator import ResourceLocatorWidget
from resource_locator_program.path_teacher import PathTeacherWidget


logging.getLogger("pylabrobot").setLevel(logging.DEBUG)


BUTTON_SIZE = 50


class Window(QMainWindow):
  def __init__(self):
    super().__init__()
    self.setWindowTitle("Resource Locator Program")
    self.setMinimumSize(QSize(1000, 1000))
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
    # result = msg.exec()

    self.teaching_tools = None

  def _load_locator(self, lh):
    self.teaching_tools = TeachingTools(parent=self, lh=lh)
    self.general_layout.addWidget(self.teaching_tools)

    self.load_widget.hide()
    self.teaching_tools.show()
    self.teaching_tools.build_ui()
    self.teaching_tools.start()

  def keyPressEvent(self, event):
    if self.teaching_tools is None:
      return
    self.teaching_tools.keyPressEvent(event)

  def keyReleaseEvent(self, event):
    if self.teaching_tools is None:
      return
    self.teaching_tools.keyReleaseEvent(event)


class TeachingTools(QWidget):
  def __init__(self, lh, parent=None):
    super().__init__(parent=parent)
    self.lh = lh

    self.general_layout = QVBoxLayout()
    self.setLayout(self.general_layout)

    self.index = 0

    # add tab widget
    self.tab_widget = QTabWidget()
    self.general_layout.addWidget(self.tab_widget)

    self.location_teacher = ResourceLocatorWidget(
      enable_all_tabs=self.enable_all_tabs,
      lock_tab=partial(self.lock_tab, 0),
      lh=self.lh)
    self.general_layout.addWidget(self.location_teacher)
    self.tab_widget.addTab(self.location_teacher, "Resource Locator")

    self.path_teacher = PathTeacherWidget(
      enable_all_tabs=self.enable_all_tabs,
      lock_tab=partial(self.lock_tab, 1),
      lh=self.lh)
    self.general_layout.addWidget(self.path_teacher)
    self.tab_widget.addTab(self.path_teacher, "Path Teacher")

    self.tab_widget.currentChanged.connect(self._tab_changed)

  def _tab_changed(self, index):
    self.index = index
    if index == 0:
      self.location_teacher.start()
    elif index == 1:
      self.path_teacher.start()

  def start(self):
    if self.index == 0:
      self.location_teacher.start()
    elif self.index == 1:
      self.path_teacher.start()

  def enable_all_tabs(self):
    for i in range(self.tab_widget.count()):
      self.tab_widget.setTabEnabled(i, True)

  def lock_tab(self, tab: int):
    for i in range(self.tab_widget.count()):
      self.tab_widget.setTabEnabled(i, i == tab)

  def build_ui(self):
    self.location_teacher.build_ui()
    self.path_teacher.build_ui()

  def keyPressEvent(self, event):
    # TODO: find a good pattern for this.
    if self.index == 0:
      self.location_teacher.keyPressEvent(event)
    elif self.index == 1:
      self.path_teacher.keyPressEvent(event)
    else:
      raise ValueError

  def keyReleaseEvent(self, event):
    # TODO: find a good pattern for this.
    if self.index == 0:
      self.location_teacher.keyReleaseEvent(event)
    elif self.index == 1:
      self.location_teacher.keyReleaseEvent(event)
    else:
      raise ValueError


def main():
  app = QApplication([])
  window = Window()
  window.show()
  sys.exit(app.exec())


if __name__ == "__main__":
  main()
