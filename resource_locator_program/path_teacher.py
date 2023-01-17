import traceback
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
  QGroupBox,
  QHBoxLayout,
  QLabel,
  QListWidget,
  QPushButton,
  QScrollArea,
  QTextEdit,
  QVBoxLayout,
  QWidget,
)

from resource_locator_program.shared_widgets import LocationEditor, show_error_alert

from pylabrobot.liquid_handling.standard import GripDirection
from pylabrobot.resources import Plate, Coordinate, Resource, CarrierSite, PlateCarrier


PICKUP_DISTANCE_FROM_TOP = 13.2 # mm, for path teaching.


class BuildPathEditorWidget(QWidget):
  def __init__(self, get_location, put_plate, parent=None):
    super().__init__(parent)
    self.put_plate = put_plate
    self.get_location = get_location

    self.destination = None
    self.points = []

    self.general_layout = QVBoxLayout()
    self.setLayout(self.general_layout)

    self.path_builder_group = QGroupBox("Path builder")
    self.path_builder_layout = QVBoxLayout()
    self.path_builder_group.setLayout(self.path_builder_layout)

    # Add current point as intermediate button
    self.add_intermediate_button = QPushButton("Add current point as INTERMEDIATE")
    self.add_intermediate_button.clicked.connect(self.add_intermediate_point)
    self.path_builder_layout.addWidget(self.add_intermediate_button)

    # Add current point as destination button
    self.add_destination_button = QPushButton("Add current point as DESTINATION")
    self.add_destination_button.clicked.connect(self.add_destination_point)
    self.path_builder_layout.addWidget(self.add_destination_button)

    # Remove previous points button
    self.points_list = QListWidget()
    self.path_builder_layout.addWidget(self.points_list)

    # Remove point button to delete the selected point
    self.remove_button = QPushButton("Remove selected point")
    self.remove_button.clicked.connect(self.remove_point)
    self.path_builder_layout.addWidget(self.remove_button)

    # Python code view
    self.python_code = QTextEdit()
    self.python_code.setReadOnly(True)
    self.path_builder_layout.addWidget(self.python_code)
    self.python_code.setFont(QFont("Courier New"))
    self.python_code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    self.general_layout.addWidget(self.path_builder_group)

    self.refresh_ui()

  def set_destination(self, destination):
    self.destination = destination
    self.refresh_ui()

  def refresh_ui(self):
    self.python_code.setText(self.write_python_code())

    # Update the list of points
    self.points_list.clear()
    for point in self.points:
      self.points_list.addItem(
        f"({point.x}, {point.y}, {point.z})")

  def add_intermediate_point(self):
    self.points.append(self.get_location())

    for point in self.points:
      self.points_list.addItem(repr(point))

    self.refresh_ui()

  def remove_point(self):
    if self.points_list.currentRow() == -1:
      return

    self.points.pop(self.points_list.currentRow())

    self.refresh_ui()

  def write_python_code(self):
    if self.destination is None:
      destination_string = "<destination>"
    elif isinstance(self.destination, Coordinate):
      destination_string = repr(self.destination)
    elif isinstance(self.destination, Resource):
      destination_string = f"lh.deck.get_resource(\"{self.destination.name}\")"
    else:
      raise ValueError("Invalid destination")

    if len(self.points) == 0:
      if self.destination is None:
        return "# add points or release plate to generate code"
      return f"lh.move_plate(plate, to={destination_string})"

    code = f"lh.move_plate(plate, to={destination_string}, intermediate_locations=[\n"

    for point in self.points:
      code += f"  {repr(point)}, \n"

    code += "])"

    return code

  def add_destination_point(self):
    self.put_plate(self.get_location())

  def enable(self):
    self.add_intermediate_button.setEnabled(True)
    self.add_destination_button.setEnabled(True)

  def disable(self):
    self.add_intermediate_button.setEnabled(False)
    self.add_destination_button.setEnabled(False)

  def clear(self):
    self.points = []
    self.destination = None
    self.refresh_ui()


