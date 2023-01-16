"""
Реализация управления сканером с контроллером ORBIT/FR AL-4164 и AL-4166
"""
import time

from ..scanner import Scanner, BaseAxes, Position, Velocity, Acceleration, Deceleration
from ..scanner import ScannerConnectionError, ScannerInternalError, ScannerMotionError
from ..scanner import ScannerSignals
from ...utils import EmptySignal, FIFOLock
import socket
from typing import Union, List, Iterable
from dataclasses import fields, astuple

import logging
logger = logging.getLogger('scanner.TRIM')

STEPS_PER_MM_X = 8192
STEPS_PER_MM_Y = 5120
STEPS_PER_MM_Z = 5120
STEPS_PER_DEG_W = 1

AXES_SCALE = BaseAxes(
    x=STEPS_PER_MM_X,
    y=STEPS_PER_MM_Y,
    z=STEPS_PER_MM_Z,
    w=STEPS_PER_DEG_W
)


def cmds_from_axes(axes: BaseAxes, basecmd: str, val: bool = True, scale: bool = True) -> List[str]:
    """
    Переводит BaseAxes(x=V) в 'X<basecmd>=V', но только если V не None.
    Пример: BaseAxes(x=100, y=None) при basecmd='PS' получаем ['XPS=100'].
    Если val=False, то получим команды без '=V': ['XPS']

    :param axes: экземпляр BaseAxes
    :param basecmd: суффикс команды
    :param val: требуется ли указывать значение в команде
    :param scale: требуется ли преобразовать мм в шаги
    :return:
    """
    cmds = []
    for field in fields(axes):
        axis = field.name
        value = axes.__getattribute__(axis)
        scale_val = AXES_SCALE.__getattribute__(axis)
        if value is not None:
            if val:
                cmd_value = int(value * scale_val) if scale else int(value)
                cmds.append(f'{axis.upper()}{basecmd}={cmd_value}')
            else:
                cmds.append(f'{axis.upper()}{basecmd}')
    return cmds


EM = [
    'Motion is still active',
    'Normal end-of-motion',
    'Forward limit switch',
    'Reverse limit switch',
    'High software limit',
    'Low software limit',
    'Motor was disabled',
    'User command (stop or abort)',
    'Motor off by user'
]


def scanner_motion_error(action_description: str, stop_reasons: List[int]):
    """
    Возвращает исключение по описанию и причинам остановки

    :param action_description: описание движения во время которого возникла ошибка
    :param stop_reasons: причины ошибки (код EM)
    :return:
    """
    return ScannerMotionError(
        f'During {action_description} unexpected cause for end-of-motion was received:\n'
        f'\tx: {EM[stop_reasons[0]]}\n'
        f'\ty: {EM[stop_reasons[1]]}\n'
        f'\tz: {EM[stop_reasons[2]]}\n'
        f'\tw: {EM[stop_reasons[3]]}\n'
    )


DEFAULT_SETTINGS = {
    'acceleration': Acceleration(
        x=800000 / STEPS_PER_MM_X,
        y=1000000 / STEPS_PER_MM_Y,
        z=200000 / STEPS_PER_MM_Z,
        w=2000 / STEPS_PER_DEG_W,
    ),
    'deceleration': Deceleration(
        x=800000 / STEPS_PER_MM_X,
        y=1000000 / STEPS_PER_MM_Y,
        z=200000 / STEPS_PER_MM_Z,
        w=2000 / STEPS_PER_DEG_W,
    ),
    'velocity': Velocity(
        x=1228800 / STEPS_PER_MM_X,
        y=1024000 / STEPS_PER_MM_Y,
        z=100000 / STEPS_PER_MM_Z,
        w=3000 / STEPS_PER_DEG_W,
    ),
    'motion_mode': BaseAxes(
        x=0,
        y=0,
        z=0,
        w=0
    ),
    'special_motion_mode': BaseAxes(
        x=0,
        y=0,
        z=0,
        w=0
    ),
    'motor_on': BaseAxes(
        x=1,
        y=1,
        z=1,
        w=1
    )
}


