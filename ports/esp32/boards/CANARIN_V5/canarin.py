import os
import time
import struct
from machine import Pin, I2C, UART, ADC, SDCard


# Pin definitions are sourced from pins.csv
# Access via Pin.board.NAME (e.g., Pin.board.MUX_INH)


# Board API --------------------------------------------------------------------
def get_version():
    """Return the board version string."""
    return "V5"


def enable_sensor_power():
    """No-op for V5 (no load switch)."""
    pass


def disable_sensor_power():
    """No-op for V5 (no load switch)."""
    pass


def enable_netport_power():
    """No-op for V5 (no load switch)."""
    pass


def disable_netport_power():
    """No-op for V5 (no load switch)."""
    pass


# SD Card - SPI mode on slot 2 (VSPI)
_sd = None

def mount_sd(mount_point="/sd"):
    """Mount the SD card and return the mount point."""
    global _sd
    _sd = SDCard(slot=2)
    os.mount(os.VfsFat(_sd), mount_point)
    return mount_point

def umount_sd(mount_point="/sd"):
    """Unmount the SD card."""
    global _sd
    os.umount(mount_point)
    if _sd:
        _sd.deinit()
        _sd = None


# BME280 - Temperature, Pressure, Humidity (I2C)
class BME280:
    """BME280 I2C driver (forced mode). Returns (temp_C, pres_hPa, humi_pct)."""

    _REG_CHIP_ID  = 0xD0
    _REG_RESET    = 0xE0
    _REG_CALIB_00 = 0x88
    _REG_CALIB_26 = 0xE1
    _REG_CTRL_HUM  = 0xF2
    _REG_CTRL_MEAS = 0xF4
    _REG_CONFIG    = 0xF5
    _REG_DATA      = 0xF7

    _CHIP_ID  = 0x60
    _RESET_CMD = 0xB6

    _CTRL_HUM_OS1 = 0b00000001
    _CTRL_MEAS_FORCED = 0b00100101
    _CONFIG = 0b00010000

    def __init__(self, i2c, addr=0x76):
        self.i2c = i2c
        self.addr = addr
        self._t_fine = 0
        self._detect()
        self._reset()
        self._read_calibration()
        self._set_forced_mode()
        self._set_config()

    def _detect(self):
        chip_id = self.i2c.readfrom_mem(self.addr, self._REG_CHIP_ID, 1)[0]
        if chip_id != self._CHIP_ID:
            raise RuntimeError(
                "BME280 not found (chip_id=0x{:02X}, expected 0x{:02X})".format(
                    chip_id, self._CHIP_ID))

    def _reset(self):
        self.i2c.writeto_mem(self.addr, self._REG_RESET, bytes([self._RESET_CMD]))
        time.sleep_ms(10)

    def _read_calibration(self):
        c0 = self.i2c.readfrom_mem(self.addr, self._REG_CALIB_00, 25)
        c1 = self.i2c.readfrom_mem(self.addr, self._REG_CALIB_26, 7)

        self._dig_T1 = struct.unpack_from('<H', c0, 0)[0]
        self._dig_T2 = struct.unpack_from('<h', c0, 2)[0]
        self._dig_T3 = struct.unpack_from('<h', c0, 4)[0]

        self._dig_P1 = struct.unpack_from('<H', c0, 6)[0]
        self._dig_P2 = struct.unpack_from('<h', c0, 8)[0]
        self._dig_P3 = struct.unpack_from('<h', c0, 10)[0]
        self._dig_P4 = struct.unpack_from('<h', c0, 12)[0]
        self._dig_P5 = struct.unpack_from('<h', c0, 14)[0]
        self._dig_P6 = struct.unpack_from('<h', c0, 16)[0]
        self._dig_P7 = struct.unpack_from('<h', c0, 18)[0]
        self._dig_P8 = struct.unpack_from('<h', c0, 20)[0]
        self._dig_P9 = struct.unpack_from('<h', c0, 22)[0]

        self._dig_H1 = c0[24]
        self._dig_H2 = struct.unpack_from('<h', c1, 0)[0]
        self._dig_H3 = c1[2]
        self._dig_H4 = (c1[3] << 4) | (c1[4] & 0x0F)
        if self._dig_H4 > 2047:
            self._dig_H4 -= 4096
        self._dig_H5 = ((c1[4] >> 4) & 0x0F) | (c1[5] << 4)
        if self._dig_H5 > 2047:
            self._dig_H5 -= 4096
        self._dig_H6 = struct.unpack_from('<b', c1, 6)[0]

    def _set_forced_mode(self):
        self.i2c.writeto_mem(self.addr, self._REG_CTRL_HUM, bytes([self._CTRL_HUM_OS1]))
        self.i2c.writeto_mem(self.addr, self._REG_CTRL_MEAS, bytes([self._CTRL_MEAS_FORCED]))
        time.sleep_ms(10)

    def _set_config(self):
        self.i2c.writeto_mem(self.addr, self._REG_CONFIG, bytes([self._CONFIG]))
        time.sleep_ms(1)

    def _compensate_temperature(self, adc_T):
        var1 = (((adc_T >> 3) - (self._dig_T1 << 1)) * self._dig_T2) >> 11
        var2 = (((((adc_T >> 4) - self._dig_T1) *
                  ((adc_T >> 4) - self._dig_T1)) >> 12) *
                self._dig_T3) >> 14
        self._t_fine = var1 + var2
        return ((self._t_fine * 5 + 128) >> 8) / 100.0

    def _compensate_pressure(self, adc_P):
        var1 = self._t_fine - 128000
        var2 = var1 * var1 * self._dig_P6
        var2 = var2 + ((var1 * self._dig_P5) << 17)
        var2 = var2 + (self._dig_P4 << 35)
        var1 = ((var1 * var1 * self._dig_P3) >> 8) + \
               ((var1 * self._dig_P2) << 12)
        var1 = (((1 << 47) + var1) * self._dig_P1) >> 33
        if var1 == 0:
            return 0.0
        p = 1048576 - adc_P
        p = (((p << 31) - var2) * 3125) // var1
        var1 = (self._dig_P9 * (p >> 13) * (p >> 13)) >> 25
        var2 = (self._dig_P8 * p) >> 19
        p = ((p + var1 + var2) >> 8) + (self._dig_P7 << 4)
        return (p / 256.0) / 100.0

    def _compensate_humidity(self, adc_H):
        v = self._t_fine - 76800
        v = (((((adc_H << 14) - (self._dig_H4 << 20) -
               (self._dig_H5 * v)) + 16384) >> 15) *
             (((((((v * self._dig_H6) >> 10) *
                  (((v * self._dig_H3) >> 11) + 32768)) >> 10) +
                2097152) * self._dig_H2 + 8192) >> 14))
        v = v - (((((v >> 15) * (v >> 15)) >> 7) * self._dig_H1) >> 4)
        v = max(0, min(v, 419430400))
        return (v >> 12) / 1024.0

    def read(self):
        """Return (temp_C, pres_hPa, humi_pct)."""
        self._set_forced_mode()
        data = self.i2c.readfrom_mem(self.addr, self._REG_DATA, 8)
        adc_P = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        adc_T = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        adc_H = (data[6] << 8) | data[7]
        temp = self._compensate_temperature(adc_T)
        pres = self._compensate_pressure(adc_P)
        humi = self._compensate_humidity(adc_H)
        return (temp, pres, humi)