class PlatesWidget(QWidget):
  def __init__(self, set_location, put_plate, pick_up_plate, get_picked_up_plate, lh, parent=None):
    super().__init__(parent=parent)
    self.put_plate = put_plate
    self.get_picked_up_plate = get_picked_up_plate
    self.pick_up_plate = pick_up_plate
    self.lh = lh

    self.general_layout = QHBoxLayout()
    self.setLayout(self.general_layout)

    # Add a scrollable box for the plates
    self.plates_box = QGroupBox("Available plates")
    self.plates_box_layout = QVBoxLayout()
    self.plates_box_layout.setContentsMargins(0, 0, 0, 0)
    self.plates_box.setLayout(self.plates_box_layout)

    self.plates_scrollable_content = QWidget()
    self.plates_scrollable_content_layout = QVBoxLayout()
    self.plates_scrollable_content.setLayout(self.plates_scrollable_content_layout)

    self.plates_scroll_area = QScrollArea()
    self.plates_scroll_area.setWidgetResizable(True)
    self.plates_scroll_area.setWidget(self.plates_scrollable_content)
    self.plates_box_layout.addWidget(self.plates_scroll_area)
    self.general_layout.addWidget(self.plates_box)

    self.plates_box_layout.addStretch(1)
    self.plates_box.setLayout(self.plates_box_layout)
    self.general_layout.addWidget(self.plates_box)

    # sites
    self.carrier_sites_box = QGroupBox("Available plate carrier sites")
    self.carrier_sites_box_layout = QVBoxLayout()
    self.carrier_sites_box_layout.setContentsMargins(0, 0, 0, 0)
    self.carrier_sites_box.setLayout(self.carrier_sites_box_layout)
    self.carrier_sites_box.setEnabled(False)
    self.carrier_sites_scrollable_content = QWidget()
    self.carrier_sites_scrollable_content_layout = QVBoxLayout()
    self.carrier_sites_scrollable_content.setLayout(self.carrier_sites_scrollable_content_layout)

    self.carrier_sites_scroll_area = QScrollArea()
    self.carrier_sites_scroll_area.setWidgetResizable(True)
    self.carrier_sites_scroll_area.setWidget(self.carrier_sites_scrollable_content)
    self.carrier_sites_box_layout.addWidget(self.carrier_sites_scroll_area)
    self.general_layout.addWidget(self.carrier_sites_box)

    self.carrier_sites = {}
    self.carrier_sites_rows = {}
    self.carrier_sites_buttons = []
    self.plates_buttons = []

    self.set_location = set_location

  def plate_was_picked_up(self, plate):
    # if plate parent is a site, show the row
    if isinstance(plate.parent, CarrierSite):
      for elem in self.carrier_sites_rows[plate.parent.name]:
        elem.show()

    # enable the carrier site box, disable the plate box.
    self.carrier_sites_box.setEnabled(True)
    self.plates_box.setEnabled(False)

  def plate_was_put(self, plate, site: Optional[CarrierSite]):
    # hide the row where the plate was put because it's no longer available.
    if site is not None:
      for e in self.carrier_sites_rows[site.name]:
        e.hide()

    # show the site where the plate was picked up from, because it's now available again
    if isinstance(plate.parent, CarrierSite):
      for e in self.carrier_sites_rows[plate.parent.name]:
        e.show()

    # enable all plate buttons, the gripper is now free.
    for b in self.plates_buttons:
      b.setEnabled(True)

    # now in plate picking mode.
    self.carrier_sites_box.setEnabled(False)
    self.plates_box.setEnabled(True)

  def build_ui(self):
    if len([x for x in self.lh.deck.get_all_resources() if (
      isinstance(x, Plate) and x.location is not None)]) == 0:
      show_error_alert(
        title="The file does not contain any plates.",
        description="Layouts must contain at least one plate for teaching.")
      return

    for plate in [r for r in self.lh.deck.get_all_resources() if isinstance(r, Plate)]:
      def make_pick_up_plate(plate): # closure
        return lambda: self.pick_up_plate(plate)

      row = QHBoxLayout()
      row.addWidget(QLabel(plate.name))
      button = QPushButton("Pick up this plate")
      button.clicked.connect(make_pick_up_plate(plate))
      row.addWidget(button)
      self.plates_buttons.append(button)
      self.plates_scrollable_content_layout.addLayout(row)

    for site in [r for r in self.lh.deck.get_all_resources() if (
      isinstance(r, CarrierSite) and isinstance(r.parent, PlateCarrier))]:
      def make_put_plate(site): # closure
        return lambda: self.put_plate(site)

      row = QHBoxLayout()
      label = QLabel(site.name)
      row.addWidget(label)
      button = QPushButton("Put plate here")
      button.clicked.connect(make_put_plate(site))
      row.addWidget(button)
      self.carrier_sites_buttons.append(button)
      self.carrier_sites_rows[site.name] = [label, button]
      self.carrier_sites_scrollable_content_layout.addLayout(row)

      if site.resource is not None:
        for e in self.carrier_sites_rows[site.name]:
          e.hide()


