# Canarin V5 - Manufacturing Test

import time
import os
from machine import I2C

from canarin import (
    BME280, ExternalRTC,
    UARTPortMux, PMS7003, MHZ16, ZE07CO, UBloxGPS,
    mount_sd, umount_sd,
)

# -- Configuration -----------------------------------------------------------
WIFI_SSID = "Canarin"
WIFI_PASS = "interlab"
WIFI_TIMEOUT_S = 10

UPORT_PMS7003 = 1
UPORT_MHZ16   = 3
UPORT_GPS     = 6
UPORT_ZE07CO  = 7

MOUNT_POINT = "/sd"
LOG_FILE = MOUNT_POINT + "/mfg_test_log.txt"
MAX_RETRIES = 5
W = 50

# -- Helpers -----------------------------------------------------------------
_results = []
_log_lines = []

OK = "OK"
FAIL = "FAIL"


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


# -- Retry helper ------------------------------------------------------------
def _retry_read(tag, name, sensor, fmt_fn, range_fn, timeout_ms=None, delay_ms=1000):
    for attempt in range(MAX_RETRIES):
        try:
            val = sensor.read() if timeout_ms is None else sensor.read(timeout_ms=timeout_ms)
            if val is not None and range_fn(val):
                detail = fmt_fn(val)
                if attempt > 0:
                    detail += " (retry {})".format(attempt)
                _result(tag, name, True, detail)
                return
        except Exception:
            pass
        time.sleep_ms(delay_ms)
    _result(tag, name, False, "no response after {} tries".format(MAX_RETRIES))


def _retry_detect(tag, name, detect_fn, fmt_fn, delay_ms=1000):
    for attempt in range(MAX_RETRIES):
        try:
            val = detect_fn()
            if val:
                detail = fmt_fn(val)
                if attempt > 0:
                    detail += " (retry {})".format(attempt)
                _result(tag, name, True, detail)
                return val
        except Exception:
            pass
        time.sleep_ms(delay_ms)
    _result(tag, name, False, "not found after {} tries".format(MAX_RETRIES))
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
        test_data = "CAN5_MFG_{}".format(time.time())
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
    import network
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
    try:
        rtc = ExternalRTC(i2c)
    except Exception as e:
        _result("RTC", "ISL1219", False, str(e))
        return

    yr, mo, dy, wd, hr, mn, sc = 2025, 1, 15, 4, 12, 30, 0
    try:
        rtc.set_time(yr, mo, dy, wd, hr, mn, sc)
    except Exception as e:
        _result("RTC", "ISL1219", False, "set: " + str(e))
        return

    time.sleep_ms(100)
    t = rtc.get_time()
    if t is None:
        _result("RTC", "ISL1219", False, "readback failed")
        return

    # Tick test
    t0 = rtc.get_time()
    time.sleep(5)
    t1 = rtc.get_time()
    if t0 is None or t1 is None:
        _result("RTC", "ISL1219", False, "tick read failed")
        return

    s0 = t0[4] * 3600 + t0[5] * 60 + t0[6]
    s1 = t1[4] * 3600 + t1[5] * 60 + t1[6]
    elapsed = s1 - s0
    if elapsed < 0:
        elapsed += 86400

    ok = 4 <= elapsed <= 7
    _result("RTC", "ISL1219", ok, "set/get/tick {}s".format(elapsed))


def test_sensors(i2c):
    # BME280
    try:
        bme = BME280(i2c)
        _retry_read(
            "SENSOR", "BME280", bme,
            fmt_fn=lambda v: "T={:.1f}C P={:.0f}hPa H={:.0f}%".format(*v),
            range_fn=lambda v: (-40 <= v[0] <= 85) and (300 <= v[1] <= 1100) and (0 <= v[2] <= 100),
        )
    except Exception as e:
        _result("SENSOR", "BME280", False, str(e))

    # UART sensors via mux
    try:
        umux = UARTPortMux(timeout=2000)
    except Exception as e:
        _result("SENSOR", "UART_MUX", False, str(e))
        return

    # PMS7003
    try:
        pms = PMS7003(umux, port=UPORT_PMS7003)
        _retry_read(
            "SENSOR", "PMS7003", pms,
            fmt_fn=lambda d: "PM2.5={} PM10={}".format(d["pm2_5_atm"], d["pm10_atm"]),
            range_fn=lambda d: 0 <= d["pm2_5_atm"] <= 999,
            timeout_ms=5000,
        )
    except Exception as e:
        _result("SENSOR", "PMS7003", False, str(e))

    # MHZ16
    try:
        mhz = MHZ16(umux, port=UPORT_MHZ16)
        _retry_read(
            "SENSOR", "MHZ16", mhz,
            fmt_fn=lambda v: "CO2={} ppm".format(v),
            range_fn=lambda v: 0 <= v <= 5000,
            delay_ms=2000,
        )
    except Exception as e:
        _result("SENSOR", "MHZ16", False, str(e))

    # ZE07CO
    try:
        ze = ZE07CO(umux, port=UPORT_ZE07CO)
        _retry_read(
            "SENSOR", "ZE07CO", ze,
            fmt_fn=lambda v: "CO={:.1f} ppm".format(v),
            range_fn=lambda v: 0 <= v <= 500,
            delay_ms=2000,
        )
    except Exception as e:
        _result("SENSOR", "ZE07CO", False, str(e))

    # GPS
    try:
        gps = UBloxGPS(umux, port=UPORT_GPS)
        _retry_detect(
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
    _emit("  CANARIN V5 MFG TEST")
    _emit("  FW: {}".format(info.version))
    _bar()

    i2c = I2C(0)

    test_i2c(i2c)
    test_sd_card()
    test_wifi()
    test_rtc(i2c)
    test_sensors(i2c)
    print_summary()
    save_log(_log_lines)


main()
