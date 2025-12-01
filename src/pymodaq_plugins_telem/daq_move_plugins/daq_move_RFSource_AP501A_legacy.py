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

from pymeasure.instruments.anapico import APSIN12G

import pyvisa
rm = pyvisa.ResourceManager()
VISA_RESOURCES = rm.list_resources()
ADAPTERS = dict(VISA=VISAAdapter, Prologix=PrologixAdapter)


# TODO:

class DAQ_Move_RFSource_AP510A(DAQ_Move_base):
    _controller_units = ['V' ,'A']
    _epsilon = 1e-6
    is_multiaxes = True
    _axis_names = [ 'voltage','current']
    data_actuator_type = DataActuatorType.DataActuator

    params = [
                 {'title': 'Adapter', 'name': 'adapter', 'type': 'list',
                  'limits': list(ADAPTERS.keys())},
                 {'title': 'VISA Address:', 'name': 'address', 'type': 'list',
                  'limits': VISA_RESOURCES},
                 {'title': 'Output:', 'name': 'output', 'type': 'led_push', 'value': False},
             ] + comon_parameters_fun(is_multiaxes, axis_names=_axis_names, epsilon=_epsilon)


    def ini_attributes(self):
        #  TODO declare the type of the wrapper (and assign it to self.controller) you're going to use for easy
        #  autocompletion
        self.controller: APSIN12G = None

        #TODO declare here attributes you want/need to init with a default value
        pass

    def get_actuator_value(self) -> DataActuator:
        """Get the current value from the hardware with scaling conversion.

        Returns
        -------
        float: The position obtained after scaling conversion.
        """
        raise NotImplemented

    def close(self):
        """Terminate the communication protocol"""
        raise NotImplemented

    def commit_settings(self, param: Parameter)-> None:
        """Apply the consequences of a change of value in the detector settings

        Parameters
        ----------
        param: Parameter
            A given parameter (within detector_settings) whose value has been changed by the user
        """
        ## TODO for your custom plugin
        raise NotImplemented

    def ini_stage(self, controller=None)-> Tuple[str, bool]:
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

    def move_abs(self, f: DataActuator) -> None:
        """ Move the actuator to the absolute target defined by value

        Parameters
        ----------
        value: (float) value of the absolute target positioning
        """
        raise NotImplemented

    def move_rel(self, f: DataActuator)-> None:
        """ Move the actuator to the relative target actuator value defined by value

        Parameters
        ----------
        value: (float) value of the relative target positioning
        """
        raise NotImplemented

    def move_home(self):
        """Call the reference method of the controller"""
        raise NotImplemented

    def stop_motion(self):
      """Stop the actuator and emits move_done signal"""
      raise NotImplemented

if __name__ == '__main__':
    main(__file__, init=False)
