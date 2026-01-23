from typing import Tuple
import math

from pymodaq.control_modules.move_utility_classes import (
    DAQ_Move_base,
    DataActuator,
    DataActuatorType,
    comon_parameters_fun,
    main
)
from pymodaq.utils.parameter import Parameter

from pymeasure.adapters import VISAAdapter, PrologixAdapter
import pyvisa
from pymodaq_plugins_telem.hardware.anapico_AP5011A import AP5011A



# ----------------------------
# VISA SETUP
# ----------------------------
rm = pyvisa.ResourceManager()
VISA_RESOURCES = rm.list_resources()
ADAPTERS = dict(VISA=VISAAdapter, Prologix=PrologixAdapter)


class DAQ_Move_RFSource_AP5011A(DAQ_Move_base):
    """
    PyMoDAQ 5 plugin for AnaPico APSIN12G

    Axis 0: Frequency (GHz)
    Axis 1: Power (W)
    """

    # =============================
    # ✅ USER-FACING UNITS (FORCED)
    # =============================
    _controller_units = ['GHz', 'W']
    _axis_names = ['Freq', 'Pow']
    is_multiaxes = True
    data_actuator_type = DataActuatorType.DataActuator
    _epsilon = 1e-12

    # =============================
    # ✅ HARD LIMITS (ENFORCED)
    # =============================
    FREQ_MIN_GHZ = 0.1      # 100 MHz
    FREQ_MAX_GHZ = 20.0     # 20.0 GHz
    POW_MIN_W = 1e-9        # -90 dBm
    POW_MAX_W = 0.316        # +25 dBm

    params = [
        {'title': 'Adapter', 'name': 'adapter', 'type': 'list',
         'limits': list(ADAPTERS.keys())},

        {'title': 'VISA Address:', 'name': 'address', 'type': 'list',
         'limits': VISA_RESOURCES},

        {'title': 'Output', 'name': 'output', 'type': 'bool',
         'value': False},
    ] + comon_parameters_fun(
        is_multiaxes,
        axis_names=_axis_names,
        epsilon=_epsilon
    )

    # =============================
    # INIT ATTRIBUTES
    # =============================
    def ini_attributes(self) -> None:
        self.controller: AP5011A | None = None

    # =============================
    # ✅ READ POSITION (GHz, W)
    # =============================
    def get_actuator_value(self) -> DataActuator:
        """
        Returns the current actuator value for the selected axis.
        Always returns a numeric value (float) suitable for 2D scans.
        Axis 'Freq' → GHz
        Axis 'Pow'  → W
        """

        if self.axis_value == 'Freq':
            # Hardware gives Hz → convert to GHz
            try:
                freq_hz = float(self.controller.frequency)
            except Exception:
                freq_hz = 0.0  # fallback if reading fails
            freq_ghz = freq_hz * 1e-9

            val = DataActuator(data=freq_ghz)
            val = self.get_position_with_scaling(val)
            return val

        elif self.axis_value == 'Pow':
            # Hardware gives dBm → convert to W
            try:
                val_dbm = self.controller.power

                # Convert string to float if necessary
                if isinstance(val_dbm, str):
                    val_dbm = float(val_dbm.replace('dBm', '').strip())

            except Exception:
                val_dbm = -90.0  # fallback if reading fails

            # Convert dBm → W
            val_w = 10 ** (val_dbm / 10) * 1e-3

            val = DataActuator(data=val_w)
            val = self.get_position_with_scaling(val)
            return val

        else:
            # Unknown axis → return 0 safely
            return DataActuator(data=0.0)

    # =============================
    # ✅ CLOSE
    # =============================
    def close(self) -> None:
        if self.controller is not None:
            self.controller.shutdown()

    # =============================
    # ✅ LIVE PARAMETER UPDATES
    # =============================
    def commit_settings(self, param: Parameter) -> None:

        if param.name() == "output":
            if param.value():
                self.controller.enable_rf()
            else:
                self.controller.disable_rf()

    # =============================
    # ✅ INITIALIZATION
    # =============================
    def ini_stage(self, controller: object = None) -> Tuple[str, bool]:

        self.ini_stage_init(slave_controller=controller)

        if self.is_master:
            adapter = ADAPTERS[
                self.settings.child('adapter').value()
            ](self.settings.child('address').value())

            self.controller = AP5011A(adapter)

        try:
            info = self.controller.id
            initialized = True
        except Exception:
            info = ""
            initialized = False

        return info, initialized

    # =============================
    # ✅ ABSOLUTE MOVE (GHz, W)
    # =============================
    def move_abs(self, val: DataActuator):

        val = self.check_bound(val)
        val = self.set_position_with_scaling(val)

        if self.axis_value == 'Freq':
            # GHz → Hz
            freq_ghz = val.value()
            freq_hz = freq_ghz * 1e9
            self.controller.frequency = freq_hz

        elif self.axis_value == 'Pow':
            # W → dBm
            pow_w = val.value()
            pow_dbm = 10 * math.log10(pow_w / 1e-3)
            self.controller.power = pow_dbm

        self.target_position = val
        self.current_value = val

    # =============================
    # ✅ RELATIVE MOVE
    # =============================
    def move_rel(self, val: DataActuator) -> None:

        val = self.check_bound(self.current_value + val) - self.current_value
        self.target_value = val + self.current_value
        val = self.set_position_relative_with_scaling(val)

        self.move_abs(self.target_value)

    # =============================
    # ✅ HOME
    # =============================
    def move_home(self):

        # Safe home: minimum power, minimum frequency
        if self.axis_value == 'Freq':
            self.move_abs(DataActuator(self.FREQ_MIN_GHZ))

        elif self.axis_value == 'Pow':
            self.move_abs(DataActuator(self.POW_MIN_W))

    # =============================
    # ✅ STOP
    # =============================
    def stop_motion(self):
        # RF off = safest "stop"
        self.controller.disable_rf()


# =============================
# ✅ STANDALONE MODE
# =============================
if __name__ == '__main__':
    main(__file__)
