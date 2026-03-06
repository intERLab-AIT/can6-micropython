# Canarin Manufacturing Test

import time
import os
import network
from machine import I2C

from canarin import (
    BME280, ExternalRTC,
    UARTPortMux, PMS7003, MHZ16, ZE07CO, UBloxGPS,
    mount_sd, umount_sd,
    get_version,
    enable_sensor_power, disable_sensor_power,
    enable_netport_power, disable_netport_power,
)

# -- Configuration -----------------------------------------------------------
WIFI_SSID = "Canarin"
WIFI_PASS = "interlab"
WIFI_TIMEOUT_S = 10

# Get board version and set configuration
BOARD_VERSION = get_version()

if BOARD_VERSION == "V5":
    BOARD_NAME = "CANARIN V5"
    UPORT_PMS7003 = 1
    UPORT_MHZ16 = 3
    UPORT_GPS = 6
    UPORT_ZE07CO = 7
    HAS_MHZ16 = True
    HAS_ZE07CO = True
    LOG_PREFIX = "CAN5_MFG_"
    POWER_CONTROL = False
elif BOARD_VERSION == "V6":
    BOARD_NAME = "CANARIN V6"
    UPORT_PMS7003 = 0
    UPORT_MHZ16 = None
    UPORT_GPS = 2
    UPORT_ZE07CO = None
    HAS_MHZ16 = False
    HAS_ZE07CO = False
    LOG_PREFIX = "CAN6_MFG_"
    POWER_CONTROL = True
else:
    raise ValueError("Unknown board version: {}".format(BOARD_VERSION))

# Board-specific constants from canarin module
RTC_ADDR = ExternalRTC.RTC_ADDR
RTC_NAME = ExternalRTC.RTC_NAME

MOUNT_POINT = "/sd"
LOG_FILE = MOUNT_POINT + "/mfg_test_log.txt"
MAX_RETRIES = 5
W = 50

# -- Helpers -----------------------------------------------------------------
_results = []
_log_lines = []


def _emit(line):
    print(line)
    _log_lines.append(line)


def _result(tag, name, ok, detail=""):
    icon = " OK " if ok else "FAIL"
    line = " [{}] [{}] {:<10} {}".format(icon, tag, name, detail[:30])
    _emit(line)
    _results.append((name, ok, detail))


def _info(msg):
    _emit("  .. {}".format(msg))


def _bar(char="="):
    _emit(char * W)


def _get_mac():
    """Return the ESP32 STA MAC address as a hex string (e.g. 'AA:BB:CC:DD:EE:FF')."""
    mac = network.WLAN(network.STA_IF).config('mac')
    return ":".join("{:02X}".format(b) for b in mac)


# -- Retry helper ------------------------------------------------------------
def _retry(tag, name, read_fn, fmt_fn, ok_fn=None, max_retries=MAX_RETRIES, delay_ms=1000):
    """
    Generic retry wrapper for sensor reads or detect calls.

    read_fn: callable returning a value (or None on failure)
    fmt_fn:  callable(value) -> detail string
    ok_fn:   callable(value) -> bool for range validation (default: truthy check)
    """
    if ok_fn is None:
        ok_fn = lambda v: bool(v)
    for attempt in range(max_retries):
        try:
            val = read_fn()
            if val is not None and ok_fn(val):
                detail = fmt_fn(val)
                if attempt > 0:
                    detail += " (retry {})".format(attempt)
                _result(tag, name, True, detail)
                return val
        except Exception:
            pass
        time.sleep_ms(delay_ms)
    _result(tag, name, False, "no response after {} tries".format(max_retries))
    return None


# -- Tests -------------------------------------------------------------------
def test_i2c(i2c):
    devices = i2c.scan()
    if devices:
        addrs = " ".join("0x{:02X}".format(d) for d in devices)
        _result("I2C", "BUS", True, addrs)
    else:
        _result("I2C", "BUS", False, "no devices")
    return devices


def test_sd_card():
    try:
        mount_sd(MOUNT_POINT)
    except Exception as e:
        _result("SD", "CARD", False, str(e))
        return

    ok = False
    try:
        test_file = MOUNT_POINT + "/mfg_test.txt"
        test_data = "{}{}".format(LOG_PREFIX, time.time())
        with open(test_file, "w") as f:
            f.write(test_data)
        with open(test_file, "r") as f:
            ok = f.read() == test_data
        os.remove(test_file)
    except Exception as e:
        _result("SD", "CARD", False, str(e))
        umount_sd(MOUNT_POINT)
        return

    _result("SD", "CARD", ok, "write/read OK" if ok else "data mismatch")
    umount_sd(MOUNT_POINT)


def test_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    time.sleep(1)

    try:
        nets = wlan.scan()
        n = len(nets) if nets else 0
    except Exception:
        n = 0

    if n == 0:
        _result("WIFI", "SCAN", False, "no networks")
        wlan.active(False)
        return
    _result("WIFI", "SCAN", True, "scan OK")

    if WIFI_SSID is None:
        wlan.active(False)
        return

    try:
        if wlan.isconnected():
            wlan.disconnect()
            time.sleep(1)
        wlan.connect(WIFI_SSID, WIFI_PASS or "")
        deadline = time.time() + WIFI_TIMEOUT_S
        while not wlan.isconnected() and time.time() < deadline:
            time.sleep(0.5)
        if wlan.isconnected():
            _result("WIFI", "CONN", True, wlan.ifconfig()[0])
        else:
            _result("WIFI", "CONN", False, "timeout")
    except Exception as e:
        _result("WIFI", "CONN", False, str(e))
    finally:
        try:
            wlan.disconnect()
        except Exception:
            pass
    wlan.active(False)