# PortMultiplexer - base mux control
class PortMultiplexer:
    """Controls an analog multiplexer for sensor port routing."""

    def __init__(self, inh_pin, sel_pins, en_pin=None):
        self._inh = Pin(inh_pin, Pin.OUT, value=1)
        self._sel = [Pin(p, Pin.OUT, value=0) for p in sel_pins]
        self._en = Pin(en_pin, Pin.OUT, value=0) if en_pin is not None else None
        self._selected = -1
        self._max_ports = 1 << len(sel_pins)

    def select(self, port):
        if not 0 <= port < self._max_ports:
            raise ValueError("port {} out of range 0-{}".format(
                port, self._max_ports - 1))
        if port == self._selected:
            return
        self._inh.value(1)
        time.sleep_ms(10)
        for i, pin in enumerate(self._sel):
            pin.value((port >> i) & 1)
        time.sleep_ms(10)
        self._inh.value(0)
        time.sleep_ms(10)
        self._selected = port

    def enable(self, state=True):
        if self._en is not None:
            self._en.value(1 if state else 0)

    def disable(self):
        self.enable(False)

    @property
    def selected(self):
        return self._selected

    @property
    def max_ports(self):
        return self._max_ports


# UARTPortMux - multiplexed UART sensor ports (up to 8 channels)
class UARTPortMux:
    """
    Multiplexed UART access for Canarin V5 UPORT channels.

    Uses UART2 (TX=GPIO16, RX=GPIO17) with baudrate=9600.
    Supports up to 8 sensor ports via 3-bit mux select.
    """

    def __init__(self, uart_id=2, baudrate=9600, timeout_ms=1000, **uart_kwargs):
        self._mux = PortMultiplexer(
            inh_pin=Pin.board.MUX_INH,
            sel_pins=[Pin.board.UPORT_SEL0, Pin.board.UPORT_SEL1, Pin.board.UPORT_SEL2],
            en_pin=Pin.board.UPORT_EN,
        )
        kwargs = {"timeout": timeout_ms, "tx": Pin.board.UPORT_TX, "rx": Pin.board.UPORT_RX}
        kwargs.update(uart_kwargs)
        self._uart = UART(uart_id, baudrate=baudrate, **kwargs)

    def select(self, port):
        self._mux.select(port)
        self._mux.enable(True)
        time.sleep_ms(50)

    def read(self, nbytes=None):
        if nbytes:
            return self._uart.read(nbytes)
        return self._uart.read()

    def readline(self):
        return self._uart.readline()

    def write(self, data):
        return self._uart.write(data)

    def any(self):
        return self._uart.any()

    def disable(self):
        self._mux.enable(False)

    def flush_rx(self):
        while self._uart.any():
            self._uart.read(self._uart.any())

    @property
    def uart(self):
        return self._uart

    @property
    def mux(self):
        return self._mux


