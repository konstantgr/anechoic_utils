import socket
import threading

from typing import List, Union
from anechoic_utils.analyzator.analyzator_parameters import (
    AnalyzatorType, ResultsFormatType, FrequencyParameters, SParameters, FrequencyTypes
)
from anechoic_utils.analyzator.base_analyzator import BaseAnalyzer
import win32com.client
import numpy as np


class PlanarAnalyzer(BaseAnalyzer):
    analyzator_type = AnalyzatorType.PLANAR

    def __init__(
            self,
            ip: str,
            port: Union[str, int],
            bufsize: int = 1024,
            maxbufs: int = 1024,
    ):
        """

        :param ip: ip адрес сканера
        :param port: порт сканера
        :param bufsize: размер чанка сообщения в байтах
        :param maxbufs: максимальное число чанков
        """
        self.ip, self.port, self.conn = ip, port, socket.socket()
        self.bufsize, self.maxbufs = bufsize, maxbufs
        self.tcp_lock = threading.Lock()
        self.is_connected = False
        self.instrument = None
        self.settings = None

    def set_settings(self, channel: int, settings: FrequencyParameters) -> None:
        self.instrument.SCPI.SYSTem.PRESet()
        self.instrument.SCPI.GetSENSe(1).FREQuency.STARt = settings.start
        self.instrument.SCPI.GetSENSe(1).FREQuency.STOP = settings.stop
        self.instrument.SCPI.GetSENSe(1).SWEep.POINts = settings.num_points
        self.settings = settings

    def connect(self) -> None:
        resource = f'TCPIP::{self.ip}::{self.port}::SOCKET'  # VISA resource string for the device
        self.instrument = win32com.client.Dispatch("S5048.Application")
        # self.instrument = win32com.client.DispatchEx("./S5048.exe")
        self.instrument.Visible = True
        self.is_connected = True

    def disconnect(self) -> None:
        if not self.is_connected:
            return
        try:
            self.instrument.Application.Quit()
            self.is_connected = False
        except Exception as e:
            return

    def get_scattering_parameters(
            self,
            parameters: List[SParameters],
            frequency_parameters: FrequencyParameters,
            results_formats: List[ResultsFormatType]
    ) -> dict[str: List[float]]:

        res = {}

        if not self.is_connected:
            return

        channel = 1
        self.set_settings(channel=channel, settings=frequency_parameters)

        for num, S_param in enumerate(parameters):
            num += 1
            self.instrument.SCPI.GetCALCulate(1).GetPARameter.DEFine = S_param
            self.instrument.SCPI.TRIGger.SEQuence.SOURce = "bus"
            self.instrument.SCPI.TRIGger.SEQuence.SINGle()

            trace_data = self.instrument.SCPI.GetCALCulate(1).SELected.DATA.FDATa
            # trace_tup = tuple(map(str, trace_data.split(',')))
            # res[f'{S_param}'] = np.array(trace_tup).astype(float)

        return res

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        pass


if __name__ == "__main__":
    analyzator = PlanarAnalyzer(
        ip="172.16.22.182",
        port="5025"
    )
    analyzator.connect()

    sp = ['S11', 'S23']
    fp = FrequencyParameters(
        1000, 5000, FrequencyTypes.MHZ, 200
    )
    results = analyzator.get_scattering_parameters(
        sp, fp, [ResultsFormatType.DB, ResultsFormatType.REAL]
    )
    print(results['S11'])