import asyncio
import contextlib
import curses
import logging

from pylabrobot.liquid_handling import LiquidHandler
from pylabrobot.liquid_handling.backends import STAR
from pylabrobot.resources.hamilton import STARLetDeck


logger = logging.getLogger(__name__)
logging.basicConfig(filename="cli.log", level=logging.DEBUG)


@contextlib.contextmanager
def full_screen_message(stdscr, message):
  stdscr.clear()
  stdscr.addstr(1, 2, message)
  stdscr.refresh()
  yield
  stdscr.clear()
  stdscr.refresh()


class CLI:
  def __init__(self, star: STAR):
    self.step_size = 1.0  # Default distance in mm
    self.precision_mode = (
      False  # Toggles between precision (0.1mm) and normal step size (default 1mm)
    )
    self.position = {"x": 0, "y": 0, "z": 0}
    self.wrist_rotation = STAR.WristOrientation.RIGHT
    self.rotation_drive_orientation = STAR.RotationDriveOrientation.RIGHT
    self.input_buffer = ""  # Buffer for numeric prefixes
    self.last_action = None  # Stores last action for repeat and reverse
    self.reversing = False
    self._previous_step_size = self.step_size

    self.star = star

  async def move_arm_x(self, distance):
    logger.info(f"Moving arm along X by {distance} mm")
    await self.star.move_iswap_x_relative(distance)
    if not self.reversing:
      self.last_action = ("move", "x", distance)

  async def move_arm_y(self, distance):
    logger.info(f"Moving arm along X by {distance} mm")
    await self.star.move_iswap_y_relative(distance)
    if not self.reversing:
      self.last_action = ("move", "y", distance)

  async def move_arm_z(self, distance):
    logging.info(f"Moving arm along Z by {distance} mm")
    await self.star.move_iswap_z_relative(distance)
    if not self.reversing:
      self.last_action = ("move", "z", distance)

  def toggle_precision_mode(self):
    if not self.precision_mode:
      self._previous_step_size = self.step_size
    self.precision_mode = not self.precision_mode
    self.step_size = 0.1 if self.precision_mode else self._previous_step_size

  async def rotate_rotation_drive(self, direction):
    orientations = [
      STAR.RotationDriveOrientation.LEFT,
      STAR.RotationDriveOrientation.FRONT,
      STAR.RotationDriveOrientation.RIGHT,
    ]
    index = orientations.index(self.rotation_drive_orientation)
    self.last_action = ("rotate", "rotation", direction)
    if direction == "counter-clockwise":
      if index == 0:
        return
      self.rotation_drive_orientation = orientations[index - 1]
    elif direction == "clockwise":
      if index == len(orientations) - 1:
        return
      self.rotation_drive_orientation = orientations[index + 1]
    await self.star.rotate_iswap_rotation_drive(self.rotation_drive_orientation)

  async def rotate_wrist_drive(self, direction):
    orientations = [
      STAR.WristOrientation.REVERSE,
      STAR.WristOrientation.LEFT,
      STAR.WristOrientation.STRAIGHT,
      STAR.WristOrientation.RIGHT,
    ]
    index = orientations.index(self.wrist_rotation)
    self.last_action = ("rotate", "wrist", direction)
    if direction == "counter-clockwise":
      if index == 0:
        return
      self.wrist_rotation = orientations[index - 1]
    elif direction == "clockwise":
      if index == len(orientations) - 1:
        return
      self.wrist_rotation = orientations[index + 1]
    await self.star.rotate_iswap_wrist(self.wrist_rotation)

  def adjust_step_size(self, increment):
    self.step_size = max(0.1, self.step_size + increment)

  async def apply_reverse_last_action(self):
    """Executes the reverse of the last action without changing the action's direction."""

    if self.last_action is None:
      return

    action_type, axis_or_arm, value = self.last_action

    self.reversing = True

    if action_type == "move":
      reverse_value = -value
      if axis_or_arm == "x":
        await self.move_arm_x(reverse_value)
      elif axis_or_arm == "y":
        await self.move_arm_y(reverse_value)
      elif axis_or_arm == "z":
        await self.move_arm_z(reverse_value)
    elif action_type == "rotate":
      if axis_or_arm == "rotation":
        await self.rotate_rotation_drive("clockwise" if value == "counter-clockwise" else "counter-clockwise")
      elif axis_or_arm == "wrist":
        await self.rotate_wrist_drive("clockwise" if value == "counter-clockwise" else "counter-clockwise")

  def display_static_instructions(self, stdscr):
    stdscr.addstr(1, 2, "Resource Locator Program, v2.0")
    stdscr.addstr(14, 2, "Controls:")
    stdscr.addstr(
      15,
      4,
      "WASD (y-axis: away/towards, x-axis: left/right), JK (z-axis: up/down)",
    )
    stdscr.addstr(16, 4, "+/- to adjust step size, P to toggle precision mode")
    stdscr.addstr(17, 4, "RT/FG to rotate Rotation and Wrist Drive respectively")
    stdscr.addstr(
      18,
      4,
      "Enter to repeat last action, Backspace to execute reverse of last action",
    )
    stdscr.addstr(19, 4, "C to clear input buffer")
    stdscr.addstr(20, 4, "Press 'q' to quit")

  def display_dynamic_status(self, stdscr):
    # Display position and rotation info
    stdscr.addstr(3, 2, "Center of plate position (mm):")
    stdscr.addstr(4, 4, f"X-axis (left/right): {self.position['x']:.1f}")
    stdscr.addstr(5, 4, f"Y-axis (away/towards): {self.position['y']:.1f}")
    stdscr.addstr(6, 4, f"Z-axis (up/down): {self.position['z']:.1f}")

    # Display rotation info
    stdscr.addstr(8, 2, "Rotation (degrees):")
    stdscr.addstr(
      9,
      4,
      f"Rotation Drive: {self.rotation_drive_orientation.name.ljust(10)}  Wrist: {self.wrist_rotation.name.ljust(10)}",
    )

    # Display current settings
    stdscr.addstr(11, 2, f"Step Size: {self.step_size:.1f} mm")
    mode = "Precision" if self.precision_mode else "Normal"
    stdscr.addstr(12, 2, f"Mode: {mode}")

    stdscr.refresh()

  async def repeat_last_action(self):
    if self.last_action:
      action_type, axis_or_arm, value = self.last_action
      if action_type == "move":
        if axis_or_arm == "x":
          await self.move_arm_x(value)
        elif axis_or_arm == "y":
          await self.move_arm_y(value)
        elif axis_or_arm == "z":
          await self.move_arm_z(value)
      elif action_type == "rotate":
        if axis_or_arm == "rotation":
          await self.rotate_rotation_drive(value)
        elif axis_or_arm == "wrist":
          await self.rotate_wrist_drive(value)

  async def process_key(self, key):
    logger.debug(f"key: {chr(key)}")

    if key == curses.KEY_BACKSPACE or key == 26:  # 26 is the ASCII code for Ctrl+Z
      await self.apply_reverse_last_action()
      return

    if key in map(ord, "0123456789"):
      self.input_buffer += chr(key)
      return
    elif key in map(ord, "wasdjk"):
      direction = chr(key)
      axis = {"w": "y", "s": "y", "a": "x", "d": "x", "j": "z", "k": "z"}[direction]
      multiplier = 1 if direction in "wdk" else -1
      distance = (
        float(self.input_buffer) * multiplier if self.input_buffer else self.step_size * multiplier
      )
      distance = min(99.9, max(-99.9, distance))  # Limit to +/- 99.9 mm

      if axis == "y":
        await self.move_arm_y(distance)
      elif axis == "x":
        await self.move_arm_x(distance)
      elif axis == "z":
        await self.move_arm_z(distance)
      self.input_buffer = ""  # Clear buffer after movement

    elif key in map(ord, "rt"):
      direction = "counter-clockwise" if key == ord("r") else "clockwise"
      await self.rotate_rotation_drive(direction)
      self.input_buffer = ""  # Clear buffer after rotation
    elif key in map(ord, "fg"):
      direction = "counter-clockwise" if key == ord("f") else "clockwise"
      await self.rotate_wrist_drive(direction)
      self.input_buffer = ""  # Clear buffer after rotation

    elif key == ord("+"):
      self.adjust_step_size(0.1)
    elif key == ord("-") and not self.input_buffer:
      self.adjust_step_size(-0.1)
    elif key == ord("p"):
      self.toggle_precision_mode()
    elif key == ord("\n") or key == ord("."):  # Enter key or period
      await self.repeat_last_action()
    elif key == ord("q"):
      return "exit"
    elif key == ord("c"):
      self.input_buffer = ""  # Clear buffer

    self.reversing = False

  async def run(self, stdscr):
    iswap_pos = await self.star.request_iswap_position()
    self.position = {
      "x": iswap_pos["xs"],
      "y": iswap_pos["yj"],
      "z": iswap_pos["zj"],
    }

    self.display_static_instructions(stdscr)

    while True:
      self.display_dynamic_status(stdscr)

      # getch might have queued keys while we were processing the last one
      key = -1
      while True:
        next_key = stdscr.getch()
        if next_key == -1:
          break
        key = next_key

      if key != -1:
        action = await self.process_key(key)
        if action == "exit":
          logger.info("Exiting...")
          break


def main():
  async def _wrapped(stdscr):
    curses.use_default_colors()
    stdscr.nodelay(True)
    curses.curs_set(0)

    logger.info("Setting up...")
    star = STAR()
    lh = LiquidHandler(backend=star, deck=STARLetDeck())
    with full_screen_message(stdscr, "setting up STAR..."):
      await lh.setup()
      await star.position_components_for_free_iswap_y_range()

    await CLI(star=star).run(stdscr)

    logger.info("Stopping...")
    with full_screen_message(stdscr, "Parking iswap..."):
      await lh.backend.park_iswap()
      await lh.stop()

  curses.wrapper(lambda stdscr: asyncio.run(_wrapped(stdscr)))


if __name__ == "__main__":
  main()