# ADCPortMux - multiplexed ADC sensor ports (up to 4 channels)
class ADCPortMux:
    """Multiplexed ADC access for Canarin V5 ADPORT channels."""

    def __init__(self, atten=ADC.ATTN_11DB):
        self._mux = PortMultiplexer(
            inh_pin=Pin.board.MUX_INH,
            sel_pins=[Pin.board.ADPORT_SEL0, Pin.board.ADPORT_SEL1],
            en_pin=Pin.board.ADPORT_EN,
        )
        self._adc = ADC(Pin.board.ADPORT_SIG)
        self._adc.atten(atten)
        self._adc.width(ADC.WIDTH_12BIT)

    def select(self, port):
        self._mux.select(port)
        self._mux.enable(True)

    def read(self):
        return self._adc.read()

    def read_uv(self):
        return self._adc.read_uv()

    def disable(self):
        self._mux.enable(False)

    @property
    def adc(self):
        return self._adc

    @property
    def mux(self):
        return self._mux


# ExternalRTC (ISL1219)
class ExternalRTC:
    """External RTC driver for ISL1219 over I2C. Default address: 0x6F."""

    _REG_RTC_SC = 0x00
    _HR_MIL     = 0x80

    RTC_ADDR = 0x6F
    RTC_NAME = "ISL1219"

    def __init__(self, i2c, addr=0x6F):
        self.i2c = i2c
        self.addr = addr
        if addr not in i2c.scan():
            raise Exception("ExternalRTC not found at address 0x{:02X}".format(addr))

    @staticmethod
    def _bcd2dec(bcd):
        return (bcd >> 4) * 10 + (bcd & 0x0F)

    @staticmethod
    def _dec2bcd(dec):
        return (dec // 10) << 4 | (dec % 10)

    def get_time(self):
        """
        Returns (year, month, day, weekday, hour, minute, second) or None.
        year=4-digit, month=1-12, day=1-31, weekday=1-7, hour=0-23
        """
        try:
            d = self.i2c.readfrom_mem(self.addr, self._REG_RTC_SC, 7)
            return (
                self._bcd2dec(d[5]) + 2000,
                self._bcd2dec(d[4]),
                self._bcd2dec(d[3]),
                d[6] & 0x07,
                self._bcd2dec(d[2] & 0x3F),
                self._bcd2dec(d[1]),
                self._bcd2dec(d[0]),
            )
        except Exception as e:
            print("Error reading RTC:", e)
            return None

    def set_time(self, year, month, day, weekday, hour, minute, second):
        """
        Set RTC time. Returns True on success.
        year (4-digit), month=1-12, day=1-31, weekday=1-7, hour=0-23
        """
        try:
            data = bytearray(7)
            data[0] = self._dec2bcd(second)
            data[1] = self._dec2bcd(minute)
            data[2] = self._dec2bcd(hour) | self._HR_MIL
            data[3] = self._dec2bcd(day)
            data[4] = self._dec2bcd(month)
            data[5] = self._dec2bcd(year - 2000)
            data[6] = weekday & 0x07
            self.i2c.writeto_mem(self.addr, self._REG_RTC_SC, data)
            return True
        except Exception as e:
            print("Error writing RTC:", e)
            return False


# _MuxUARTSensor - shared base for UART sensors that use UARTPortMux
class _MuxUARTSensor:
    """Base class for UART sensors connected via UARTPortMux or direct UART."""

    def __init__(self, uart_or_mux, port=None):
        if isinstance(uart_or_mux, UARTPortMux):
            self._mux = uart_or_mux
            self._port = port
            self._uart = uart_or_mux.uart
        else:
            self._mux = None
            self._port = None
            self._uart = uart_or_mux

    def _select(self):
        if self._mux is not None and self._port is not None:
            self._mux.select(self._port)

    def _flush(self):
        while self._uart.any():
            self._uart.read(self._uart.any())


# PMS7003 - Plantower Particulate Matter sensor (UART)
class PMS7003(_MuxUARTSensor):
    """PMS7003 PM sensor driver (passive/Q&A mode, 9600 baud)."""

    _START1 = 0x42
    _START2 = 0x4D
    _FRAME_LEN = 32

    _CMD_PASSIVE = bytes([0x42, 0x4D, 0xE1, 0x00, 0x00, 0x01, 0x70])
    _CMD_READ    = bytes([0x42, 0x4D, 0xE2, 0x00, 0x00, 0x01, 0x71])

    def __init__(self, uart_or_mux, port=None):
        super().__init__(uart_or_mux, port)
        self._select()
        self._flush()
        self._uart.write(self._CMD_PASSIVE)
        time.sleep_ms(100)
        self._flush()

    @staticmethod
    def _checksum_ok(frame):
        expected = (frame[30] << 8) | frame[31]
        return sum(frame[:30]) == expected

    def _read_frame(self, timeout_ms=2000):
        self._select()
        self._flush()
        self._uart.write(self._CMD_READ)

        buf = bytearray(self._FRAME_LEN)
        pos = 0
        start_found = False
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)

        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            if not self._uart.any():
                time.sleep_ms(5)
                continue
            b = self._uart.read(1)
            if b is None:
                continue
            ch = b[0]

            if not start_found:
                if ch == self._START1:
                    buf[0] = ch
                    pos = 1
                    start_found = True
                continue

            if pos == 1 and ch != self._START2:
                if ch == self._START1:
                    buf[0] = ch
                    pos = 1
                else:
                    start_found = False
                    pos = 0
                continue

            buf[pos] = ch
            pos += 1

            if pos == self._FRAME_LEN:
                if self._checksum_ok(buf):
                    return buf
                start_found = False
                pos = 0

        return None

    @staticmethod
    def _parse(frame):
        def u16(hi, lo):
            return (frame[hi] << 8) | frame[lo]
        return {
            "pm1_0_cf1":  u16(4, 5),
            "pm2_5_cf1":  u16(6, 7),
            "pm10_cf1":   u16(8, 9),
            "pm1_0_atm":  u16(10, 11),
            "pm2_5_atm":  u16(12, 13),
            "pm10_atm":   u16(14, 15),
        }

    def read(self, timeout_ms=2000):
        """Return dict with PM readings, or None on timeout."""
        frame = self._read_frame(timeout_ms)
        if frame is None:
            return None
        return self._parse(frame)


