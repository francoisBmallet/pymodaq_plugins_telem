from typing import Tuple
import math
import time

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


rm = pyvisa.ResourceManager()
VISA_RESOURCES = rm.list_resources()
ADAPTERS = dict(VISA=VISAAdapter, Prologix=PrologixAdapter)


class DAQ_Move_RFSource_AP5011A(DAQ_Move_base):
    """
    PyMoDAQ 5 plugin for AnaPico APSIN12G

    Axis 0: Frequency (GHz)
    Axis 1: Power (W)
    """

    _controller_units = ['GHz', 'W']
    _axis_names = ['Freq', 'Pow']
    is_multiaxes = True
    data_actuator_type = DataActuatorType.DataActuator
    _epsilon = 1e-12

    FREQ_MIN_GHZ = 0.1
    FREQ_MAX_GHZ = 20.0
    POW_MIN_W = 1e-9
    POW_MAX_W = 0.316

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
        self.controller: AP5011A | None = None
        self._cached_freq = self.FREQ_MIN_GHZ
        self._cached_pow = self.POW_MIN_W

    def get_actuator_value(self) -> DataActuator:
        """
        IMPORTANT:
        Do NOT query the instrument continuously during scans.
        Only return cached values.
        """
        if self.axis_value == 'Freq':
            return DataActuator(self._cached_freq)

        elif self.axis_value == 'Pow':
            return DataActuator(self._cached_pow)

        return DataActuator(0.0)

    def close(self) -> None:
        if self.controller is not None:
            self.controller.shutdown()

    def commit_settings(self, param: Parameter) -> None:
        if param.name() == "output":
            if param.value():
                self.controller.enable_rf()
            else:
                self.controller.disable_rf()

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

    def move_abs(self, val: DataActuator):

        val = self.check_bound(val)
        val = self.set_position_with_scaling(val)

        if self.axis_value == 'Freq':
            freq_ghz = val.value()
            freq_hz = freq_ghz * 1e9
            self.controller.frequency = freq_hz
            self._cached_freq = freq_ghz

        elif self.axis_value == 'Pow':
            pow_w = val.value()
            pow_dbm = 10 * math.log10(pow_w / 1e-3)
            self.controller.power = pow_dbm
            self._cached_pow = pow_w

        time.sleep(0.05)

        self.target_position = val
        self.current_value = val

    def move_rel(self, val: DataActuator) -> None:
        val = self.check_bound(self.current_value + val) - self.current_value
        self.target_value = val + self.current_value
        val = self.set_position_relative_with_scaling(val)

        self.move_abs(self.target_value)

    def move_home(self):
        if self.axis_value == 'Freq':
            self.move_abs(DataActuator(self.FREQ_MIN_GHZ))

        elif self.axis_value == 'Pow':
            self.move_abs(DataActuator(self.POW_MIN_W))

    def stop_motion(self):
        self.controller.disable_rf()


if __name__ == '__main__':
    main(__file__)
