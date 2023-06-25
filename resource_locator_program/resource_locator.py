import asyncio
import traceback

from PyQt6.QtWidgets import (
  QFileDialog,
  QGroupBox,
  QHBoxLayout,
  QLabel,
  QPushButton,
  QVBoxLayout,
  QWidget,
)

from pylabrobot.resources import TipRack, Plate, Coordinate

from resource_locator_program.shared_widgets import LocationEditor, show_error_alert


class UnlocatedResourcesWidget(QWidget):
  def __init__(self, get_location, lh, parent=None):
    super().__init__(parent)
    self.get_location = get_location
    self.lh = lh

    self.general_layout = QVBoxLayout()
    self.setLayout(self.general_layout)

    self.unlocated_resources_box = QGroupBox("Unlocated resources")
    self.unlocated_resources_box_layout = QVBoxLayout()

    self.unlocated_resources = {}
    self.buttons = []

    self.unlocated_resources_box_layout.addStretch(1)
    self.unlocated_resources_box.setLayout(self.unlocated_resources_box_layout)
    self.general_layout.addWidget(self.unlocated_resources_box)

  def _get_unlocated_resources(self):
    return [resource for resource in self.lh.deck.get_all_resources() if resource.location is None]

  def build_ui(self):
    # TODO: we should handle the case where the child and parent location are unknown. In that case,
    # parent location should be identified first, which should be represented in the UI.

    for i, resource in enumerate(self._get_unlocated_resources()):
      def make_resource_here(i, resource): # closure
        def resource_here():
          print(f"Resource '{resource.name}' is at absolute location {self.get_location()}")

          if isinstance(resource, Plate):
            resource.location = self.get_location() - \
              resource.get_item("A1").location - \
              resource.get_item("A1").center() - \
              resource.parent.get_absolute_location()
          else:
            resource.location = self.get_location() - \
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


class TipRacksWidget(QWidget):
  def __init__(self, pick_up_tip_a1, drop_tip_a1, lh, parent=None):
    super().__init__(parent=parent)
    self.pick_up_tip_a1 = pick_up_tip_a1
    self.drop_tip_a1 = drop_tip_a1
    self.lh = lh

    self.general_layout = QVBoxLayout()
    self.setLayout(self.general_layout)

    self.tip_racks_box = QGroupBox("Tip racks")
    self.tip_racks_box_layout = QVBoxLayout()

    self.tip_racks = {}
    self.buttons = {}

    self.tip_racks_box_layout.addStretch(1)
    self.tip_racks_box.setLayout(self.tip_racks_box_layout)
    self.general_layout.addWidget(self.tip_racks_box)

  def start_pick_up_tip_a1(self):
    for b in self.buttons.values():
      b.setEnabled(False)

  def pick_up_tip_failed(self):
    for b in self.buttons.values():
      b.setEnabled(True)

  def pick_up_tip_a1_succeeded(self, tip_rack):
    self.buttons[tip_rack.name].setText("Drop tip to A1")
    self.buttons[tip_rack.name].setEnabled(True)
    self.tip_racks[tip_rack.name] = True

  def start_drop_tip_a1(self):
    for b in self.buttons.values():
      b.setEnabled(False)

  def start_drop_tip_failed(self, tip_rack):
    self.buttons[tip_rack.name].setEnabled(True)

  def drop_tip_a1_succeeded(self, tip_rack):
    self.buttons[tip_rack.name].setText("Pick up tip A1")
    for b in self.buttons.values():
      b.setEnabled(True)
    self.tip_racks[tip_rack.name] = False

  def build_ui(self):
    if len([x for x in self.lh.deck.get_all_resources() if isinstance(x, TipRack)]) == 0:
      show_error_alert(
        title="The file does not contain any tip racks.",
        description="Layouts must contain at least one tip rack for teaching.")
      return

    for tip_rack in [r for r in self.lh.deck.get_all_resources() if isinstance(r, TipRack)]:
      def make_pick_up_tip_a1(tip_rack): # closure
        def pick_up_tip_a1():
          has_tip = self.tip_racks.get(tip_rack.name, False)
          if has_tip:
            self.drop_tip_a1(tip_rack)
          else:
            self.pick_up_tip_a1(tip_rack)

        return pick_up_tip_a1

      row = QHBoxLayout()
      row.addWidget(QLabel(tip_rack.name))
      button = QPushButton("Pick up tip A1")
      button.clicked.connect(make_pick_up_tip_a1(tip_rack))
      row.addWidget(button)
      self.buttons[tip_rack.name] = button
      self.tip_racks_box_layout.addLayout(row)