# _WinsenSensor - shared base for Winsen 9-byte frame protocol sensors
class _WinsenSensor(_MuxUARTSensor):
    """
    Base for Winsen sensors using the 9-byte frame protocol (MH-Z16, ZE07-CO).

    Subclasses set _CMD_INIT, _CMD_READ and implement _parse_value(frame).
    Frame format: [START=0xFF][CMD=0x86][data...][checksum]
    Checksum: sum of bytes 0..7 == 0x00 (mod 256).
    """

    _FRAME_LEN = 9
    _START_BYTE = 0xFF
    _CMD_BYTE = 0x86

    _CMD_INIT = None  # Subclasses override
    _CMD_READ = None  # Subclasses override

    def __init__(self, uart_or_mux, port=None):
        super().__init__(uart_or_mux, port)
        self._select()
        self._flush()
        if self._CMD_INIT:
            self._uart.write(self._CMD_INIT)
            time.sleep_ms(100)
            self._flush()

    def _read_frame(self, timeout_ms=1000):
        self._select()
        self._flush()
        self._uart.write(self._CMD_READ)

        buf = bytearray(self._FRAME_LEN)
        pos = 0
        start_found = False
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)

        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            if not self._uart.any():
                time.sleep_ms(5)
                continue
            b = self._uart.read(1)
            if b is None:
                continue
            ch = b[0]

            if not start_found:
                if ch == self._START_BYTE:
                    start_found = True
                    pos = 0
                continue

            buf[pos] = ch
            pos += 1

            if pos == 1 and ch != self._CMD_BYTE:
                start_found = False
                pos = 0
                continue

            if pos == self._FRAME_LEN - 1:
                if sum(buf[0:8]) & 0xFF == 0:
                    return buf
                start_found = False
                pos = 0

        return None

    def _parse_value(self, frame):
        """Subclasses override to extract the sensor value from a valid frame."""
        raise NotImplementedError

    def read(self, timeout_ms=1000):
        """Return parsed sensor value, or None on timeout."""
        frame = self._read_frame(timeout_ms)
        if frame is None:
            return None
        return self._parse_value(frame)


