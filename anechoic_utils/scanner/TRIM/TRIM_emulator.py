import socket
from ..scanner import Position, Velocity, Acceleration, Deceleration, BaseAxes
import threading
import time
from dataclasses import dataclass
import dataclasses
from typing import Union, Any, Iterable


@dataclass
class ScannerStorage:
    acceleration = Acceleration(10, 20, 30, 40)
    deceleration = Deceleration(10, 20, 30, 40)
    velocity = Velocity(10, 20, 30, 40)
    position = Position(10, 20, 30, 40)
    absolute_position = Position(10, 20, 30, 40)
    motor_on = BaseAxes(0, 0, 0, 0)
    motion_mode = BaseAxes(0, 0, 0, 0)
    special_motion_mode = BaseAxes(0, 0, 0, 0)
    high_limit = BaseAxes(127, 127, 127, 127)
    low_limit = BaseAxes(-127, -127, -127, -127)

    motor_status = BaseAxes(0, 0, 0, 0)
    error_motion = BaseAxes(1, 1, 1, 1)
    motion_start_time = BaseAxes(0, 0, 0, 0)

    in_motion = False


def return_by_cmd(axis: BaseAxes, letter: bytes) -> bytes:
    if letter == b'A':
        return f'{axis.x},{axis.y},{axis.z},{axis.w}>'.encode()
    elif letter.decode().lower() in axis.__dict__.keys():
        return f'{axis.__getattribute__(letter.decode().lower())}>'.encode()


def set_by_value(axis: BaseAxes, letter: bytes, value: Union[Iterable[Any], Any]):
    if letter == b'A':
        if isinstance(value, Iterable):
            for val, attr in zip(value, axis.__dict__.keys(), strict=True):
                axis.__setattr__(attr, val)
        else:
            for attr in axis.__dict__.keys():
                axis.__setattr__(attr, value)
    elif letter.decode().lower() in axis.__dict__.keys():
        axis.__setattr__(letter.decode().lower(), value)


def set_by_cmd(axis: BaseAxes, letter: bytes, cmd: bytes) -> bytes:
    try:
        if letter == b'A':
            if len(cmd.split(b',')) != 1:
                set_by_value(axis, letter, map(int, cmd.split(b',')))
            else:
                set_by_value(axis, letter, int(cmd.split(b',')[0]))
        elif letter.decode().lower() in axis.__dict__.keys():
            set_by_value(axis, letter, int(cmd))
        return b'>'
    except:
        return b'?>'


def update_ms_em(scanner, tmp, motion_time):
    ends = []
    for field in dataclasses.fields(BaseAxes):
        attr = field.name
        dt = tmp - scanner.motion_start_time.__getattribute__(attr)
        if scanner.in_motion:
            if dt < motion_time:
                scanner.motor_status.__setattr__(attr, 1)
                scanner.error_motion.__setattr__(attr, 0)
                if scanner.motion_mode.__getattribute__(attr) == 0:
                    new_pos = scanner.absolute_position.__getattribute__(attr)
                    prev_pos = scanner.position.__getattribute__(attr)
                    cur_pos = int((new_pos + prev_pos)/2)
                elif scanner.motion_mode.__getattribute__(attr) == 1:
                    cur_pos = scanner.position.__getattribute__(attr) + 1
                scanner.position.__setattr__(attr, cur_pos)
                ends.append(False)
            else:
                scanner.motor_status.__setattr__(attr, 0)
                if scanner.motion_mode.__getattribute__(attr) == 0:
                    scanner.error_motion.__setattr__(attr, 1)
                elif scanner.motion_mode.__getattribute__(attr) == 1:
                    scanner.error_motion.__setattr__(attr, 2)
                scanner.position.__setattr__(attr, scanner.absolute_position.__getattribute__(attr))
                ends.append(True)
        else:
            ends.append(True)
    scanner.in_motion = not all(ends)


def emulator(ip="127.0.0.1", port=9000, motion_time: int = 5):
    scanner = ScannerStorage()
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((ip, port))
            s.listen()
            conn, addr = s.accept()
            with conn:
                while True:
                    data = conn.recv(1024)
                    if not data:
                        break

                    if not data.endswith(b';'):
                        raise RuntimeError
                    new_data = data

                    axis = None
                    done = False
                    if data[1:3] == b'PS':
                        update_ms_em(scanner, time.time(), motion_time)
                        axis = scanner.position
                    elif data[1:3] == b'AP':
                        axis = scanner.absolute_position
                    elif data[1:3] == b'SP':
                        axis = scanner.velocity
                    elif data[1:3] == b'AC':
                        axis = scanner.acceleration
                    elif data[1:3] == b'DC':
                        axis = scanner.deceleration
                    elif data[1:3] == b'MO':
                        axis = scanner.motor_on
                    elif data[1:3] == b'MM':
                        axis = scanner.motion_mode
                    elif data[1:3] == b'SM':
                        axis = scanner.special_motion_mode
                    elif data[1:3] == b'HL':
                        axis = scanner.high_limit
                    elif data[1:3] == b'LL':
                        axis = scanner.low_limit

                    elif data[1:3] == b'BG':
                        scanner.in_motion = True
                        axis = scanner.motion_start_time
                        letter = data[0:1]
                        tmp = time.time()
                        set_by_value(axis, letter, tmp)
                        update_ms_em(scanner, time.time(), motion_time)
                        new_data += b'>'
                        done = True

                    elif data[1:3] == b'ST' or data[1:3] == b'AB':
                        update_ms_em(scanner, time.time(), motion_time)
                        scanner.in_motion = False
                        letter = data[0:1]
                        axis = scanner.motor_status
                        set_by_value(axis, letter, 0)
                        axis = scanner.error_motion
                        set_by_value(axis, letter, 1)
                        new_data += b'>'
                        done = True

                    elif data[1:3] == b'MS':
                        update_ms_em(scanner, time.time(), motion_time)
                        axis = scanner.motor_status
                    elif data[1:3] == b'EM':
                        update_ms_em(scanner, time.time(), motion_time)
                        axis = scanner.error_motion

                    if axis is None and not done:
                        new_data += b'?>'
                    elif not done:
                        if data.count(b'=') == 0:
                            new_data += return_by_cmd(axis, data[0:1])
                        elif data[3:4] == b'=':
                            new_data += set_by_cmd(axis, data[0:1], data[4:-1])
                        else:
                            new_data += b'?>'
                    conn.sendall(new_data)


def run(blocking=True, ip="127.0.0.1", port=9000, motion_time=5):
    server_thread = threading.Thread(target=emulator, args=(ip, port, motion_time))
    print('Starting server')
    server_thread.start()
    if blocking:
        server_thread.join()


if __name__ == "__main__":
    run()
