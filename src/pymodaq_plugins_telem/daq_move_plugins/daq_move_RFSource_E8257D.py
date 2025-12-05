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

from pymeasure.instruments.agilent import Agilent8257D


# =============================
# VISA SETUP
# =============================
rm = pyvisa.ResourceManager()
VISA_RESOURCES = rm.list_resources()
ADAPTERS = dict(VISA=VISAAdapter, Prologix=PrologixAdapter)


class DAQ_Move_RFSource_E8257D(DAQ_Move_base):
    """
    PyMoDAQ 5 plugin for Agilent / Keysight E8257D

    Axis 0: Frequency (GHz)
    Axis 1: Power (mW)
    """

    # =============================
    # ✅ FORCED USER UNITS
    # =============================
    _controller_units = ['GHz', 'mW']
    _axis_names = ['Freq', 'Pow']
    is_multiaxes = True
    data_actuator_type = DataActuatorType.DataActuator
    _epsilon = 1e-12

    # =============================
    # ✅ HARD LIMITS
    # =============================
    FREQ_MIN_GHZ = 0.1      # 100 MHz
    FREQ_MAX_GHZ = 20.0     # 20 GHz (adjust if needed)

    POW_MIN_MW = 1e-6       # -60 dBm
    POW_MAX_MW = 100.0      # +20 dBm

    params = [
        {'title': 'Adapter', 'name': 'adapter', 'type': 'list',
         'limits': list(ADAPTERS.keys())},

        {'title': 'VISA Address:', 'name': 'address', 'type': 'list',
         'limits': VISA_RESOURCES},

        {'title': 'Output', 'name': 'output', 'type': 'bool',
         'value': False}
    ] + comon_parameters_fun(
        is_multiaxes,
        axis_names=_axis_names,
        epsilon=_epsilon
    )

    # =============================
    # INIT ATTRIBUTES
    # =============================
    def ini_attributes(self) -> None:
        self.controller: Agilent8257D | None = None

    # =============================
    # ✅ READ POSITION (GHz, mW)
    # =============================
    def get_actuator_value(self) -> DataActuator:

        if self.axis_value == 'Freq':
            # Hardware → Hz → GHz
            freq_hz = self.controller.frequency
            freq_ghz = freq_hz * 1e-9

            val = DataActuator(data=freq_ghz)
            val = self.get_position_with_scaling(val)
            return val

        elif self.axis_value == 'Pow':
            # Hardware → dBm → mW
            pow_dbm = self.controller.power
            pow_mw = 10 ** (pow_dbm / 10)

            val = DataActuator(data=pow_mw)
            val = self.get_position_with_scaling(val)
            return val

    # =============================
    # ✅ CLOSE
    # =============================
    def close(self) -> None:
        if self.controller is not None:
            self.controller.shutdown()

    # =============================
    # ✅ OUTPUT ON/OFF
    # =============================
    def commit_settings(self, param: Parameter) -> None:

        if param.name() == "output":
            if param.value():
                self.controller.enable()
            else:
                self.controller.disable()

    # =============================
    # ✅ INITIALIZATION
    # =============================
    def ini_stage(self, controller: object = None) -> Tuple[str, bool]:

        self.ini_stage_init(slave_controller=controller)

        if self.is_master:
            adapter = ADAPTERS[
                self.settings.child('adapter').value()
            ](self.settings.child('address').value())

            self.controller = Agilent8257D(adapter)

        try:
            info = self.controller.id
            initialized = True
        except Exception:
            info = ""
            initialized = False

        return info, initialized

    # =============================
    # ✅ ABSOLUTE MOVE (GHz, mW)
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
            # mW → dBm
            pow_mw = val.value()
            pow_dbm = 10 * math.log10(pow_mw)
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

        if self.axis_value == 'Freq':
            self.move_abs(DataActuator(self.FREQ_MIN_GHZ))

        elif self.axis_value == 'Pow':
            self.move_abs(DataActuator(self.POW_MIN_MW))

    # =============================
    # ✅ STOP
    # =============================
    def stop_motion(self):
        # Safest stop = RF OFF
        self.controller.disable()


# =============================
# ✅ STANDALONE MODE
# =============================
if __name__ == '__main__':
    main(__file__)
