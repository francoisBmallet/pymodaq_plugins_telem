from pymodaq.control_modules.move_utility_classes import DAQ_Move_base, comon_parameters_fun, main, DataActuatorType,\
    DataActuator  # common set of parameters for all actuators
from pymodaq.utils.daq_utils import ThreadCommand # object used to send info back to the main thread
from pymodaq.utils.parameter import Parameter



from pymeasure.instruments.yokogawa import Yokogawa7651

from pyvisa import ResourceManager

VISA_rm = ResourceManager()
devices = list(VISA_rm.list_resources())
device = 'GPIB0::1::INSTR'

from pymeasure.instruments import list_resources

from easydict import EasyDict as edict

_controller_units = ''
_epsilon = 1e-6
is_multiaxes = False
stage_names = []
axes_names = ['Voltage', 'Current']  # TODO for your plugin: complete the list
_epsilon = 1e-6

SOURCE_MODES = ['current', 'voltage']

VRANGE = [
        '30V', '10V', '1V', '.1V', '.01V'
            ]
VRANGE_NUM = [
        30, 10, 1, .1, .01
            ]
IRANGE = [
        '0.2A', '0.1A', '0.01A', '0.001A'
            ]
IRANGE_NUM = [
        .2, .1, .01, .001
            ]

class DAQ_Move_DCSource_Yoko7651_legacy(DAQ_Move_base):
    """Plugin for the Template Instrument

    This object inherits all functionality to communicate with PyMoDAQ Module through inheritance via DAQ_Move_base
    It then implements the particular communication with the instrument

    Attributes:
    -----------
    controller: object
        The particular object that allow the communication with the hardware, in general a python wrapper around the
         hardware library

    """
    params = [
                 #{'title': 'Address:', 'name': 'address', 'type': 'list', 'limits': list_resources(), 'value': 'GPIB0::1::INSTR'},
                 {'title': 'VISA:', 'name': 'address', 'type': 'list', 'limits': devices, 'value': device},
                 {'title': 'ID:', 'name': 'id', 'type': 'str'},
                 {'title': 'Output:', 'name': 'output', 'type': 'led_push', 'value': False},
                 {'title': 'Source Mode:', 'name': 'source_mode', 'type': 'list', 'limits': SOURCE_MODES},
                 {'title': 'Voltage Range:', 'name': 'voltage_range', 'type': 'list', 'limits': VRANGE},
                 {'title': 'Current Range:', 'name': 'current_range', 'type': 'list', 'limits': IRANGE},
             ] + comon_parameters_fun(is_multiaxes, axes_names, epsilon=_epsilon)

    def ini_attributes(self):
        self.controller: Yokogawa7651 = None


    def get_actuator_value(self):
        """Get the current value from the hardware with scaling conversion.

        Returns
        -------
        float: The position obtained after scaling conversion.
        """
        ## TODO for your custom plugin
        #raise NotImplemented  # when writing your own plugin remove this line
        #pos = self.controller.your_method_to_get_the_actuator_value()  # when writing your own plugin replace this line
        level = 0
        level = self.controller.source_level
        level = self.get_position_with_scaling(level)
        #self.emit_status(ThreadCommand('check_position', [level]))
        return level


    def close(self):
        """Terminate the communication protocol"""
        ## TODO for your custom plugin
        #raise NotImplemented  # when writing your own plugin remove this line
        #  self.controller.your_method_to_terminate_the_communication()  # when writing your own plugin replace this line
        self.controller.shutdown()

    def commit_settings(self, param: Parameter):
        """Apply the consequences of a change of value in the detector settings

        Parameters
        ----------
        param: Parameter
            A given parameter (within detector_settings) whose value has been changed by the user
        """
        pass
        ## TODO for your custom plugin
        #if param.name() == "a_parameter_you've_added_in_self.params":
           #self.controller.your_method_to_apply_this_param_change()
        #else:
        #    pass
        if param.name() == "output":
            state = param.value()
            if state == 0:
                self.controller.disable_source()
            else:
                self.controller.enable_source()

        if param.name() == "source_mode":
            self.controller.disable_source()
            state = param.value()
            if state == 'current':
                self.controller.apply_current()
                self.controller.source_current = 0
            else:
                self.controller.apply_voltage()
                self.controller.source_voltage = 0
            pass

        if param.name() == "voltage_range":
            if self.axis_value == 'Voltage':
                for i in range(len(VRANGE)):
                    if param.value() == VRANGE[i]:
                        self.controller.source_voltage_range = VRANGE_NUM[i]
                pass
            pass

        if param.name() == "current_range":
            if self.axis_value == 'Current':
                for i in range(len(IRANGE)):
                    if param.value() == IRANGE[i]:
                        self.controller.source_current_range = IRANGE_NUM[i]
                pass
            pass




    def ini_stage(self, controller=None):
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

        #raise NotImplemented  # TODO when writing your own plugin remove this line and modify the one below




        try:
            self.status.update(edict(info="", controller=None, initialized=False))

            if self.settings.child('multiaxes', 'ismultiaxes').value() and self.settings.child('multiaxes',
                                                                                               'multi_status').value() == "Slave":
                if controller is None:
                    raise Exception('no controller has been defined externally while this axe is a slave one')
                else:
                    self.controller = controller
            else:  # Master stage
                pass
            info = self.ini_stage_init(old_controller=controller,
                                      new_controller=Yokogawa7651(self.settings['address']))

        #info = "Whatever info you want to log"
        #initialized = self.controller.a_method_or_atttribute_to_check_if_init()  # todo
            self.settings.child('id').setValue(info)
            initialized = True
            return info, initialized

        except Exception as e:
            self.emit_status(ThreadCommand('Update_Status', [getLineInfo() + str(e), 'log']))
            self.status.info = getLineInfo() + str(e)
            self.status.initialized = False
            return self.status

    def move_abs(self, value):
        """ Move the actuator to the absolute target defined by value

        Parameters
        ----------
        value: (float) value of the absolute target positioning
        """

        value = self.check_bound(value)  #if user checked bounds, the defined bounds are applied here
        self.target_value = value
        value = self.set_position_with_scaling(value)  # apply scaling if the user specified one
        self.controller.source_level = value  # when writing your own plugin replace this line
        self.emit_status(ThreadCommand('Update_Status', ['move_abs ok']))
        ##############################

        self.target_position = value
        self.poll_moving()


    def move_rel(self, value):
        """ Move the actuator to the relative target actuator value defined by value

        Parameters
        ----------
        value: (float) value of the relative target positioning
        """
        value = self.check_bound(self.current_position + value) - self.current_position
        self.target_value = value + self.current_position
        value = self.set_position_relative_with_scaling(value)
        self.controller.source_level = value  # when writing your own plugin replace this line
        self.emit_status(ThreadCommand('Update_Status', ['move_rel ok']))
        ##############################

        self.target_position = value
        self.poll_moving()

    def move_home(self):
        """Call the reference method of the controller"""

        ## TODO for your custom plugin
        raise NotImplemented  # when writing your own plugin remove this line
        self.controller.source_level = 0  # when writing your own plugin replace this line
        self.emit_status(ThreadCommand('Update_Status', ['Move home ok']))

    def stop_motion(self):
      """Stop the actuator and emits move_done signal"""

      self.source_enabled = False  # when writing your own plugin replace this line
      self.emit_status(ThreadCommand('Update_Status', ['stop ok']))
      self.move_done()


if __name__ == '__main__':
    main(__file__)