# MHZ16 - Winsen MH-Z16 NDIR CO2 sensor (UART)
class MHZ16(_WinsenSensor):
    """MH-Z16 CO2 sensor driver (Q&A mode, 9600 baud)."""

    _CMD_INIT = bytes([0xFF, 0x01, 0x78, 0x41, 0x00, 0x00, 0x00, 0x00, 0x46])
    _CMD_READ = bytes([0xFF, 0x01, 0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79])

    def _parse_value(self, frame):
        """Return CO2 in ppm."""
        return frame[1] * 256 + frame[2]


# ZE07CO - Winsen ZE07-CO electrochemical CO sensor (UART)
class ZE07CO(_WinsenSensor):
    """ZE07-CO carbon-monoxide sensor driver (Q&A mode, 9600 baud)."""

    _CMD_INIT = bytes([0xFF, 0x01, 0x78, 0x41, 0x00, 0x00, 0x00, 0x00, 0x46])
    _CMD_READ = bytes([0xFF, 0x01, 0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79])

    def __init__(self, uart_or_mux, port=None, bias=0.0):
        self.bias = bias
        super().__init__(uart_or_mux, port)

    def _parse_value(self, frame):
        """Return CO in ppm (float)."""
        val = (frame[1] * 256 + frame[2]) * 0.1 + self.bias
        return max(0.0, val)


