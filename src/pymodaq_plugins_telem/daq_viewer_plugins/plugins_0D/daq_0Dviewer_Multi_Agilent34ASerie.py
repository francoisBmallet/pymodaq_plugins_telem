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

class DAQ_0DViewer_Multi_Agilent34ASerie(DAQ_Viewer_base):
    """ Instrument plugin class for a OD viewer.

    This object inherits all functionalities to communicate with PyMoDAQ’s DAQ_Viewer module through inheritance via
    DAQ_Viewer_base. It makes a bridge between the DAQ_Viewer module and the Python wrapper of a particular instrument.

    Attributes:
    -----------
    controller: object
        The particular object that allow the communication with the hardware, in general a python wrapper around the
         hardware library.

    """

    params = [
                 {'title': 'Adapter', 'name': 'adapter', 'type': 'list',
                  'limits': list(ADAPTERS.keys())},
                 {'title': 'VISA Address:', 'name': 'address', 'type': 'list',
                  'limits': VISA_RESOURCES},
                 {'title': 'ID:', 'name': 'id', 'type': 'str'},
                 {'title': 'Channels:', 'name': 'channels', 'type': 'list', 'limits' : CHANNELS }
             ] + comon_parameters + [
                {'title': 'Configuration:', 'name': 'config', 'type': 'group', 'children': [
                {'title': 'Reset:', 'name': 'reset', 'type': 'bool_push', 'value': False},
                {'title': 'Setup number:', 'name': 'setup_number', 'type': 'int', 'value': 1, 'min': 1, 'max': 9},
                {'title': 'Save setup:', 'name': 'save_setup', 'type': 'bool_push', 'value': False,'label': 'Save'},
                {'title': 'Load setup:', 'name': 'load_setup', 'type': 'bool_push', 'value': False,'label': 'Load'}
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
            data = []
            for child in self.settings.child('channels').children():
                labels = child.value()['selected']
                data.append(
                    DataFromPlugins(
                        name=child.name(),
                        data=[np.array([0]) for _ in labels],
                        labels=labels,
                        dim='Data0D'
                    )
                )
            self.dte_signal_temp.emit(DataToExport(
                name="Agilent34ASerie",
                data=data
            ))

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

        self.ini_detector_init(slave_controller=controller)

        if self.is_master:
            adapter = ADAPTERS[self.settings.child('adapter').value()](
                self.settings.child('address').value()
            )
            self.controller = Agilent34450A(adapter)

        self.dte_signal_temp.emit(
            DataToExport(
                name="Agilent34ASerie",
                data=[
                    DataFromPlugins(
                        name="Agilent34ASerie",
                        data=[np.array([0])],
                        dim="Data0D",
                        labels=["x"]
                    )
                ]
            )
        )

        try:
            info = self.controller.id
            initialized = True
        except:
            info = ""
            initialized = False

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
                                                                dim='Data0D', labels=['data0'])]))

    def stop(self):
        """Stop the current grab hardware wise if necessary"""
        return ''


if __name__ == '__main__':
    main(__file__, init=False)