from pymeasure.instruments import Instrument, SCPIUnknownMixin
from pymeasure.instruments.validators import strict_range, strict_discrete_set


class AP5011A(SCPIUnknownMixin, Instrument):
    """ Represents the Anapico APSIN12G Signal Generator updated for 20 GHz max. """

    # Updated limits
    FREQ_LIMIT = [9e3, 20e9]  # 9 kHz → 20 GHz
    POW_LIMIT = [-30, 27]  # dBm, adjust if needed

    def __init__(self, adapter, name="Anapico APSIN12G Signal Generator", **kwargs):
        super().__init__(adapter, name, **kwargs)

    # Power control (dBm)
    power = Instrument.control(
        "SOUR:POW:LEV:IMM:AMPL?;", "SOUR:POW:LEV:IMM:AMPL %gdBm;",
        """Control the output power in dBm. (float)""",
        validator=strict_range,
        values=POW_LIMIT
    )

    # Frequency control (Hz)
    frequency = Instrument.control(
        "SOUR:FREQ:CW?;", "SOUR:FREQ:CW %eHz;",
        """Control the output frequency in Hz. (float)""",
        validator=strict_range,
        values=FREQ_LIMIT
    )

    # Optional additional controls
    blanking = Instrument.control(
        ":OUTP:BLAN:STAT?", ":OUTP:BLAN:STAT %s",
        """Control output blanking during frequency changes.""",
        validator=strict_discrete_set,
        values=['ON', 'OFF']
    )

    reference_output = Instrument.control(
        "SOUR:ROSC:OUTP:STAT?", "SOUR:ROSC:OUTP:STAT %s",
        """Control the 10MHz reference output.""",
        validator=strict_discrete_set,
        values=['ON', 'OFF']
    )

    # RF output
    def enable_rf(self):
        """ Enables the RF output. """
        self.write("OUTP:STAT 1")

    def disable_rf(self):
        """ Disables the RF output. """
        self.write("OUTP:STAT 0")
