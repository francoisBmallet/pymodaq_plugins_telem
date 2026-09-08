from typing import Tuple
import time

from pymodaq.control_modules.move_utility_classes import (
    DAQ_Move_base,
    DataActuator,
    DataActuatorType,
    comon_parameters_fun,
    main
)
from pymodaq.utils.parameter import Parameter
from pymodaq_utils.utils import ThreadCommand

from pymeasure.adapters import VISAAdapter, PrologixAdapter

import pyvisa

from pymeasure.instruments.yokogawa import Yokogawa7651

rm = pyvisa.ResourceManager()
VISA_RESOURCES = rm.list_resources()
ADAPTERS = dict(VISA=VISAAdapter, Prologix=PrologixAdapter)

VRANGE = {"30V": 30, "10V": 10, "1V": 1, "0.1V": 100e-3,  "0.01V": 10e-3}
IRANGE = {"0.2A": .2, "0.1A": .1, ".01A": .01, ".001A": .001}


class DAQ_Move_DCSource_Yoko7651(DAQ_Move_base):
    _controller_units = ['V', 'A']
    _epsilon = 1e-6
    is_multiaxes = True
    _axis_names = ['voltage', 'current']
    data_actuator_type = DataActuatorType.DataActuator

    params = [
        {'title': 'Adapter', 'name': 'adapter', 'type': 'list',
         'limits': list(ADAPTERS.keys())},
        {'title': 'VISA Address:', 'name': 'address', 'type': 'list',
         'limits': VISA_RESOURCES},
        {'title': 'Output', 'name': 'output', 'type': 'bool', 'value': False},
        {'title': 'Voltage Range:', 'name': 'voltage_range', 'type': 'list',
         'limits': list(VRANGE.keys())},
        {'title': 'Current Range:', 'name': 'current_range', 'type': 'list',
         'limits': list(IRANGE.keys())},

        # ---- Ramp settings -------------------------------------------------
        {'title': 'Ramp:', 'name': 'ramp', 'type': 'group', 'children': [
            {'title': 'Enable ramp:', 'name': 'ramp_enable', 'type': 'bool',
             'value': True},
            {'title': 'Ramp rate (V/s or A/s):', 'name': 'ramp_rate',
             'type': 'float', 'value': 1.0, 'min': 0.0},
            {'title': 'Step interval (s):', 'name': 'ramp_dt',
             'type': 'float', 'value': 0.05, 'min': 1e-3},
        ]},
    ] + comon_parameters_fun(is_multiaxes, axis_names=_axis_names, epsilon=_epsilon)

    def ini_attributes(self) -> None:
        self.controller: Yokogawa7651 = None
        self._stop_ramp = False

    def get_actuator_value(self) -> DataActuator:
        if self.axis_value == 'voltage':
            val = DataActuator(data=self.controller.source_voltage)
        elif self.axis_value == 'current':
            val = DataActuator(data=self.controller.source_current)
        val = self.get_position_with_scaling(val)
        return val

    def close(self) -> None:
        self.controller.shutdown()

    def commit_settings(self, param: Parameter) -> None:
        if param.name() == "output":
            state = param.value()
            if state == 0:
                self.controller.disable_source()
            else:
                self.controller.enable_source()
        if param.name() == "voltage_range":
            if self.axis_value == 'voltage':
                self.controller.source_voltage_range = VRANGE[param.value()]

        if param.name() == "current_range":
            if self.axis_value == 'current':
                self.controller.source_current_range = IRANGE[param.value()]

        if param.name() == "axis":
            if param.value() == "voltage":
                self.controller.apply_voltage()
            if param.value() == "current":
                self.controller.apply_current()

    def ini_stage(self, controller: object = None) -> Tuple[str, bool]:
        self.ini_stage_init(slave_controller=controller)

        if self.is_master:
            adapter = ADAPTERS[self.settings.child('adapter').value()](
                self.settings.child('address').value()
            )
            self.controller = Yokogawa7651(adapter)

        try:
            info = self.controller.id
            initialized = True
        except Exception:
            info = ""
            initialized = False

        return info, initialized

    # -------------------------------------------------------------------------
    # Low-level setter used by both direct move and ramp
    # -------------------------------------------------------------------------
    def _set_hw_level(self, level: float) -> None:
        if self.axis_value == 'voltage':
            self.controller.source_voltage = level
        elif self.axis_value == 'current':
            self.controller.source_current = level

    def _read_hw_level(self) -> float:
        if self.axis_value == 'voltage':
            return float(self.controller.source_voltage)
        elif self.axis_value == 'current':
            return float(self.controller.source_current)
        return 0.0

    # -------------------------------------------------------------------------
    # Ramp helper
    # -------------------------------------------------------------------------
    def _ramp_to(self, target: float) -> None:
        """Ramp the source level from the current hardware value to ``target``.

        Uses the user-defined ramp rate (units/s) and step interval (s).
        Falls back to a direct set if ramping is disabled or rate == 0.
        """
        ramp_enable = bool(self.settings['ramp', 'ramp_enable'])
        rate = float(self.settings['ramp', 'ramp_rate'])
        dt = float(self.settings['ramp', 'ramp_dt'])

        if (not ramp_enable) or rate <= 0.0 or dt <= 0.0:
            self._set_hw_level(target)
            return

        start = self._read_hw_level()
        delta = target - start
        if abs(delta) <= self._epsilon:
            self._set_hw_level(target)
            return

        step = rate * dt
        n = max(1, int(abs(delta) / step))
        # Ensure the last point is exactly ``target``
        self._stop_ramp = False
        for k in range(1, n + 1):
            if self._stop_ramp:
                self.emit_status(ThreadCommand(
                    'Update_Status', ['Yoko7651: ramp stopped by user']))
                return
            level = start + delta * (k / n)
            self._set_hw_level(level)
            time.sleep(dt)
        # Guarantee exact target at the end
        self._set_hw_level(target)

    # -------------------------------------------------------------------------
    # PyMoDAQ move API
    # -------------------------------------------------------------------------
    def move_abs(self, val):
        val = self.check_bound(val)
        val = self.set_position_with_scaling(val)
        self._ramp_to(val.value())
        self.target_position = val
        self.current_value = self.target_value

    def move_rel(self, val: DataActuator) -> None:
        val = (self.check_bound(self.current_value + val)
               - self.current_value)
        self.target_value = val + self.current_value
        val = self.set_position_relative_with_scaling(val)
        self.move_abs(self.target_value)

    def move_home(self):
        """Ramp back to 0 using the same ramp settings."""
        self._ramp_to(0.0)

    def stop_motion(self):
        """Interrupt an ongoing ramp; leaves the source at the last written level."""
        self._stop_ramp = True


if __name__ == '__main__':
    main(__file__)