# NetPort - UART2 for Ethernet/Cellular modem
class NetPort:
    """
    Access to NETPORT UART (UART2).

    Used for cellular modules (e.g., SIM7600) or Ethernet.
    Pinout: TX=GPIO32, RX=GPIO35, PERST=GPIO13
    """

    def __init__(self, uart_id=1, baudrate=9600, timeout_ms=1000, **uart_kwargs):
        self._perst = Pin.board.NETPORT_PERST
        self._perst.init(Pin.OUT, value=1)
        kwargs = {"timeout": timeout_ms, "tx": Pin.board.NETPORT_TX, "rx": Pin.board.NETPORT_RX}
        kwargs.update(uart_kwargs)
        self._uart = UART(uart_id, baudrate=baudrate, **kwargs)

    def reset(self, delay_ms=1000):
        """Reset modem via PERST pin."""
        self._perst.value(0)
        time.sleep_ms(delay_ms)
        self._perst.value(1)

    def read(self, nbytes=None):
        if nbytes:
            return self._uart.read(nbytes)
        return self._uart.read()

    def readline(self):
        return self._uart.readline()

    def write(self, data):
        return self._uart.write(data)

    def any(self):
        return self._uart.any()

    def flush_rx(self):
        while self._uart.any():
            self._uart.read(self._uart.any())

    @property
    def uart(self):
        return self._uart

    @property
    def perst(self):
        return self._perst


