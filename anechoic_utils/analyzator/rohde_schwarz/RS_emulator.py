from typing import List, Union
from .rohde_schwarz import RohdeSchwarzAnalyzer
import numpy as np
from time import sleep


class RohdeSchwarzEmulator(RohdeSchwarzAnalyzer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.freq_start = None
        self.freq_stop = None
        self.freq_num = None
        self.channel = 1

    def set_settings(
            self,
            channel: int = None,
            freq_start: float = None,
            freq_stop: float = None,
            freq_num: int = None
    ) -> None:
        if channel is not None:
            self.channel = channel
        if freq_start is not None:
            self.freq_start = freq_start
        if freq_stop is not None:
            self.freq_stop = freq_stop
        if freq_num is not None:
            self.freq_num = freq_num

    def connect(self) -> None:
        self._set_is_connected(True)

    def disconnect(self) -> None:
        self._set_is_connected(False)

    def get_scattering_parameters(
            self,
            parameters: List[str]
    ) -> dict[str: List[float]]:

        res = {}

        if not self.is_connected:
            return

        res[f'f'] = np.linspace(self.freq_start, self.freq_stop, int(self.freq_num))

        for num, S_param in enumerate(parameters):
            trace_tup = np.linspace(0, 4*np.pi, int(self.freq_num))
            res[f'{S_param}'] = np.sin(trace_tup) + np.random.normal(0, 0.1, int(self.freq_num))

        self._signals.data.emit(res)
        sleep(0.9)
        return res
