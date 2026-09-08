"""
PyMoDAQ 0D Viewer plugin for the Magnet-Physik FH 54 Gauss-/Teslameter.

Protocol (RS232, 8N1, 4800/9600/19200 baud, no handshake):
    - Read : "?COMMAND\r"          e.g. b"?MEAS\r"
    - Write: "#COMMAND VALUE\r"    e.g. b"#MODE 1\r"
    - Reply terminates with "\r\n".
    - ?MEAS returns e.g. "123 mT" (value + space + unit).
      Units returned : uT, mT, T, G, kG, A/m, kA/m ...

Tested target :
    - Magnet-Physik FH 54 Gauss-/Teslameter with Hall probe, connected
      through a USB-to-RS232 adapter (Windows COMx or Linux /dev/ttyUSBx).

Author: F. Mallet (2026), based on pymodaq_plugins_telem template.
"""

from typing import Tuple

import numpy as np
import serial
import serial.tools.list_ports

from pymodaq_utils.utils import ThreadCommand
from pymodaq.control_modules.viewer_utility_classes import (
    DAQ_Viewer_base,
    comon_parameters,
    main,
)
from pymodaq.utils.parameter import Parameter
from pymodaq.utils.data import DataFromPlugins, DataToExport


# -----------------------------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------------------------

# Conversion of any unit returned by the FH 54 into Tesla
UNIT_TO_TESLA = {
    "T":    1.0,
    "mT":   1e-3,
    "uT":   1e-6,
    "µT":   1e-6,
    "G":    1e-4,
    "kG":   1e-1,
    "A/m":  4 * np.pi * 1e-7,      # H -> B in vacuum : B = µ0 * H
    "kA/m": 4 * np.pi * 1e-4,
}

MODE_MAP = {"DC": 0, "AC": 1}
BAUDRATES = [4800, 9600, 19200]

# Try to list serial ports so the user can pick one from a drop-down
try:
    SERIAL_PORTS = [p.device for p in serial.tools.list_ports.comports()]
except Exception:
    SERIAL_PORTS = []
if not SERIAL_PORTS:
    SERIAL_PORTS = ["COM1"]


# -----------------------------------------------------------------------------
# LIGHTWEIGHT SERIAL WRAPPER FOR THE FH 54
# -----------------------------------------------------------------------------

class FH54Serial:
    """Minimal serial wrapper for the Magnet-Physik FH 54 teslameter."""

    EOL_W = b"\r"          # commands terminated by CR
    EOL_R = b"\r\n"        # replies terminated by CR LF

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 1.0):
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            write_timeout=timeout,
        )
        # Flush anything left over from a previous session
        try:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except Exception:
            pass

    # ---- low level ----------------------------------------------------------

    def _write(self, cmd: str) -> None:
        self.ser.write(cmd.encode("ascii") + self.EOL_W)
        self.ser.flush()

    def _read_line(self) -> str:
        # read_until stops on the CR LF terminator
        line = self.ser.read_until(self.EOL_R)
        return line.decode("ascii", errors="ignore").strip()

    def query(self, cmd: str) -> str:
        """Send ?CMD and return the raw reply text."""
        self._write(f"?{cmd}")
        return self._read_line()

    def write(self, cmd: str, value=None) -> str:
        """Send #CMD [VALUE] and return the (usually empty / OK) reply."""
        payload = f"#{cmd}" if value is None else f"#{cmd} {value}"
        self._write(payload)
        # Some setters do not reply — a short read is enough
        try:
            return self._read_line()
        except Exception:
            return ""

    # ---- high level ---------------------------------------------------------

    def set_mode(self, mode: str) -> None:
        """mode = 'DC' or 'AC'."""
        self.write("MODE", MODE_MAP[mode])

    def set_autorange(self, on: bool) -> None:
        self.write("AUTO", 1 if on else 0)

    def zero(self) -> None:
        self.write("ZERO", 1)

    def id(self) -> str:
        """FH 54 has no *IDN?; use MODE query as a liveness check."""
        return self.query("MODE")

    def measure_tesla(self) -> Tuple[float, str]:
        """Return (field_in_Tesla, raw_reply)."""
        raw = self.query("MEAS")
        return _parse_field_to_tesla(raw), raw

    def close(self) -> None:
        try:
            # Return to front-panel control
            self.write("LOCAL")
        except Exception:
            pass
        try:
            self.ser.close()
        except Exception:
            pass


def _parse_field_to_tesla(reply: str) -> float:
    """Parse a FH 54 reply like '123 mT' or '-0.045 T' into Tesla."""
    if not reply:
        raise ValueError("Empty reply from FH 54")

    # Some firmwares echo the command name, e.g. "MEAS 123 mT" — drop it
    txt = reply.strip()
    if txt.upper().startswith("MEAS"):
        txt = txt[4:].strip()

    # Normalise decimal separator (FH 54 usually uses '.', keep it safe)
    txt = txt.replace(",", ".")
    parts = txt.split()
    if len(parts) < 2:
        # Value without unit — assume Tesla
        return float(parts[0])

    value = float(parts[0])
    unit = parts[1]
    if unit not in UNIT_TO_TESLA:
        raise ValueError(f"Unknown FH 54 unit: {unit!r} (reply={reply!r})")
    return value * UNIT_TO_TESLA[unit]


