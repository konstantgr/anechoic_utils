import abc
from typing import List
from .analyzator_parameters import SParameters, FrequencyParameters, AnalyzatorType, ResultsFormatType
from ..utils import EmptySignal


class AnalyzerConnectionError(Exception):
    """
    Исключение при ошибке в соединении
    """
    def __init__(self):
        super().__init__("Error in analyzer connection")


class AnalyzerSignals(metaclass=abc.ABCMeta):
    """
    Базовые сигналы анализатора
    """

    @property
    @abc.abstractmethod
    def data(self) -> EmptySignal:
        """
        Сигнал с данными анализатора
        """

    @property
    @abc.abstractmethod
    def is_connected(self) -> EmptySignal:
        """
        Сигнал с состоянием анализатора
        """


class BaseAnalyzer(abc.ABC):
    """
    Базовый класс анализатора
    """
    @abc.abstractmethod
    def connect(self) -> bool:
        """
        Подключение к анализатору
        """

    @abc.abstractmethod
    def disconnect(self) -> bool:
        """
        Отключение от анализатора
        """

    @abc.abstractmethod
    def get_scattering_parameters(
            self,
            parameters: List[str],
    ) -> dict[str: List[float]]:
        """
        Получить S параметры
        """

    @abc.abstractmethod
    def set_settings(self, *args, **kwargs) -> None:
        """
        Применение настроек

        :param args:
        :param kwargs:
        :return:
        """

    @property
    @abc.abstractmethod
    def is_connected(self) -> bool:
        """
        Доступность анализатора для управления

        :return: доступность
        """

    @abc.abstractmethod
    def __enter__(self):
        raise NotImplementedError('__enter__ method not implemented yet')

    @abc.abstractmethod
    def __exit__(self, type, value, traceback):
        raise NotImplementedError('__exit__ method not implemented yet')