class ResourceLocatorWidget(LocationEditor):
  def __init__(self, enable_all_tabs, lock_tab, lh, parent=None):
    super().__init__(enable_all_tabs, lock_tab, lh, parent)

    self.tip_racks_widget = TipRacksWidget(
      pick_up_tip_a1=self.pick_up_tip_a1, drop_tip_a1=self.drop_tip_a1, lh=self.lh)
    self.general_layout.addWidget(self.tip_racks_widget)

    self.general_layout.addWidget(self.mover_group)

    self.unlocated_resources_widget = UnlocatedResourcesWidget(
      get_location=self.get_location, lh=self.lh)
    self.general_layout.addWidget(self.unlocated_resources_widget)

    self.save_button = QPushButton("Save to file")
    self.save_button.clicked.connect(self.save)
    self.general_layout.addWidget(self.save_button)

  def set_location(self, x=None, y=None, z=None):
    super().set_location(x, y, z)

    self.controller_disabled = True

    try:
      if x is not None:
        asyncio.run(self.lh.backend.move_channel_x(self.lh.backend.num_channels - 1, x))
        self.display.set_x(x)
      if y is not None:
        asyncio.run(self.lh.backend.move_channel_y(self.lh.backend.num_channels - 1, y))
        self.display.set_y(y)
      if z is not None:
        asyncio.run(self.lh.backend.move_channel_z(self.lh.backend.num_channels - 1, z))
        self.display.set_z(z)
    except Exception as e:
      traceback.print_exc()
      show_error_alert(
        title="Error while moving y axis",
        description=str(e),
        details=traceback.format_exc())
    finally:
      self.controller_disabled = False

  def pick_up_tip_a1(self, tip_rack: TipRack):
    tip = tip_rack.get_tip("A1")

    try:
      self.tip_racks_widget.start_pick_up_tip_a1()
      asyncio.run(
        self.lh.pick_up_tips(tip_rack["A1"], use_channels=[self.lh.backend.num_channels - 1]))
    except Exception as e: # pylint: disable=broad-except
      self.tip_racks_widget.pick_up_tip_failed()
      traceback.print_exc()
      show_error_alert(
        title="Error while picking up tip",
        description=str(e),
        details=traceback.format_exc())
    else:
      self.tip_racks_widget.pick_up_tip_a1_succeeded(tip_rack)
      tip_spot = tip_rack.get_item("A1")
      tip_spot_location = tip_spot.get_absolute_location() + tip_spot.center()
      self.set_location(
        x=round(tip_spot_location.x, 1),
        y=round(tip_spot_location.y, 1),
        z=round(tip_spot_location.z + tip.total_tip_length + 10, 1))

      self.pad.setDisabled(False)
      self.display.setDisabled(False)
      self.unlocated_resources_widget.setDisabled(False)
      self.controller_disabled = False
      self.lock_tab()

  def drop_tip_a1(self, tip_rack: TipRack):
    try:
      self.tip_racks_widget.start_drop_tip_a1()
      asyncio.run(
        self.lh.drop_tips(tip_rack["A1"], use_channels=[self.lh.backend.num_channels - 1]))
    except Exception as e:
      self.tip_racks_widget.drop_tip_failed()
      traceback.print_exc()
      show_error_alert(
        title="Error while dropping up tip",
        description=str(e),
        details=traceback.format_exc())
    else:
      self.tip_racks_widget.drop_tip_a1_succeeded(tip_rack)
      tip_spot = tip_rack.get_item("A1")
      tip_spot_location = tip_spot.get_absolute_location() + tip_spot.center()
      tip = tip_rack.get_tip("A1")
      self.set_location(
        x=round(tip_spot_location.x, 1),
        y=round(tip_spot_location.y, 1),
        z=round(tip_spot_location.z + tip.total_tip_length + 10, 1))

      self.pad.setDisabled(True)
      self.display.setDisabled(True)
      self.unlocated_resources_widget.setDisabled(True)
      self.controller_disabled = True
      self.enable_all_tabs()

  def build_ui(self):
    super().build_ui()

    self.tip_racks_widget.build_ui()
    self.unlocated_resources_widget.build_ui()

  def start(self):
    try:
      asyncio.run(self.lh.backend.prepare_for_manual_channel_operation())
    except Exception as e:
      traceback.print_exc()
      show_error_alert(
        title="Error moving channels",
        description=str(e),
        details=traceback.format_exc())

  def save(self):
    name = QFileDialog.getSaveFileName(self, "Save file", "lh.json", filter="JSON files (*.json)")

    if name[0] == "":
      return

    self.lh.save(name[0])