PTP_MODE_SETTINGS = {
    'motion_mode': BaseAxes(
        x=0,
        y=0,
        z=0,
        w=0
    ),
    'special_motion_mode': BaseAxes(
        x=0,
        y=0,
        z=0,
        w=0
    ),
    'motor_on': BaseAxes(
        x=1,
        y=1,
        z=1,
        w=1
    )
}

JOG_MODE_SETTINGS = {
    'motion_mode': BaseAxes(
        x=1,
        y=1,
        z=1,
        w=1
    ),
    'special_motion_mode': BaseAxes(
        x=0,
        y=0,
        z=0,
        w=0
    ),
    'motor_on': BaseAxes(
        x=1,
        y=1,
        z=1,
        w=1
    )
}


def settings_check(
        x: float or None,
        y: float or None,
        z: float or None,
        w: float or None,
        axes: BaseAxes or None,
) -> None or BaseAxes:
    """
    Проверяет, как были переданы настройки: отдельными параметрами или при помощи BaseAxes.
    В первом случае преобразует отдельные настройки в BaseAxes, во втором случае -- возвращает BaseAxes без изменений.
    В случае, если не все параметры None, то возвращает None
    """
    separated = not (x is None and y is None and z is None and w is None)
    if axes is not None:
        if not separated:
            return axes
        raise RuntimeError("You have to pass either BaseAxes or separated settings, but not both")
    else:
        if not separated:
            return
        return BaseAxes(x=x, y=y, z=z, w=w)


class TRIMScannerSignals(ScannerSignals):
    position = EmptySignal()
    velocity = EmptySignal()
    acceleration = EmptySignal()
    deceleration = EmptySignal()
    is_connected = EmptySignal()
    is_moving = EmptySignal()


