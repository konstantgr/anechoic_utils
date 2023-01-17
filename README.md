# anechoic_utils

# Примеры
## Сканер

```python
from anechoic_utils.scanner.TRIM import TRIMScanner

scanner = TRIMScanner(ip="172.16.22.244", port=9000)
# подключение к сканеру
scanner.connect()
```
Существует эмулятор сканера, на котором можно проводить тесты.
Его необходимо запустить, а затем подключиться к нему, как к реальному сканеру
```python
from anechoic_utils.scanner.TRIM import TRIMScanner, TRIM_emulator

# запуск эмулятора
TRIM_emulator.run(blocking=False, ip="127.0.0.1", port=9000, motion_time=5)

scanner = TRIMScanner(ip="127.0.0.1", port=9000)
# подключение к сканеру
scanner.connect()
```

### Настройки

**Касательно TRIM:**

Доступные настройки сканера: позиция, скорость движения, ускорение, замедление, статус двигателей (вкл. или выкл.), тип движения, специальный тип движения.
Все настройки применяются для каждой оси отдельно.

Чтобы применить настройки по умолчанию, необходимо написать
```python
from anechoic_utils.scanner.TRIM import DEFAULT_SETTINGS
scanner.set_settings(**DEFAULT_SETTINGS)
```
Помимо `DEFAULT_SETTINGS` есть `PTP_MODE_SETTINGS` и `JOG_MODE_SETTINGS`.
Первые настройки отвечают за движение от точки к точке, то есть за обычное движение.
Вторые - за бесконечное движение, направление которого соответствует знаку скорости оси.

**Касательно всех сканеров:**

Есть два способа выставить определенные настройки.
Первый способ заключается в создании экземпляра класса `BaseAxes` и использовании его для настроек.
Пример:
```python
from anechoic_utils.scanner import BaseAxes
# скорость вдоль оси x 100 мм/с,
# скорость вдоль оси z 120 мм/с
velocity = BaseAxes(x=100, z=120)
# применить эти настройки.
scanner.set_settings(velocity=velocity)
```
Скорости вдоль осей y и w остались прежними.
Для наглядности можно использовать классы `Position`, `Velocity`, `Acceleration`, `Deceleration`, которые являются по сути тем же классом `BaseAxes`.

Второй способ настройки заключается в выставлении настроек по осям отдельно.
```python
from anechoic_utils.scanner import BaseAxes
# скорость вдоль оси x 100 мм/с,
velocity_x = 100
# скорость вдоль оси z 120 мм/с
velocity_y = 120
# применить эти настройки.
scanner.set_settings(velocity_x=velocity_x, velocity_z=velocity_z)
```

### Получение данных

Сканер может вернуть его текущую позицию, скорость, ускорение и замедление.
```python
position = scanner.position()
velocity = scanner.velocity()
acceleration = scanner.acceleration()
deceleration = scanner.deceleration()
```

### Управление

Команды, не требующие аргументов:
1. `stop` останавливает сканер с замедлением
2. `abort` останавливает сканер без замедления
3. `home` направляет сканер на парковку

Пример:
```python
scanner.home()
```

Команда, требующая аргумент: `goto`.
Эта команда принимает `BaseAxes` или `Position` и отправляет в эту точку сканер.
```python
from anechoic_utils.scanner import Position

# новая позиция с координатами 1200 мм по x и 500 мм по y
new_position = Position(x=1200, y=500)
# отправить сканер в новую позицию
scanner.goto(new_position)
```

Позиции можно складывать
```python
from anechoic_utils.scanner import Position

# текущая позиция сканера
position = scanner.position()
# новая позиция, сдвинутая относительно текущей на 100 мм по x и 200 мм по y
new_position = position + Position(x=100, y=200)
scanner.goto(new_position)
```

# Анализатор

