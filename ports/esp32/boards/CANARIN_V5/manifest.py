include("$(PORT_DIR)/boards/manifest.py")

# Utils
require("time")
require("senml")
require("logging")

# Bluetooth
require("aioble")

# Board modules
module("canarin.py", base_path="$(BOARD_DIR)")

# Optional: Include main.py as a module (doesn't auto-run, need to import)
# Uncomment to include in firmware build:
# module("main.py", base_path="$(BOARD_DIR)", opt=3)
