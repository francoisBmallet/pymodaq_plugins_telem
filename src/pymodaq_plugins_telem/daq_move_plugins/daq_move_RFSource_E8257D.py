from typing import Tuple
import math
import time

from pymodaq.control_modules.move_utility_classes import (
    DAQ_Move_base,
    DataActuatorType,
    comon_parameters_fun,
    main
)
from pymodaq.utils.parameter import Parameter

from pymeasure.adapters import VISAAdapter, PrologixAdapter
import pyvisa

from pymeasure.instruments.agilent import Agilent8257D


rm = pyvisa.ResourceManager()
VISA_RESOURCES = rm.list_resources()
ADAPTERS = dict(VISA=VISAAdapter, Prologix=PrologixAdapter)


class DAQ_Move_RFSource_E8257D(DAQ_Move_base):
    """
    PyMoDAQ 5 plugin for Agilent / Keysight E8257D

    Axis 0: Frequency (GHz)
    Axis 1: Power (W)
    """

    _controller_units = ['GHz', 'W']
    _axis_names = ['Freq', 'Pow']
    is_multiaxes = True

    data_actuator_type = DataActuatorType.float
    _epsilon = 1e-12

    FREQ_MIN_GHZ = 0.1
    FREQ_MAX_GHZ = 20.0

    POW_MIN_DBM = -60.0
    POW_MAX_DBM = 18.0

    POW_MIN_W = 1e-9
    POW_MAX_W = 0.064

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

    def ini_attributes(self) -> None:
        self.controller: Agilent8257D | None = None
        self._cached_freq = self.FREQ_MIN_GHZ
        self._cached_pow = self.POW_MIN_W

    def get_actuator_value(self):
        """
        IMPORTANT:
        Do NOT query the instrument continuously (polling) during scans.
        Only return cached values.
        """
        if self.axis_value == 'Freq':
            return self._cached_freq
        elif self.axis_value == 'Pow':
            return self._cached_pow
        return 0.0

    def close(self) -> None:
        if self.controller is not None:
            self.controller.shutdown()

    def commit_settings(self, param: Parameter) -> None:
        if param.name() == "output":
            self.controller.enable() if param.value() else self.controller.disable()

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

    def move_abs(self, val: float):
        val = self.check_bound(val)
        val = self.set_position_with_scaling(val)

        if self.axis_value == 'Freq':
            self.controller.frequency = val * 1e9
            self._cached_freq = val

        elif self.axis_value == 'Pow':
            pow_dbm = 10 * math.log10(val / 1e-3)
            if pow_dbm < self.POW_MIN_DBM:
                pow_dbm = self.POW_MIN_DBM
            elif pow_dbm > self.POW_MAX_DBM:
                pow_dbm = self.POW_MAX_DBM

            self.controller.power = pow_dbm
            self._cached_pow = val

        time.sleep(0.05)

        self.current_value = val
        self.target_position = val

    def move_rel(self, val: float) -> None:
        self.move_abs(self.current_value + val)

    def move_home(self):
        if self.axis_value == 'Freq':
            self.move_abs(self.FREQ_MIN_GHZ)
        elif self.axis_value == 'Pow':
            self.move_abs(self.POW_MIN_W)

    def stop_motion(self):
        self.controller.disable()


if __name__ == '__main__':
    main(__file__)
