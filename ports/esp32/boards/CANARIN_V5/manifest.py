include("$(PORT_DIR)/boards/manifest.py")

# Utils
require("time")
require("senml")
require("logging")

# Bluetooth
require("aioble")

# Board modules
module("canarin.py", base_path="$(BOARD_DIR)")

# Uncomment the following to freeze main.py
#module("main.py", base_path="$(BOARD_DIR)")