def test_rtc(i2c):
    if RTC_ADDR not in i2c.scan():
        _result("RTC", RTC_NAME, False, "not on I2C bus")
        return

    try:
        rtc = ExternalRTC(i2c, addr=RTC_ADDR)
    except Exception as e:
        _result("RTC", RTC_NAME, False, str(e))
        return

    yr, mo, dy, wd, hr, mn, sc = 2025, 1, 15, 4, 12, 30, 0
    try:
        rtc.set_time(yr, mo, dy, wd, hr, mn, sc)
    except Exception as e:
        _result("RTC", RTC_NAME, False, "set: " + str(e))
        return

    time.sleep_ms(100)
    t = rtc.get_time()
    if t is None:
        _result("RTC", RTC_NAME, False, "readback failed")
        return

    t0 = rtc.get_time()
    time.sleep(5)
    t1 = rtc.get_time()
    if t0 is None or t1 is None:
        _result("RTC", RTC_NAME, False, "tick read failed")
        return

    s0 = t0[4] * 3600 + t0[5] * 60 + t0[6]
    s1 = t1[4] * 3600 + t1[5] * 60 + t1[6]
    elapsed = s1 - s0
    if elapsed < 0:
        elapsed += 86400

    ok = 4 <= elapsed <= 7
    _result("RTC", RTC_NAME, ok, "set/get/tick {}s".format(elapsed))


def test_sensors(i2c):
    # BME280 — skip quickly if not on bus
    if 0x76 in i2c.scan():
        try:
            bme = BME280(i2c)
            _retry(
                "SENSOR", "BME280", bme.read,
                fmt_fn=lambda v: "T={:.1f}C P={:.0f}hPa H={:.0f}%".format(*v),
                ok_fn=lambda v: (-40 <= v[0] <= 85) and (300 <= v[1] <= 1100) and (0 <= v[2] <= 100),
            )
        except Exception as e:
            _result("SENSOR", "BME280", False, str(e))
    else:
        _result("SENSOR", "BME280", False, "not on I2C bus")

    # UART sensors via mux
    try:
        umux = UARTPortMux(timeout=2000)
    except Exception as e:
        _result("SENSOR", "UART_MUX", False, str(e))
        return

    # PMS7003
    try:
        pms = PMS7003(umux, port=UPORT_PMS7003)
        _retry(
            "SENSOR", "PMS7003", lambda: pms.read(timeout_ms=2000),
            fmt_fn=lambda d: "PM2.5={} PM10={}".format(d["pm2_5_atm"], d["pm10_atm"]),
            ok_fn=lambda d: 0 <= d["pm2_5_atm"] <= 999,
        )
    except Exception as e:
        _result("SENSOR", "PMS7003", False, str(e))

    # MHZ16 (V5 only)
    if HAS_MHZ16 and UPORT_MHZ16 is not None:
        try:
            mhz = MHZ16(umux, port=UPORT_MHZ16)
            _retry(
                "SENSOR", "MHZ16", mhz.read,
                fmt_fn=lambda v: "CO2={} ppm".format(v),
                ok_fn=lambda v: 0 <= v <= 5000,
            )
        except Exception as e:
            _result("SENSOR", "MHZ16", False, str(e))

    # ZE07CO (V5 only)
    if HAS_ZE07CO and UPORT_ZE07CO is not None:
        try:
            ze = ZE07CO(umux, port=UPORT_ZE07CO)
            _retry(
                "SENSOR", "ZE07CO", ze.read,
                fmt_fn=lambda v: "CO={:.1f} ppm".format(v),
                ok_fn=lambda v: 0 <= v <= 500,
            )
        except Exception as e:
            _result("SENSOR", "ZE07CO", False, str(e))

    # GPS — skip configure to avoid long blocking waits when absent
    try:
        gps = UBloxGPS(umux, port=UPORT_GPS, configure=False)
        _retry(
            "SENSOR", "GPS", gps.detect,
            fmt_fn=lambda v: "SW={} HW={}".format(v["sw_version"], v["hw_version"]),
        )
    except Exception as e:
        _result("SENSOR", "GPS", False, str(e))

    umux.disable()


def save_log(lines):
    try:
        mount_sd(MOUNT_POINT)
        with open(LOG_FILE, "w") as f:
            for line in lines:
                f.write(line + "\n")
        _info("log saved to " + LOG_FILE)
        umount_sd(MOUNT_POINT)
    except Exception:
        pass


def print_summary():
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    total = len(_results)

    _emit("")
    _bar()
    if failed == 0:
        _emit(" [ OK ] ALL PASSED ({}/{})".format(passed, total))
    else:
        _emit(" [FAIL] {}/{} PASSED, {} FAILED".format(passed, total, failed))
        for name, ok, detail in _results:
            if not ok:
                _emit("   FAIL {}: {}".format(name, detail))
    _bar()
    _emit("")


# -- Main --------------------------------------------------------------------
def main():
    info = os.uname()
    _bar()
    _emit("  {} TEST".format(BOARD_NAME))
    _emit("  FW: {}".format(info.version))
    _emit("  MAC: {}".format(_get_mac()))
    _bar()

    if POWER_CONTROL:
        enable_sensor_power()
        enable_netport_power()
        time.sleep(1)

    i2c = I2C(0)

    test_i2c(i2c)
    test_sd_card()
    test_wifi()
    test_rtc(i2c)
    test_sensors(i2c)
    print_summary()
    save_log(_log_lines)

    if POWER_CONTROL:
        disable_sensor_power()
        disable_netport_power()


main()
