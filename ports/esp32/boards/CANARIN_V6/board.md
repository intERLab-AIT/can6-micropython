# Canarin V6

The Canarin V6 is a custom ESP32-S3-based environmental monitoring board designed for the Hazemon project.

## Features

- **MCU**: ESP32-S3
- **Sensors**:
  - BME280 (Temperature, Pressure, Humidity) via I2C
  - DS3231 (External RTC) via I2C
  - PMS7003 (Particulate Matter) via UART multiplexer

- **Connectivity**:
  - WiFi (ESP32-S3 built-in)
  - Ethernet port (NETPORT)

- **Storage**:
  - SD Card slot (SPI interface)

- **Multiplexed I/O**:
  - UPORT: 4-channel UART multiplexer for sensors (PM2.5)

## Pin Configuration

See `PIN_SYSTEM.md` for detailed pin documentation.

## Building

```bash
cd /home/rmukhia/data/ilab/hazemon/micropython/ports/esp32
make BOARD=CANARIN_V6
```

## Testing

Run the manufacturing test:

```bash
mpremote run main.py
```

## Board Files

- `mpconfigboard.h` - MicroPython board configuration
- `mpconfigboard.cmake` - CMake board configuration
- `pins.csv` - Pin definitions for `Pin.board.NAME` access
- `manifest.py` - Frozen module manifest
- `canarin.py` - Board-specific sensor drivers
- `main.py` - Manufacturing test script
