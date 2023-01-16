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

        freq_tup = tuple(np.zeros(self.freq_num))
        res[f'f'] = np.array(freq_tup).astype(float)

        for num, S_param in enumerate(parameters):
            trace_tup = tuple(np.zeros(self.freq_num))
            res[f'{S_param}'] = np.array(trace_tup).astype(float)

        self._signals.data.emit((res['f'], *(res[f'{S_param}'] for S_param in parameters)), )
        sleep(0.2)
        return res