class TRIMScanner(Scanner):
    """
    Класс сканера
    """
    def __init__(
            self,
            ip: str,
            port: Union[str, int],
            bufsize: int = 1024,
            maxbufs: int = 1024,
            signals: ScannerSignals = None
    ):
        """

        :param ip: ip адрес сканера
        :param port: порт сканера
        :param bufsize: размер чанка сообщения в байтах
        :param maxbufs: максимальное число чанков
        """
        self.ip = ip
        self.port = port
        self.conn = socket.socket()
        self.bufsize = bufsize
        self.maxbufs = maxbufs
        self._tcp_lock = FIFOLock()  # FIFO лок для tcp сокета. Реализует тредсейф
        #  внутренние переменные для тред сейф выполнения goto и home
        self._motion_lock = FIFOLock()
        self._inner_motion_lock = FIFOLock()
        self._stop_flag = False
        self._stop_released = True

        self._is_moving = False
        self._is_connected = False
        self._velocity = Velocity()  # необходимо хранить скорость, потому что сканер не возвращает свою скорость

        if signals is not None:
            self._signals = signals
        else:
            self._signals = TRIMScannerSignals()

    def _set_is_connected(self, state: bool):
        self._is_connected = state
        self._signals.is_connected.emit(state)
        
    def connect(self) -> None:
        if self._is_connected:
            return
        try:
            self.conn.close()
            self.conn = socket.socket()
            self.conn.connect((self.ip, self.port))
            self._set_is_connected(True)
            logger.info("Scanner is connected")
        except socket.error as e:
            raise ScannerConnectionError from e

    def disconnect(self) -> None:
        if not self.is_connected:
            return
        try:
            self.conn.shutdown(socket.SHUT_RDWR)
            self.conn.close()
            self._set_is_connected(False)
            logger.info("Scanner is disconnected")
        except socket.error:
            self._set_is_connected(False)

    def set_settings(
            self,
            position: Position = None,
            velocity: Velocity = None,
            acceleration: Acceleration = None,
            deceleration: Deceleration = None,
            motor_on: BaseAxes = None,
            motion_mode: BaseAxes = None,
            special_motion_mode: BaseAxes = None,
            position_x: float = None,
            position_y: float = None,
            position_z: float = None,
            position_w: float = None,
            velocity_x: float = None,
            velocity_y: float = None,
            velocity_z: float = None,
            velocity_w: float = None,
            acceleration_x: float = None,
            acceleration_y: float = None,
            acceleration_z: float = None,
            acceleration_w: float = None,
            deceleration_x: float = None,
            deceleration_y: float = None,
            deceleration_z: float = None,
            deceleration_w: float = None,
            motor_on_x: float = None,
            motor_on_y: float = None,
            motor_on_z: float = None,
            motor_on_w: float = None,
            motion_mode_x: float = None,
            motion_mode_y: float = None,
            motion_mode_z: float = None,
            motion_mode_w: float = None,
            special_motion_mode_x: float = None,
            special_motion_mode_y: float = None,
            special_motion_mode_z: float = None,
            special_motion_mode_w: float = None,
    ) -> None:
        """
        Применить настройки
        """
        cmds = []
        if (position_par := settings_check(
                position_x, position_y, position_z, position_w, position
        )) is not None:
            cmds += cmds_from_axes(position_par, basecmd='PS')
        if (velocity_par := settings_check(
                velocity_x, velocity_y, velocity_z, velocity_w, velocity
        )) is not None:
            cmds += cmds_from_axes(velocity_par, basecmd='SP')
        if (acceleration_par := settings_check(
                acceleration_x, acceleration_y, acceleration_z, acceleration_w, acceleration
        )) is not None:
            cmds += cmds_from_axes(acceleration_par, basecmd='AC')
        if (deceleration_par := settings_check(
                deceleration_x, deceleration_y, deceleration_z, deceleration_w, deceleration
        )) is not None:
            cmds += cmds_from_axes(deceleration_par, basecmd='DC')
        if (motion_mode_par := settings_check(
                motion_mode_x, motion_mode_y, motion_mode_z, motion_mode_w, motion_mode
        )) is not None:
            cmds += cmds_from_axes(motion_mode_par, basecmd='MM', scale=False)
        if (special_motion_mode_par := settings_check(
                special_motion_mode_x, special_motion_mode_y, special_motion_mode_z, special_motion_mode_w, special_motion_mode
        )) is not None:
            cmds += cmds_from_axes(special_motion_mode_par, basecmd='SM', scale=False)
        if (motor_on_par := settings_check(
                motor_on_x, motor_on_y, motor_on_z, motor_on_w, motor_on
        )) is not None:
            cmds += cmds_from_axes(motor_on_par, basecmd='MO', scale=False)
        self._send_cmds(cmds)

        if position_par is not None:
            self.position_signal[type(position_par)].emit(position_par)
        if velocity_par is not None:
            self.velocity_signal[type(velocity_par)].emit(velocity_par)
            # Это необходимо, так как в самом сканере некорректно реализована команда ASP -- она возвращает нули
            for axis in fields(velocity_par):
                axis_velocity = velocity_par.__getattribute__(axis.name)
                if axis_velocity is not None:
                    self._velocity.__setattr__(axis.name, axis_velocity)
        if acceleration_par is not None:
            self.acceleration_signal[type(acceleration_par)].emit(acceleration_par)
        if deceleration_par is not None:
            self.deceleration_signal[type(deceleration_par)].emit(deceleration_par)
        logger.debug("Settings have been applied")

    def _send_cmd(self, cmd: str) -> str:
        """
        Принимает команду, отправляет на сканер и ждет ответа. Ответ возвращает.

        :param cmd: команда
        :return: ответ сканера
        """
        with self._tcp_lock:
            try:
                command = f"{cmd};"
                logger.debug(f">>> {command}")
                command_bytes = command.encode('ascii')
                self.conn.sendall(command_bytes)

                response = self.conn.recv(self.bufsize)
                logger.debug(f"<<< {response}")
                i = 1
                while not response.endswith(b'>'):
                    response += self.conn.recv(self.bufsize)
                    i += 1
                    if i >= self.maxbufs:
                        raise ScannerInternalError(f'maxbufs={self.maxbufs} limit is reached')

                if response.endswith(b'?>'):
                    raise ScannerInternalError(
                        f'Scanner response:\n{response}'
                    )

                if not response.startswith(command_bytes):
                    raise ScannerInternalError(
                        f'Scanner response:\n{response}\n\nEcho in start was expected:\n{command}'
                    )

                answer = response.decode().removeprefix(command).removesuffix('>')
                return answer
            except socket.error as e:
                self._set_is_connected(False)
                raise ScannerConnectionError from e

    def _send_cmds(self, cmds: List[str]) -> List[str]:
        """
        Принимает список команд, отправляет их на сканер и ждет все ответы. Ответы возвращает.

        :param cmds: список команд
        :return: ответы на команды
        """
        responses = []
        for cmd in cmds:
            responses.append(self._send_cmd(cmd))
        return responses

    @staticmethod
    def _parse_A_res(res: str, scale=True) -> Union[Iterable[int], Iterable[float]]:
        """
        Принимает строку "1,2,10" и преобразует в кортеж целых чисел (1, 2, 10).
        Если scale=True, переводит шаги в мм и радианы

        :param res: строка целых чисел, разделенных запятой
        :param scale: переводить ли число в мм и радианы
        :return: кортеж
        """
        if not scale:
            return (int(v) for v in res.split(','))
        return (int(v) / axis_scale for v, axis_scale in zip(res.split(','), astuple(AXES_SCALE)))

    def _is_stopped(self) -> bool:
        """
        Проверяет, остановился ли двигатель

        """
        res = self._send_cmd('AMS')
        return all([r == 0 for r in self._parse_A_res(res)])

    def _end_of_motion_reason(self) -> Iterable[int]:
        """
        Проверка причины остановки

        """
        time.sleep(0.02)
        res = self._send_cmd('AEM')
        return self._parse_A_res(res, scale=False)

    def _begin_motion_and_wait(self, cmds, action_description: str = "a motion"):
        """
        Отправляет команды, а затем ждет завершение движения

        :param cmds: команды
        :param action_description: описание движения, которое будет использовано при поднятии исплючения
        """
        self._send_cmds(cmds)

        while not self._is_stopped():
            time.sleep(0.1)

    def _set_is_moving(self, state: bool):
        self._is_moving = state
        self._signals.is_moving.emit(state)

    def _motion_decorator(self, func, *args, **kwargs):
        """
        Декоратор, который контролирует флаг остановки, потому что это не реализовано в контроллере.
        По документации MS=7 должен об этом сигнализировать, но это не работает.
        Декоратор реализует тред сейф сканера.

        Если в очереди стоят, например goto или home, из разных потоков, то при поднятии _stop_flag, все стоящие в очереди
        команды завершатся.
        После остановки тред с новым движением поменяет _stop_released и _stop_flag.

        :param func:
        """
        self._inner_motion_lock.acquire()
        self._set_is_moving(True)
        if self._stop_flag and not self._stop_released:
            self._stop_released = True
            self._inner_motion_lock.release()
            with self._motion_lock:
                self._stop_flag = False
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    raise e
                finally:
                    self._set_is_moving(False)
        else:
            self._inner_motion_lock.release()
            with self._motion_lock:
                if self._stop_flag:
                    self._set_is_moving(False)
                    raise ScannerMotionError(f'During the motion STOP or ABORT was executed')
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    raise e
                finally:
                    self._set_is_moving(False)
        if self._stop_flag:
            self._set_is_moving(False)
            raise ScannerMotionError(f'During the motion STOP or ABORT was executed')

    def _goto(self, position: Position) -> None:
        logger.debug(f'Moving to {position}')
        self.set_settings(**PTP_MODE_SETTINGS)
        cmds = cmds_from_axes(position, 'AP')
        cmds += cmds_from_axes(position, 'BG', val=False, scale=False)
        action_description = f'the motion to {position}'
        self._begin_motion_and_wait(cmds, action_description)

        stop_reasons = list(self._end_of_motion_reason())
        if position.x is not None and stop_reasons[0] != 1:
            raise scanner_motion_error(action_description, stop_reasons)
        if position.y is not None and stop_reasons[1] != 1:
            raise scanner_motion_error(action_description, stop_reasons)
        if position.z is not None and stop_reasons[2] != 1:
            raise scanner_motion_error(action_description, stop_reasons)
        if position.w is not None and stop_reasons[3] != 1:
            raise scanner_motion_error(action_description, stop_reasons)
        logger.debug(f'Moved to {position}')
        self.position()

    def goto(self, position: Position) -> None:
        self._motion_decorator(self._goto, position)

    def stop(self) -> None:
        logger.info(f'Stopping...')
        self._stop_flag = True
        self._stop_released = False
        self._send_cmd('AST')

    def abort(self) -> None:
        self.stop()

    def position(self) -> Position:
        res = self._send_cmd('APS')
        ans = Position(*self._parse_A_res(res))
        self.position_signal.emit(ans)
        return ans

    def _encoder_position(self) -> Position:
        """
        Реальная позиция сканера по положению энкодера

        :return: реальная позиция
        """
        res = self._send_cmd('PS')
        ans = Position(*self._parse_A_res(res))
        return ans

    def velocity(self) -> Velocity:
        self.velocity_signal.emit(self._velocity)
        return self._velocity  # на данном сканере нельзя получить скорость

    def acceleration(self) -> Acceleration:
        res = self._send_cmd('AAC')
        ans = Acceleration(*self._parse_A_res(res))
        self.acceleration_signal.emit(ans)
        return ans

    def deceleration(self) -> Deceleration:
        res = self._send_cmd('ADC')
        ans = Deceleration(*self._parse_A_res(res))
        self.deceleration_signal.emit(ans)
        return ans

    def _motor_on(self) -> BaseAxes:
        """
        Включены или выключены двигатели

        :return: покоординатные значения состояния двигателей
        """
        res = self._send_cmd('AMO')
        ans = BaseAxes(*self._parse_A_res(res, scale=False))
        return ans

    def _motion_mode(self) -> BaseAxes:
        """
        Режим движения двигателей

        :return: покоординатные значения режима движения двигателей
        """
        res = self._send_cmd('AMM')
        ans = BaseAxes(*self._parse_A_res(res, scale=False))
        return ans

    def _special_motion_mode(self) -> BaseAxes:
        """
        Специальный режим движения двигателей

        :return: покоординатные значения специального режима движения двигателей
        """
        res = self._send_cmd('ASM')
        ans = BaseAxes(*self._parse_A_res(res, scale=False))
        return ans

    def debug_info(self) -> str:
        cmds = [
            'AAP',  # следующая точка движения в PTP режиме
            'APS',  # актуальные координаты энкодеров
            # 'APE',
            # 'ADP',
            # 'ARP',
            'AEM',  # причина последней остановки
            'AHL',  # максимальные значения координаты в софте
            'ALL',  # максимальные значения координаты в софте
            'AMM',  # режим движения
            'ASM',  # подрежим движения
            'AMO',  # включен или выключен мотор
            # 'AWW',
            # 'AMF',
            'AMS',  # состояние мотора
        ]
        res = self._send_cmds(cmds)
        return "\n".join([f'{c}: {r}' for c, r in zip(cmds, res)])

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def _home(self) -> None:
        logger.info(f'Homing...')
        # уменьшение скорости в два раза
        old_velocity = self.velocity()
        new_velocity = old_velocity / 2
        self.set_settings(velocity=new_velocity)
        # выставляем режим бесконечного движения с постоянной скоростью
        self.set_settings(**JOG_MODE_SETTINGS)

        action_description = f'homing'
        cmds = ['XBG', 'YBG', 'ZBG']
        self._begin_motion_and_wait(cmds, action_description)

        # возвращаем старую скорость
        self.set_settings(velocity=old_velocity)
        # возвращаем point-to-point режим работы
        self.set_settings(**PTP_MODE_SETTINGS)

        time.sleep(1)
        stop_reasons = list(self._end_of_motion_reason())
        if not (stop_reasons[0] == stop_reasons[1] == stop_reasons[2] == 2):
            raise scanner_motion_error(action_description, stop_reasons)

    def home(self) -> None:
        self._motion_decorator(self._home)

    @property
    def position_signal(self):
        return self._signals.position

    @property
    def velocity_signal(self):
        return self._signals.velocity

    @property
    def acceleration_signal(self):
        return self._signals.acceleration

    @property
    def deceleration_signal(self):
        return self._signals.deceleration

    @property
    def is_moving(self) -> bool:
        return self._is_moving
