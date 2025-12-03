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
import math

from pymeasure.instruments.anapico import APSIN12G
rm = pyvisa.ResourceManager()
VISA_RESOURCES = rm.list_resources()
ADAPTERS = dict(VISA=VISAAdapter, Prologix=PrologixAdapter)

class DAQ_Move_RFSource_AP5011A(DAQ_Move_base):
    _controller_units = [ 'Hz','W']
    _epsilon = 1e-6
    is_multiaxes = True
    _axis_names = [ 'Freq','Pow']
    data_actuator_type = DataActuatorType.DataActuator


    params = [
                 {'title': 'Adapter', 'name': 'adapter', 'type': 'list','limits': list(ADAPTERS.keys())},
                 {'title': 'VISA Address:', 'name': 'address', 'type': 'list','limits': VISA_RESOURCES},
                 {'title': 'Output', 'name': 'output', 'type': 'bool','value': False}
             ] + comon_parameters_fun(is_multiaxes, axis_names=_axis_names, epsilon=_epsilon)

    def ini_attributes(self) -> None:
        self.controller: APSIN12G = None


    def get_actuator_value(self) -> DataActuator:
        """Get the current value from the hardware with scaling conversion.

        Returns
        -------
        float: The position obtained after scaling conversion.
        """
        ## TODO for your custom plugin
        if self.axis_value == 'Freq':
            val = DataActuator(data=self.controller.frequency)
            val = self.get_position_with_scaling(val)
        if self.axis_value == 'Pow':
            valdB = DataActuator(data=self.controller.power)
            val = 10**(valdB / 10) * 1e-3
        return val


    def close(self) -> None:
        """Terminate the communication protocol"""
        self.controller.shutdown()

    def commit_settings(self, param: Parameter) -> None:
        """Apply the consequences of a change of value in the detector settings

        Parameters
        ----------
        param: Parameter
            A given parameter (within detector_settings) whose value has been changed by the user
        """
        if param.name() == "output":
            state = param.value()
            if state == True:
                self.controller.enable_rf()
            else:
                self.controller.disable_rf()

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
            self.controller = APSIN12G(adapter)

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

        val = self.check_bound(val)
        val = self.set_position_with_scaling(val)#if user checked bounds, the defined bounds are applied here
        if self.axis_value == 'Freq':  # Amp axis
            self.controller.frequency = val.value()
        elif self.axis_value == 'Pow':  # Frequency axis
            valdB = 10 * math.log10(val.value() / 1e-3)
            self.controller.power = valdB
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
        self.controller.source_level = -40

    def stop_motion(self):
      """Stop the actuator and emits move_done signal"""
      self.source_enabled = False  # when writing your own plugin replace this line



if __name__ == '__main__':
    main(__file__)
