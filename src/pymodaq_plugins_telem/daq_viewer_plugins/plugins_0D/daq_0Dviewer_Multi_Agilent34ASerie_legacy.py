from typing import List
#from time import perf_counter
#from qtpy.QtCore import QThread
import numpy as np
#from pymodaq.utils.daq_utils import ThreadCommand
from pymodaq.utils.data import DataFromPlugins, DataToExport
from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, comon_parameters, main
from pymodaq.utils.parameter import Parameter

from pymeasure.instruments.agilent.agilent34450A import Agilent34450A
from pymeasure.adapters import VISAAdapter, PrologixAdapter
from pyvisa import ResourceManager

import pyvisa

CHANNELS = {'voltage', 'ac voltage', 'current', 'ac current', 'resistance', '4w resistance'}
rm = pyvisa.ResourceManager()
VISA_RESOURCES = rm.list_resources()
ADAPTERS = dict(VISA=VISAAdapter, Prologix=PrologixAdapter)
class DAQ_0DViewer_Multi_Agilent34ASerie_legacy(DAQ_Viewer_base):
    """ Instrument plugin class for a OD viewer.

    This object inherits all functionalities to communicate with PyMoDAQ’s DAQ_Viewer module through inheritance via
    DAQ_Viewer_base. It makes a bridge between the DAQ_Viewer module and the Python wrapper of a particular instrument.

    Attributes:
    -----------
    controller: object
        The particular object that allow the communication with the hardware, in general a python wrapper around the
         hardware library.

    """


    params = comon_parameters + [
        {'title': 'VISA:', 'name': 'address', 'type': 'list', 'limits': devices},
        #{'title': 'Address:', 'name': 'address', 'type': 'list', 'limits': list_resources(), 'value': 'GPIB0::24::INSTR'},
        {'title': 'Mode:', 'name': 'mode', 'type': 'list', 'limits': channels, 'value': 'voltage'},
        {'title': 'ID:', 'name': 'id', 'type': 'str', 'value': ""},
        {'title': 'Acquisition:', 'name': 'acq', 'type': 'group', 'children': [
            {'title': 'Use Trigger:', 'name': 'trigger', 'type': 'bool', 'value': False},
            #{'title': 'Channels in separate viewer:', 'name': 'separate_viewers', 'type': 'bool', 'value': False},
           # {'title': 'Channels:', 'name': 'channels', 'type': 'itemselect',
             #'value': dict(all_items=channels, selected=['ac voltage'])},
        ]},
        {'title': 'Configuration:', 'name': 'config', 'type': 'group', 'children': [
            {'title': 'Reset:', 'name': 'reset', 'type': 'bool_push', 'value': False},
            {'title': 'Setup number:', 'name': 'setup_number', 'type': 'int', 'value': 1, 'min': 1, 'max': 9},
            {'title': 'Save setup:', 'name': 'save_setup', 'type': 'bool_push', 'value': False,
             'label': 'Save'},
            {'title': 'Load setup:', 'name': 'load_setup', 'type': 'bool_push', 'value': False,
             'label': 'Load'},
        ]},
    ]

    def ini_attributes(self):
        self.controller: Agilent34450A = None

    def commit_settings(self, param: Parameter):
        """Apply the consequences of a change of value in the detector settings

        Parameters
        ----------
        param: Parameter
            A given parameter (within detector_settings) whose value has been changed by the user
        """
        if param.name() == 'load_setup':
            self.controller.load_setup(self.settings['config', 'setup_number'])
            param.setValue(False)

        elif param.name() == 'save_setup':
            self.controller.save_setup(self.settings['config', 'setup_number'])
            param.setValue(False)

        elif param.name() == 'channels':
            selected_channels = param.value()['selected']
            data_list_array = [np.array([0.]) for _ in range(len(selected_channels))]
            dwas = self.create_dwas(data_list_array)
            self.dte_signal.emit(DataToExport(name='SR830', data=dwas))

        elif param.name() == 'reset':
            self.controller.reset()
            param.setValue(False)

        elif param.name() == 'mode':
            self.controller.mode = param.value()

    def ini_detector(self, controller=None):
        """Detector communication initialization

        Parameters
        ----------
        controller: (object)
            custom object of a PyMoDAQ plugin (Slave case). None if only one actuator/detector by controller
            (Master case)

        Returns
        -------
        info: str
        initialized: bool
            False if initialization failed otherwise True
        """

        if self.settings['controller_status'] == "Slave":
            if controller is None:
                raise Exception('no controller has been defined externally while this axe is a slave one')
            else:
                controller = controller
        else:  # Master stage
            controller = Agilent34450A(self.settings['address'])
        self.controller = controller

        info = self.controller.id
        self.settings.child('id').setValue(info)
        #print(self.settings['mode'])
        #self.controller.mode = self.settings['mode']
        initialized = True
        return info, initialized

    def close(self):
        """Terminate the communication protocol"""
        if self.controller is not None:
            self.controller.clear()
            self.controller.shutdown()

    def grab_data(self, Naverage=1, **kwargs):
        """Start a grab from the detector

        Parameters
        ----------
        Naverage: int
            Number of hardware averaging (if hardware averaging is possible, self.hardware_averaging should be set to
            True in class preamble and you should code this implementation)
        kwargs: dict
            others optionals arguments
        """
        data_tot = self.controller.voltage
        self.dte_signal.emit(DataToExport(name='Agilent34401A',
                                          data=[DataFromPlugins(name='Agilent34401A', data=data_tot,
                                                                dim='Data0D', labels=['data0', 'data1'])]))

    def stop(self):
        """Stop the current grab hardware wise if necessary"""
        return ''


if __name__ == '__main__':
    main(__file__, init=False)