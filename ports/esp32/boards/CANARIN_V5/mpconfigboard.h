// Both of these can be set by mpconfigboard.cmake if a BOARD_VARIANT is specified.
#ifndef MICROPY_HW_BOARD_NAME
#define MICROPY_HW_BOARD_NAME "Canarin V5"
#endif

#ifndef MICROPY_HW_MCU_NAME
#define MICROPY_HW_MCU_NAME "ESP32"
#endif

// Network config
#define MICROPY_PY_NETWORK_HOSTNAME_DEFAULT "canarin-v5"

// ------------------------------------------------------------------
// MicroPython Default Peripheral Pins
// ------------------------------------------------------------------
// These pins are used automatically by MicroPython when creating
// I2C, SPI, or UART instances without specifying pins explicitly.
//
// Pin definitions sourced from can5_pins.h and can5_wiring.h
// Other board-specific pins (MUX, buttons, etc.) are defined in
// pins.csv and accessible via Pin.board.NAME in Python.

// I2C0 - Default I2C pins (BME280, External RTC)
// I2C_NUM_0, SDA=GPIO21, SCL=GPIO22, 100kHz
#define MICROPY_HW_I2C0_SCL         (22)
#define MICROPY_HW_I2C0_SDA         (21)

// SPI1 - Default SPI pins for SD Card (MOSI, MISO, SCK)
// Note: CS pin must be specified explicitly in Python code via Pin.board.SDSPI_CS
#define MICROPY_HW_SPI1_MOSI        (23)
#define MICROPY_HW_SPI1_MISO        (19)
#define MICROPY_HW_SPI1_SCK         (18)


// ------------------------------------------------------------------
// Canarin V5 Specific Configuration
// ------------------------------------------------------------------

// MUX configuration from can5_pins.h
// MUX_INH = GPIO12
// UPORT_SEL0=GPIO4, UPORT_SEL1=GPIO2, UPORT_SEL2=GPIO15
// ADPORT_SEL0=GPIO25, ADPORT_SEL1=GPIO26

// Enable pins
// UPORT_EN = GPIO27
// ADPORT_EN = GPIO14
// NETPORT_PERST = GPIO13

// ADC port
// ADPORT_SIG = GPIO33 (ADC1_CHANNEL_5)

// Button pins
// USRBTN = GPIO0 (Boot button)
// RTCINT = GPIO34
// WAKE = GPIO39