# UBloxGPS - u-blox NEO GPS receiver (UART, UBX binary protocol)
class UBloxGPS(_MuxUARTSensor):
    """
    u-blox NEO GPS driver using UBX binary protocol (9600 baud).

    Supports NEO-M8M and compatible u-blox GPS modules.
    Configurable for continuous or power-save mode.
    """

    _SYNC1 = 0xB5
    _SYNC2 = 0x62

    _NAV_PVT_CLASS = 0x01
    _NAV_PVT_ID = 0x07
    _MON_VER_CLASS = 0x0A
    _MON_VER_ID = 0x04
    _CFG_PRT_CLASS = 0x06
    _CFG_PRT_ID = 0x00
    _CFG_RXM_CLASS = 0x06
    _CFG_RXM_ID = 0x11
    _CFG_RATE_CLASS = 0x06
    _CFG_RATE_ID = 0x08

    _PVT_VALID_DATE = 0x01
    _PVT_VALID_TIME = 0x02
    _PVT_FULLY_RESOLVED = 0x04

    def __init__(self, uart_or_mux, port=None, configure=True, power_save=False):
        super().__init__(uart_or_mux, port)
        self._power_save = power_save
        if configure:
            self._select()
            self._configure()

    @staticmethod
    def _ubx_checksum(data):
        ck_a = ck_b = 0
        for b in data:
            ck_a = (ck_a + b) & 0xFF
            ck_b = (ck_b + ck_a) & 0xFF
        return ck_a, ck_b

    @classmethod
    def _ubx_encode(cls, msg_class, msg_id, payload=b''):
        length = len(payload)
        body = bytes([msg_class, msg_id, length & 0xFF, (length >> 8) & 0xFF]) + payload
        ck_a, ck_b = cls._ubx_checksum(body)
        return bytes([cls._SYNC1, cls._SYNC2]) + body + bytes([ck_a, ck_b])

    @classmethod
    def _ubx_decode(cls, frame):
        if len(frame) < 8:
            return None
        if frame[0] != cls._SYNC1 or frame[1] != cls._SYNC2:
            return None
        msg_class = frame[2]
        msg_id = frame[3]
        length = frame[4] | (frame[5] << 8)
        if len(frame) < 6 + length + 2:
            return None
        payload = frame[6:6 + length]
        ck_a, ck_b = cls._ubx_checksum(frame[2:6 + length])
        if frame[6 + length] != ck_a or frame[7 + length] != ck_b:
            return None
        return (msg_class, msg_id, payload)

    def _recv_ubx(self, timeout_ms=1000):
        buf = bytearray(256)
        pos = 0
        state = 0
        msg_len = 0
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)

        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            if not self._uart.any():
                time.sleep_ms(2)
                continue
            b = self._uart.read(1)
            if b is None:
                continue
            ch = b[0]

            if state == 0:
                if ch == self._SYNC1:
                    buf[0] = ch
                    pos = 1
                    state = 1
                continue

            if state == 1:
                if ch == self._SYNC2:
                    buf[1] = ch
                    pos = 2
                    state = 2
                else:
                    state = 0
                continue

            buf[pos] = ch
            pos += 1

            if state == 2 and pos == 6:
                msg_len = buf[4] | (buf[5] << 8)
                if msg_len > 240:
                    state = 0
                    pos = 0
                    continue
                state = 3

            if state == 3 and pos == 6 + msg_len + 2:
                return bytes(buf[:pos])

        return None

    def _command(self, msg_class, msg_id, payload=b'', timeout_ms=1000):
        self._select()
        self._flush()
        self._uart.write(self._ubx_encode(msg_class, msg_id, payload))
        frame = self._recv_ubx(timeout_ms)
        if frame is None:
            return None
        return self._ubx_decode(frame)

    def _configure(self, meas_rate_ms=None):
        """Configure GPS for UBX-only mode and set power/rate."""
        cfg_prt = struct.pack('<BBHIIHHHxx',
                              0x01, 0x00, 0x0000, 0x08C0, 9600,
                              0x0001, 0x0001, 0x0000)
        self._command(self._CFG_PRT_CLASS, self._CFG_PRT_ID, cfg_prt, timeout_ms=500)
        time.sleep_ms(100)

        lp_mode = 0x01 if self._power_save else 0x00
        cfg_rxm = struct.pack('<BB', 0x00, lp_mode)
        self._command(self._CFG_RXM_CLASS, self._CFG_RXM_ID, cfg_rxm, timeout_ms=500)
        time.sleep_ms(100)

        if meas_rate_ms is None:
            meas_rate_ms = 30000 if self._power_save else 250
        cfg_rate = struct.pack('<HHH', meas_rate_ms, 1, 0)
        self._command(self._CFG_RATE_CLASS, self._CFG_RATE_ID, cfg_rate, timeout_ms=500)

    def detect(self):
        """Poll MON-VER. Returns version dict or None."""
        resp = self._command(self._MON_VER_CLASS, self._MON_VER_ID, timeout_ms=1000)
        if resp is None:
            return None
        _, _, payload = resp
        if len(payload) < 40:
            return None
        sw = payload[:30].split(b'\x00', 1)[0].decode()
        hw = payload[30:40].split(b'\x00', 1)[0].decode()
        return {"sw_version": sw, "hw_version": hw}

    def read(self, timeout_ms=1500):
        """Poll NAV-PVT. Returns fix dict or None."""
        resp = self._command(self._NAV_PVT_CLASS, self._NAV_PVT_ID, timeout_ms=timeout_ms)
        if resp is None:
            return None
        _, _, p = resp
        if len(p) < 92:
            return None

        valid = p[11]
        fix_type = p[20]
        num_sv = p[23]
        lon = struct.unpack_from('<i', p, 24)[0] * 1e-7
        lat = struct.unpack_from('<i', p, 28)[0] * 1e-7
        alt_msl = struct.unpack_from('<i', p, 36)[0] * 0.001
        vel_n = struct.unpack_from('<i', p, 48)[0] * 0.001
        vel_e = struct.unpack_from('<i', p, 52)[0] * 0.001
        vel_d = struct.unpack_from('<i', p, 56)[0] * 0.001

        result = {
            "lat": lat,
            "lon": lon,
            "alt": alt_msl,
            "n_sat": num_sv,
            "fix_type": fix_type,
            "fix": (valid & self._PVT_FULLY_RESOLVED) != 0,
            "vel_north": vel_n,
            "vel_east": vel_e,
            "vel_down": vel_d,
        }

        if valid & (self._PVT_VALID_DATE | self._PVT_VALID_TIME):
            result["year"] = struct.unpack_from('<H', p, 4)[0]
            result["month"] = p[6]
            result["day"] = p[7]
            result["hour"] = p[8]
            result["min"] = p[9]
            result["sec"] = p[10]

        return result
