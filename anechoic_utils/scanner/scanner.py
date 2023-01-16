"""
Базовые классы для управления сканером
"""
import dataclasses
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from numbers import Number
from ..utils import EmptySignal


class ScannerConnectionError(Exception):
    """
    Исключение, вызываемое при проблеме с подключением: разрыв соединения, невозможность подключиться, таймаут
    """
    def __init__(self):
        super().__init__(
            "Error in scanner connection"
        )


class ScannerInternalError(Exception):
    """
    Исключение, вызываемое при проблеме в самом сканере: неправильная команда, достижение предела по одной из координат
    """
    def __init__(self, message):
        super().__init__(
            f'Scanner error:\n{message}'
        )


class ScannerMotionError(Exception):
    """
    Исключение, поднимаемое при ошибках во время движения сканера
    """
    def __init__(self, message):
        super().__init__(
            f'Scanner motion error:\n{message}'
        )


@dataclass
class BaseAxes:
    """
    Все координаты сканера в мм
    """
    x: float = None
    y: float = None
    z: float = None
    w: float = None
    # e: float = None
    # f: float = None
    # g: float = None

    def __add__(self, other):
        if not isinstance(other, BaseAxes):
            raise NotImplementedError
        res = BaseAxes()
        for attr in dataclasses.fields(BaseAxes):
            name = attr.name
            if other.__getattribute__(name) is None:
                res.__setattr__(name, self.__getattribute__(name))
            else:
                res.__setattr__(name, self.__getattribute__(name) + other.__getattribute__(name))
        return res

    def __sub__(self, other):
        if not isinstance(other, BaseAxes):
            raise NotImplementedError
        res = BaseAxes()
        for attr in dataclasses.fields(BaseAxes):
            name = attr.name
            if other.__getattribute__(name) is None:
                res.__setattr__(name, self.__getattribute__(name))
            else:
                res.__setattr__(name, self.__getattribute__(name) - other.__getattribute__(name))
        return res

    def __mul__(self, other):
        if not isinstance(other, Number):
            raise NotImplementedError
        res = BaseAxes()
        for attr in dataclasses.fields(BaseAxes):
            name = attr.name
            if self.__getattribute__(name) is not None:
                res.__setattr__(name, self.__getattribute__(name) * other)
        return res

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        if not isinstance(other, Number):
            raise NotImplementedError
        res = BaseAxes()
        for attr in dataclasses.fields(BaseAxes):
            name = attr.name
            if self.__getattribute__(name) is not None:
                res.__setattr__(name, self.__getattribute__(name) / other)
        return res


@dataclass
class Position(BaseAxes):
    """
    Координаты каждой оси
    """


@dataclass
class Velocity(BaseAxes):
    """
    Скорости каждой оси
    """


@dataclass
class Acceleration(BaseAxes):
    """
    Ускорения каждой оси
    """


@dataclass
class Deceleration(BaseAxes):
    """
    Замедления каждой оси
    """


class ScannerSignals(metaclass=ABCMeta):
    """
    Базовые сигналы сканера
    """

    @property
    @abstractmethod
    def position(self) -> EmptySignal:
        """
        Сигнал с позицией сканера
        """

    @property
    @abstractmethod
    def velocity(self) -> EmptySignal:
        """
        Сигнал со скоростью сканера
        """

    @property
    @abstractmethod
    def acceleration(self) -> EmptySignal:
        """
        Сигнал с ускорением сканера
        """

    @property
    @abstractmethod
    def deceleration(self) -> EmptySignal:
        """
        Сигнал с замедлением сканера
        """

    @property
    @abstractmethod
    def is_connected(self) -> EmptySignal:
        """
        Сигнал с состоянием сканера
        """

    @property
    @abstractmethod
    def is_moving(self) -> EmptySignal:
        """
        Сигнал с состоянием сканера
        """


class Scanner(metaclass=ABCMeta):
    """
    Базовый класс сканера
    """

    @abstractmethod
    def goto(self, position: Position) -> None:
        """
        Переместиться в точку point.
        Обязан быть thread safe!

        :param position: то, куда необходимо переместиться
        :type position: Position
        """

    @abstractmethod
    def stop(self) -> None:
        """
        Полная остановка сканера (сначала замедлится, потом остановится)

        """

    @abstractmethod
    def abort(self) -> None:
        """
        Незамедлительная остановка сканера

        """

    @abstractmethod
    def position(self) -> Position:
        """
        Позиция сканера

        :return: позиция
        """

    @abstractmethod
    def velocity(self) -> Velocity:
        """
        Скорость сканера

        :return: скорость
        """

    @abstractmethod
    def acceleration(self) -> Acceleration:
        """
        Ускорения сканера

        :return: ускорение
        """

    @abstractmethod
    def deceleration(self) -> Deceleration:
        """
        Замедления сканера

        :return: замедление
        """

    @abstractmethod
    def connect(self) -> None:
        """
        Подключение к сканеру

        """

    @abstractmethod
    def disconnect(self) -> None:
        """
        Отключение от сканера

        """

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Доступность сканера для управления

        :return: доступность
        """

    @property
    @abstractmethod
    def is_moving(self) -> bool:
        """
        Состояние движения сканера

        :return: доступность
        """

    @abstractmethod
    def debug_info(self) -> str:
        """
        Возвращает максимум информации о сканере

        :return: максимальное количество информации о сканере
        """

    @abstractmethod
    def home(self) -> None:
        """
        Перемещение сканера домой.
        Является thread safe и обрабатывается аналогично goto().

        """

    @abstractmethod
    def set_settings(self, *args, **kwargs) -> None:
        """
        Применение настроек

        :param args:
        :param kwargs:
        :return:
        """
