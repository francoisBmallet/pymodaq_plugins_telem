from typing import Tuple

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

from pymeasure.instruments.yokogawa import Yokogawa7651

rm = pyvisa.ResourceManager()
VISA_RESOURCES = rm.list_resources()
ADAPTERS = dict(VISA=VISAAdapter, Prologix=PrologixAdapter)
#VISA_rm = pyvisa.ResourceManager()
#devices = list(VISA_rm.list_resources())
#device = 'GPIB0::1::INSTR'

VRANGE = {"30V": 30, "10V": 10, "1V": 1, "0.1V": 100e-3,  "0.01V": 10e-3}
IRANGE = {"0.2A": .2, "0.1A": .1, ".01A": .01, ".001A": .001}

class DAQ_Move_DCSource_Yoko7651(DAQ_Move_base):
    _controller_units = [ 'V','A']
    _epsilon = 1e-6
    is_multiaxes = True
    _axis_names = [ 'voltage','current']
    data_actuator_type = DataActuatorType.DataActuator

    params = [
                 {'title': 'Adapter', 'name': 'adapter', 'type': 'list','limits': list(ADAPTERS.keys())},
                 {'title': 'VISA Address:', 'name': 'address', 'type': 'list','limits': VISA_RESOURCES},
                 #{'title': 'VISA:', 'name': 'address', 'type': 'list', 'limits': devices, 'value': device},
                 {'title': 'Output', 'name': 'output', 'type': 'bool','value': False},
                 {'title': 'Voltage Range:', 'name': 'voltage_range', 'type': 'list', 'limits': list(VRANGE.keys())},
                 {'title': 'Current Range:', 'name': 'current_range', 'type': 'list', 'limits': list(IRANGE.keys())}
             ] + comon_parameters_fun(is_multiaxes, axis_names=_axis_names, epsilon=_epsilon)

    def ini_attributes(self) -> None:
        self.controller: Yokogawa7651 = None


    def get_actuator_value(self) -> DataActuator:
        """Get the current value from the hardware with scaling conversion.

        Returns
        -------
        float: The position obtained after scaling conversion.
        """
        if self.axis_value == 'voltage':  # Amp axis
            val = DataActuator(data=self.controller.source_voltage)
        elif self.axis_value == 'current':  # Frequency axis
            val = DataActuator(data=self.controller.source_current)
        val = self.get_position_with_scaling(val)
        return val
        val = DataActuator(data=self.controller.source_level)
        val = self.get_position_with_scaling(val)
        return val


    def close(self) -> None:
        """Terminate the communication protocol"""
        ## TODO for your custom plugin
        #raise NotImplemented  # when writing your own plugin remove this line
        #  self.controller.your_method_to_terminate_the_communication()  # when writing your own plugin replace this line
        #self.controller.shutdown()

    def commit_settings(self, param: Parameter) -> None:
        """Apply the consequences of a change of value in the detector settings

        Parameters
        ----------
        param: Parameter
            A given parameter (within detector_settings) whose value has been changed by the user
        """
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
        """Actuator communication initialization

        Parameters
        ----------
        controller: (object)
            custom object of a PyMoDAQ plugin (Slave case). None if only one actuator by controller (Master case)

        Returns
        -------
        info: str
        initialized: bool
            False if initialization failed otherwise True
        """
        self.ini_stage_init(slave_controller=controller)

        if self.is_master:
            adapter = ADAPTERS[self.settings.child('adapter').value()](
                self.settings.child('address').value()
            )
            self.controller = Yokogawa7651(adapter)
            #self.controller = Yokogawa7651(self.params[0]['value'])

        try:
            info = self.controller.id
            initialized = True
        except:
            info = ""
            initialized = False

        return info, initialized

    def move_abs(self, val):
        """ Move the actuator to the absolute target defined by value

        Parameters
        ----------
        value: (float) value of the absolute target positioning
        """
        if self.axis_value == 'voltage':  # Amp axis
            val = self.check_bound(val)
            val = self.set_position_with_scaling(val)  # if user checked bounds, the defined bounds are applied here
            self.controller.source_voltage = val.value()
        elif self.axis_value == 'current':  # Frequency axis
            val = self.check_bound(val)
            val = self.set_position_with_scaling(val)  # if user checked bounds, the defined bounds are applied here
            self.controller.source_current = val.value()
        self.target_position = val
        self.current_value = self.target_value


    def move_rel(self, val: DataActuator) -> None:
        """ Move the actuator to the relative target actuator value defined by value

        Parameters
        ----------
        value: (float) value of the relative target positioning
        """
        val= (self.check_bound(self.current_value + val)
             - self.current_value)
        self.target_value = val + self.current_value
        val = self.set_position_relative_with_scaling(val)
        self.move_abs(self.target_value)

    def move_home(self):
        """Call the reference method of the controller"""
        self.controller.source_level = 0

    def stop_motion(self):
      """Stop the actuator and emits move_done signal"""
      self.source_enabled = False  # when writing your own plugin replace this line



if __name__ == '__main__':
    main(__file__)
