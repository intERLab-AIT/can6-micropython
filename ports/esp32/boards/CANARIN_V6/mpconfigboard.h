// Both of these can be set by mpconfigboard.cmake if a BOARD_VARIANT is specified.
#ifndef MICROPY_HW_BOARD_NAME
#define MICROPY_HW_BOARD_NAME "Canarin V6"
#endif

#ifndef MICROPY_HW_MCU_NAME
#define MICROPY_HW_MCU_NAME   "ESP32S3"
#endif

// Use built-in USB Serial/JTAG for REPL (/dev/ttyACM0).
// Disable USB OTG (TinyUSB) so it doesn't steal the USB pins.
#define MICROPY_HW_ENABLE_USBDEV (0)

// Network config
#define MICROPY_PY_NETWORK_HOSTNAME_DEFAULT "canarin-v6"

// ------------------------------------------------------------------
// MicroPython Default Peripheral Pins
// ------------------------------------------------------------------
// These pins are used automatically by MicroPython when creating
// I2C, SPI, or UART instances without specifying pins explicitly.
//
// Pin definitions sourced from can5_pins.h (ESP32-S3 section).
// Other board-specific pins (MUX, buttons, etc.) are defined in
// pins.csv and accessible via Pin.board.NAME in Python.

// I2C0 - Default I2C pins (BME280, External RTC)
#define MICROPY_HW_I2C0_SCL         (2)
#define MICROPY_HW_I2C0_SDA         (1)

// SPI1 - Default SPI pins for SD Card (MOSI, MISO, SCK)
// Note: CS pin must be specified explicitly in Python code via Pin.board.SDSPI_CS
#define MICROPY_HW_SPI1_MOSI        (11)
#define MICROPY_HW_SPI1_MISO        (13)
#define MICROPY_HW_SPI1_SCK         (12)