# -----------------------------------------------------------------------------
# MAIN PLUGIN CLASS
# -----------------------------------------------------------------------------

class DAQ_0DViewer_FH54(DAQ_Viewer_base):
    """PyMoDAQ 0D viewer for the Magnet-Physik FH 54 Gauss-/Teslameter (RS232).

    Reads a single magnetic-field value (AC RMS or DC) via ?MEAS and returns
    it in Tesla, whatever the display unit selected on the instrument.
    """

    params = comon_parameters + [
        {"title": "Serial port:", "name": "com_port", "type": "list",
         "limits": SERIAL_PORTS},
        {"title": "Baud rate:", "name": "baudrate", "type": "list",
         "limits": BAUDRATES, "value": 9600},
        {"title": "Timeout (s):", "name": "timeout", "type": "float",
         "value": 1.0, "min": 0.1, "max": 10.0},

        {"title": "Measurement mode:", "name": "mode", "type": "list",
         "limits": list(MODE_MAP.keys()), "value": "DC"},
        {"title": "Autorange:", "name": "autorange", "type": "bool",
         "value": True},

        {"title": "Zero (DC):", "name": "zero", "type": "bool_push",
         "value": False},
        {"title": "Last raw reply:", "name": "last_raw", "type": "str",
         "value": "", "readonly": True},
    ]

    # -------------------------------------------------------------------------
    # ATTRIBUTES
    # -------------------------------------------------------------------------

    def ini_attributes(self):
        self.controller: FH54Serial = None

    # -------------------------------------------------------------------------
    # PARAMETER CHANGES
    # -------------------------------------------------------------------------

    def commit_settings(self, param: Parameter):
        if self.controller is None:
            return

        try:
            if param.name() == "mode":
                self.controller.set_mode(param.value())
                self.emit_status(ThreadCommand(
                    "Update_Status", [f"FH54: mode set to {param.value()}"]))

            elif param.name() == "autorange":
                self.controller.set_autorange(bool(param.value()))

            elif param.name() == "zero":
                self.controller.zero()
                param.setValue(False)
                self.emit_status(ThreadCommand(
                    "Update_Status", ["FH54: zero routine executed"]))

        except Exception as e:
            self.emit_status(ThreadCommand(
                "Update_Status", [f"FH54 commit_settings error: {e}", "log"]))

    # -------------------------------------------------------------------------
    # INITIALIZATION
    # -------------------------------------------------------------------------

    def ini_detector(self, controller=None):
        self.ini_detector_init(slave_controller=controller)

        if self.is_master:
            self.controller = FH54Serial(
                port=self.settings["com_port"],
                baudrate=int(self.settings["baudrate"]),
                timeout=float(self.settings["timeout"]),
            )
            # Push initial configuration to the instrument
            self.controller.set_mode(self.settings["mode"])
            self.controller.set_autorange(bool(self.settings["autorange"]))

        # Initialise the plot with an empty value in Tesla
        self.dte_signal_temp.emit(
            DataToExport(
                name="FH54",
                data=[DataFromPlugins(
                    name="FH54",
                    data=[np.array([0.0])],
                    labels=[f"B ({self.settings['mode']}) [T]"],
                    dim="Data0D",
                )],
            )
        )

        try:
            info = f"FH 54 ready ({self.controller.id()})"
            initialized = True
        except Exception as e:
            info = f"FH 54 init failed: {e}"
            initialized = False

        return info, initialized

    # -------------------------------------------------------------------------
    # DATA ACQUISITION
    # -------------------------------------------------------------------------

    def grab_data(self, Naverage=1, **kwargs):
        try:
            if Naverage and Naverage > 1:
                vals = []
                for _ in range(int(Naverage)):
                    v, _raw = self.controller.measure_tesla()
                    vals.append(v)
                value = float(np.mean(vals))
                raw = f"mean of {Naverage} samples"
            else:
                value, raw = self.controller.measure_tesla()

            self.settings.child("last_raw").setValue(raw)

        except Exception as e:
            self.emit_status(ThreadCommand(
                "Update_Status", [f"FH54 grab_data error: {e}", "log"]))
            value = float("nan")

        label = f"B ({self.settings['mode']}) [T]"
        self.dte_signal.emit(
            DataToExport(
                name="FH54",
                data=[DataFromPlugins(
                    name="FH54",
                    data=[np.array([value])],
                    labels=[label],
                    dim="Data0D",
                )],
            )
        )

    # -------------------------------------------------------------------------
    # STOP / CLOSE
    # -------------------------------------------------------------------------

    def stop(self):
        return ""

    def close(self):
        if self.controller is not None:
            self.controller.close()
            self.controller = None


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main(__file__, init=False)
