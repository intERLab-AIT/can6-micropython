# Canarin V5

The Canarin V5 is a custom ESP32-based environmental monitoring board designed for the Hazemon project.

## Features

- **MCU**: ESP32-WROOM-32
- **Sensors**:
  - BME280 (Temperature, Pressure, Humidity) via I2C
  - ISL1219 (External RTC) via I2C
  - PMS7003 (Particulate Matter) via UART multiplexer
  - MH-Z16 (CO2) via UART multiplexer
  - ZE07-CO (Carbon Monoxide) via UART multiplexer
  - u-blox NEO GPS via UART multiplexer

- **Connectivity**:
  - WiFi (ESP32 built-in)
  - Ethernet port (NETPORT)

- **Storage**:
  - SD Card slot (SPI interface)

- **Multiplexed I/O**:
  - UPORT: 8-channel UART multiplexer for sensors
  - ADPORT: 4-channel ADC multiplexer

## Pin Configuration

See `PIN_SYSTEM.md` for detailed pin documentation.

## Building

```bash
cd /home/rmukhia/data/ilab/hazemon/micropython/ports/esp32
make BOARD=CANARIN_V5
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
