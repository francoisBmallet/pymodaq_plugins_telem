from typing import Tuple

import pyvisa
import numpy as np

from pymeasure.adapters import VISAAdapter, PrologixAdapter

from pymodaq.control_modules.viewer_utility_classes import (
    DAQ_Viewer_base,
    comon_parameters,
    main
)
from pymodaq.utils.parameter import Parameter, utils
from pymodaq.utils.data import DataFromPlugins, DataToExport

from pyqtgraph.parametertree.Parameter import registerParameterType
from pyqtgraph.parametertree.parameterTypes.basetypes import GroupParameter

from pymodaq_plugins_telem.hardware.agilent_34A_thread_safe import Agilent34AThreadSafe
CHANNELS = ['voltage', 'voltage_ac', 'current', 'current_ac', 'resistance', 'resistance_4w']
MODE_MAP = {
    "voltage": "voltage",
    "voltage_ac": "ac voltage",
    "current": "current",
    "current_ac": "ac current",
    "resistance": "resistance",
    "resistance_4w": "4w resistance",
}
rm = pyvisa.ResourceManager()
VISA_RESOURCES = rm.list_resources()
ADAPTERS = dict(VISA=VISAAdapter, Prologix=PrologixAdapter)


for channel in CHANNELS:
    assert hasattr(Agilent34AThreadSafe, channel)

class ChannelGroup(GroupParameter):
    """Group Parameter listing the different output
    """

    def __init__(self, **opts) -> None:
        opts['type'] = 'agilent34Achannel'
        opts['addText'] = "Add Channel"
        super().__init__(**opts)

    def addNew(self) -> None:
        """Add new channel to viewer
        """
        name_prefix = 'Agilent34ACh'

        child_indexes = [int(par.name()[len(name_prefix) + 1:])
                         for par in self.children()]

        if child_indexes == []:
            newindex = 0
        else:
            newindex = max(child_indexes) + 1

        child = {
            'title': f'Measure {newindex:02.0f}',
            'name': f'{name_prefix}{newindex:02.0f}',
            'type': 'itemselect',
            'removable': True,
            # FIX → selected must be a list, NOT a string
            'value': dict(all_items=CHANNELS, selected=[CHANNELS[0]])
        }

        self.addChild(child)


registerParameterType('agilent34Achannel', ChannelGroup, override=True)


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
                 {'title': 'Channels:', 'name': 'channels', 'type': 'agilent34Achannel'}
             ] + comon_parameters + [
                {'title': 'Configuration:', 'name': 'config', 'type': 'group', 'children': [
                {'title': 'Reset:', 'name': 'reset', 'type': 'bool_push', 'value': False},
                {'title': 'Setup number:', 'name': 'setup_number', 'type': 'int', 'value': 1, 'min': 1, 'max': 9},
                {'title': 'Save setup:', 'name': 'save_setup', 'type': 'bool_push', 'value': False,'label': 'Save'},
                {'title': 'Load setup:', 'name': 'load_setup', 'type': 'bool_push', 'value': False,'label': 'Load'}
                ]},
    ]

    def ini_attributes(self):
        self.controller: Agilent34AThreadSafe = None

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

        elif param.name() in utils.iter_children(

                self.settings.child('channels'), []):

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

                name="agilent34A",

                data=data

            ))

        elif param.name() == 'reset':
            self.controller.reset()
            param.setValue(False)


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
            self.controller = Agilent34AThreadSafe(adapter)

        self.dte_signal_temp.emit(
            DataToExport(
                name="agilent34A",
                data=[
                    DataFromPlugins(
                        name="agilent34A",
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
        data = []

        for child in self.settings.child('channels').children():
            labels = child.value()['selected'][:]

            subdata = []

            for label in labels:
                mode = MODE_MAP[label]

                # Only change mode if it is different
                if getattr(self.controller, "mode") != mode:
                    self.controller.mode = mode

                value = getattr(self.controller, label)  # thread-safe wrapper
                subdata.append(np.array([value]))

            data.append(DataFromPlugins(
                name=child.name(),
                data=subdata,
                labels=labels,
                dim='Data0D'
            ))

        self.dte_signal.emit(DataToExport(
            name="agilent34A",
            data=data
        ))

    def stop(self):
        """Stop the current grab hardware wise if necessary"""
        return ''


if __name__ == '__main__':
    main(__file__, init=False)