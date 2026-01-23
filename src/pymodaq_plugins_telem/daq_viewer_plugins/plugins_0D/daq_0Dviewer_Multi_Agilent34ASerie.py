from typing import Tuple

import pyvisa
import time
import numpy as np

from pymeasure.adapters import VISAAdapter, PrologixAdapter

from pymodaq.control_modules.viewer_utility_classes import (
    DAQ_Viewer_base,
    comon_parameters,
    main
)
from pymodaq.utils.parameter import Parameter
from pymodaq.utils.data import DataFromPlugins, DataToExport

from pymodaq_plugins_telem.hardware.agilent_34A_thread_safe import Agilent34athreadsafe


# -----------------------------------------------------------------------------
# CHANNEL DEFINITIONS
# -----------------------------------------------------------------------------

CHANNELS = ['voltage', 'voltage_ac', 'current', 'current_ac', 'resistance', 'resistance_4w']

MODE_MAP = {
    "voltage": "voltage",
    "voltage_ac": "ac voltage",
    "current": "current",
    "current_ac": "ac current",
    "resistance": "resistance",
    "resistance_4w": "4w resistance",
}

UNIT_MAP = {
    "voltage": "V",
    "voltage_ac": "V",
    "current": "A",
    "current_ac": "A",
    "resistance": "Ω",
    "resistance_4w": "Ω",
}


# -----------------------------------------------------------------------------
# VISA
# -----------------------------------------------------------------------------

rm = pyvisa.ResourceManager()
VISA_RESOURCES = rm.list_resources()

ADAPTERS = dict(
    VISA=VISAAdapter,
    Prologix=PrologixAdapter
)


# -----------------------------------------------------------------------------
# MAIN PLUGIN CLASS
# -----------------------------------------------------------------------------

class DAQ_0DViewer_Multi_Agilent34ASerie(DAQ_Viewer_base):
    """Single-channel Agilent 34A PyMoDAQ Viewer with unit display"""

    params = [
        {'title': 'Adapter', 'name': 'adapter', 'type': 'list',
         'limits': list(ADAPTERS.keys())},

        {'title': 'VISA Address:', 'name': 'address', 'type': 'list',
         'limits': VISA_RESOURCES},

        {'title': 'ID:', 'name': 'id', 'type': 'str'},

        # ✅ SINGLE CHANNEL SELECTION
        {'title': 'Channel:', 'name': 'channel', 'type': 'list',
         'limits': CHANNELS},

        # ✅ UNIT DISPLAY (READ ONLY)
        {'title': 'Unit:', 'name': 'unit', 'type': 'str', 'readonly': True},

    ] + comon_parameters + [

        {'title': 'Configuration:', 'name': 'config', 'type': 'group', 'children': [
            {'title': 'Reset:', 'name': 'reset', 'type': 'bool_push', 'value': False},
            {'title': 'Setup number:', 'name': 'setup_number', 'type': 'int', 'value': 1, 'min': 1, 'max': 9},
            {'title': 'Save setup:', 'name': 'save_setup', 'type': 'bool_push', 'value': False, 'label': 'Save'},
            {'title': 'Load setup:', 'name': 'load_setup', 'type': 'bool_push', 'value': False, 'label': 'Load'}
        ]},
    ]


    # -------------------------------------------------------------------------
    # INIT
    # -------------------------------------------------------------------------

    def ini_attributes(self):
        self.controller: Agilent34athreadsafe = None


    # -------------------------------------------------------------------------
    # PARAMETER CHANGES
    # -------------------------------------------------------------------------

    def commit_settings(self, param: Parameter):

        if param.name() == 'load_setup':
            self.controller.load_setup(self.settings['config', 'setup_number'])
            param.setValue(False)

        elif param.name() == 'save_setup':
            self.controller.save_setup(self.settings['config', 'setup_number'])
            param.setValue(False)

        elif param.name() == 'reset':
            self.controller.reset()
            param.setValue(False)

        # ✅ UPDATE UNIT WHEN CHANNEL CHANGES
        elif param.name() == 'channel':

            label = self.settings['channel']
            unit = UNIT_MAP[label]

            # ✅ Update unit display
            self.settings.child('unit').setValue(unit)

            # ✅ SET MODE HERE (ONCE, SAFELY)
            mode = MODE_MAP[label]
            try:
                if self.controller is not None:
                    self.controller.mode = mode
                    time.sleep(2)
                    try:
                        self.controller.adapter.connection.clear()  # flush VISA buffer
                    except Exception:
                        pass
            except Exception as e:
                self.emit_status(
                    ThreadCommand(
                        'Update_Status',
                        [f"Mode change failed: {e}", "log"]
                    )
                )

            # ✅ Update temporary data structure for PyMoDAQ
            self.dte_signal_temp.emit(
                DataToExport(
                    name="agilent34A",
                    data=[
                        DataFromPlugins(
                            name="agilent34A",
                            data=[np.array([0])],
                            labels=[f"{label} ({unit})"],
                            dim="Data0D"
                        )
                    ]
                )
            )

    # -------------------------------------------------------------------------
    # INITIALIZATION
    # -------------------------------------------------------------------------

    def ini_detector(self, controller=None):

        self.ini_detector_init(slave_controller=controller)

        if self.is_master:
            adapter = ADAPTERS[self.settings['adapter']](
                self.settings['address']
            )
            self.controller = Agilent34athreadsafe(adapter)

        # Initialize unit display
        label = self.settings['channel']
        self.settings.child('unit').setValue(UNIT_MAP.get(label, ""))

        self.dte_signal_temp.emit(
            DataToExport(
                name="agilent34A",
                data=[
                    DataFromPlugins(
                        name="agilent34A",
                        data=[np.array([0])],
                        labels=[label],
                        dim="Data0D"
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


    # -------------------------------------------------------------------------
    # DATA ACQUISITION
    # -------------------------------------------------------------------------

    def grab_data(self, Naverage=1, **kwargs):

        label = self.settings['channel']
        unit = UNIT_MAP[label]
        value=self.controller.voltage

        self.dte_signal.emit(
            DataToExport(
                name="agilent34A",
                data=[
                    DataFromPlugins(
                        name="agilent34A",
                        data=[np.array([value])],
                        labels=[f"{label} ({unit})"],
                        dim="Data0D"
                    )
                ]
            )
        )

    # -------------------------------------------------------------------------
    # STOP
    # -------------------------------------------------------------------------

    def stop(self):
        return ''


    # -------------------------------------------------------------------------
    # CLOSE
    # -------------------------------------------------------------------------

    def close(self):
        if self.controller is not None:
            self.controller.clear()
            self.controller.shutdown()


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    main(__file__, init=False)