class PathTeacherWidget(LocationEditor):
  def __init__(self, enable_all_tabs, lock_tab, lh, parent=None):
    super().__init__(enable_all_tabs, lock_tab, lh, parent)
    self.picked_up_plate = None

    self.plates_widget = PlatesWidget(
      set_location=self.set_location,
      pick_up_plate=self.pick_up_plate,
      put_plate=self.put_plate,
      get_picked_up_plate=self.get_picked_up_plate,
      lh=self.lh)
    self.general_layout.addWidget(self.plates_widget)

    self.general_layout.addWidget(self.mover_group)

    self.build_path_widget = BuildPathEditorWidget(
      get_location=self.get_location,
      put_plate=self.put_plate)
    self.general_layout.addWidget(self.build_path_widget)
    self.build_path_widget.disable()

  def pick_up_plate(self, plate):
    try:
      self.lh.backend.pick_up_resource(
        resource=plate,
        grip_direction=GripDirection.FRONT,
        pickup_distance_from_top=PICKUP_DISTANCE_FROM_TOP,
        offset=Coordinate.zero(),
      )
    except Exception as e:
      print(traceback.format_exc())
      show_error_alert(
        title="An error occurred while picking up plate.",
        description=str(e),
        details=traceback.format_exc())
    else:
      self.controller_disabled = False
      self.pad.setEnabled(True)
      self.display.setEnabled(True)
      self.build_path_widget.enable()
      self.lock_tab()

      self.picked_up_plate = plate

      loc = plate.get_absolute_location()
      self.set_location(
        x=round(loc.x, 1),
        y=round(loc.y, 1),
        z=round(loc.z + self.picked_up_plate.get_size_z() + PICKUP_DISTANCE_FROM_TOP, 1))

      self.plates_widget.plate_was_picked_up(plate)
      self.build_path_widget.clear()

  def put_plate(self, site_or_location):
    assert self.picked_up_plate is not None

    if isinstance(site_or_location, CarrierSite):
      site = site_or_location
      location = site_or_location.get_absolute_location()
    else:
      site = None
      location = site_or_location

    try:
      self.lh.backend.release_picked_up_resource(
        resource=self.picked_up_plate,
        location=location,
        offset=Coordinate.zero(),
        grip_direction=GripDirection.FRONT,
        pickup_distance_from_top=PICKUP_DISTANCE_FROM_TOP,
        minimum_traverse_height_at_beginning_of_a_command=
          int(self._location.z + self.picked_up_plate.get_size_z() / 2) * 10 # "minimum" is scam
      )
    except Exception as e:
      print(traceback.format_exc())
      show_error_alert(
        title="An error occurred while putting plate.",
        description=str(e),
        details=traceback.format_exc())
      raise e
    else:
      self.controller_disabled = True
      self.pad.setDisabled(True)
      self.display.setDisabled(True)
      self.build_path_widget.disable()
      self.enable_all_tabs()

      self.plates_widget.plate_was_put(self.picked_up_plate, site)
      self.build_path_widget.set_destination(site or location)

      self.set_location(
        x=round(location.x, 1),
        y=round(location.y, 1),
        z=200.0)

      self.picked_up_plate = None

  def get_picked_up_plate(self):
    return self.picked_up_plate

  def start(self):
    pass

  def build_ui(self):
    super().build_ui()
    self.plates_widget.build_ui()

  def set_location(self, x=None, y=None, z=None):
    assert self.picked_up_plate is not None

    super().set_location(x=x, y=y, z=z)

    self.controller_disabled = True

    try:
      self.lh.backend.move_picked_up_resource(
        location=self._location,
        resource=self.picked_up_plate,
        grip_direction=GripDirection.FRONT,
        minimum_traverse_height_at_beginning_of_a_command=
          int(self._location.z + self.picked_up_plate.get_size_z() / 2) * 10 # "minimum" is scam
      )
    except Exception as e:
      traceback.print_exc()
      show_error_alert(
        title="Error while moving plate",
        description=str(e),
        details=traceback.format_exc())
    else:
      if x is not None:
        self.display.set_x(x)
      if y is not None:
        self.display.set_y(y)
      if z is not None:
        self.display.set_z(z)
    finally:
      self.controller_disabled = False
