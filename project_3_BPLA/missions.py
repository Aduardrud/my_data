from abc import ABC, abstractmethod
import airsim
import sys
import math
import time
import logging
import os


# Настройка логирования
logging.basicConfig(level=logging.INFO, filemode="w")


# Абстрактный класс для миссий
class Missions(ABC):
    @abstractmethod
    def start(self):
        """Запустить миссию."""
        pass

    @abstractmethod
    def landed(self):
        """Запустить приземление дрона."""
        pass


# Класс для обследования площади по квадрату
class SurveyNavigator(Missions):
    def __init__(self, **kwargs):
        """Инициализация параметров миссии патрулирования.

        Args:
            kwargs: Параметры, необходимые для обследования:
                boxsize: размер области, которую нужно обследовать.
                stripewidth: ширина полосы, по которой будет осуществляться движение.
                altitude: высота полета.
                velocity: скорость дрона.
        """
        self.boxsize = kwargs.get('boxsize')
        self.stripewidth = kwargs.get('stripewidth')
        self.altitude = kwargs.get('altitude')
        self.velocity = kwargs.get('velocity')

        # Проверка на наличие необходимых параметров
        if self.boxsize is None or self.stripewidth is None or self.altitude is None or self.velocity is None:
            raise ValueError(
                "Отсутствуют необходимые параметры: boxsize, stripewidth, altitude, and velocity!")

        self.client = airsim.MultirotorClient()  # Инициализация клиента AirSim
        self.client.confirmConnection()  # Подтверждение подключения
        self.client.enableApiControl(True)  # Включение API управления

    # Метод начала патрулирования
    def start(self):
        """Запуск миссии патрулирования в заданном квадрате."""
        # Запускаем дрон (подготавливаем к полету)
        logging.info("Армирование моторов...")
        self.client.armDisarm(True)  # Армируем дрон
        time.sleep(2)  # Небольшая пауза для стабилизации

        # Получаем текущее состояние дрона (приземлен ли он)
        landed = self.client.getMultirotorState().landed_state
        # Если дрон приземлен, то начинаем взлет
        if landed == airsim.LandedState.Landed:
            logging.info("Взлёт...")
            self.client.takeoffAsync().join()  # Запускаем взлет

        # Проверяем снова, приземлен ли дрон после взлета
        landed = self.client.getMultirotorState().landed_state
        if landed == airsim.LandedState.Landed:
            logging.info("сбой взлета - проверьте журнал сообщений Unreal для получения подробной информации")
            return  # Выходим из метода, если взлет не удался

        # В AirSim используются координаты NED, поэтому ось Z направлена вверх
        x = -self.boxsize
        z = -self.altitude

        # Поднимаемся на заданную высоту
        logging.info("Набор высоты: " + str(self.altitude))
        self.client.moveToPositionAsync(0, 0, z, self.velocity).join()
        time.sleep(2)

        # Летаем к первому углу коробки для обследования
        logging.info("Начало патрулирования")
        self.client.moveToPositionAsync(x, -self.boxsize, z, self.velocity).join()

        # Даем дрону немного времени для стабилизации
        self.client.hoverAsync().join()
        time.sleep(2)

        # После зависания снова включаем управление API для следующего этапа полета
        self.client.enableApiControl(True)

        # Теперь вычисляем путь для обследования, чтобы заполнить коробку
        path = []
        distance = 0
        # Цикл для вычисления координат пути
        while x < self.boxsize:
            distance += self.boxsize
            path.append(airsim.Vector3r(x, self.boxsize, z))  # Добавляем первую позицию
            x += self.stripewidth  # Сдвигаем x на ширину полосы
            distance += self.stripewidth
            path.append(airsim.Vector3r(x, self.boxsize, z))  # Добавляем вторую позицию
            distance += self.boxsize

        path.append(airsim.Vector3r(x, -self.boxsize, z))  # Добавляем третью позицию
        x += self.stripewidth  # Сдвигаем x на ширину полосы
        distance += self.stripewidth
        path.append(airsim.Vector3r(x, -self.boxsize, z))  # Добавляем четвертую позицию
        distance += self.boxsize

        # Сообщаем о начале обследования и вычисленной дистанции
        logging.info("Расчетное расстояние полёта:" + str(distance))
        trip_time = distance / self.velocity  # Вычисляем время поездки
        logging.info("Расчётное время полёта " + str(trip_time))
        time.sleep(2)

        try:
            # Даем команду на движение по рассчитанному пути
            result = self.client.moveOnPathAsync(path, self.velocity, trip_time, airsim.DrivetrainType.ForwardOnly,
                                                 airsim.YawMode(False, 0), self.velocity + (self.velocity / 2),
                                                 1).join()
        except:
            # Обработка ошибок, если команда движения не удалась
            errorType, value, traceback = sys.exc_info()
            logging.info("moveOnPath threw exception: " + str(value))
            pass

        # Возвращаемся к начальной позиции
        logging.info("Возврат к точке старта")
        self.client.moveToPositionAsync(0, 0, z, self.velocity).join()
        logging.info("Миссия завершена. Дрон готов к следующей миссии или посадке.")



    def landed(self):
        """Запустить приземление дрона."""
        # Даем дрону немного времени для стабилизации
        self.client.hoverAsync().join()
        time.sleep(2)

        # После зависания снова включаем управление API для следующего этапа полета
        self.client.enableApiControl(True)

        z = self.client.getMultirotorState().kinematics_estimated.position.z_val

        # Если высота выше 5, опускаемся до 5
        if z < -5:
            logging.info("Снижаемся")
            self.client.moveToPositionAsync(0, 0, -5, 5).join()
            time.sleep(2)

        # Садимся на землю
        logging.info("Посадка...")
        self.client.landAsync().join()

        # Блокируем дрон после завершения миссии
        logging.info("Дрон заблокирован.")
        self.client.armDisarm(False)
        self.client.enableApiControl(False)


class Position:
    def __init__(self, pos):
        """Инициализация позиции дрона.

        Args:
            pos: Позиция дрона в виде объекта, содержащего координаты x, y и z.
        """
        self.x = pos.x_val
        self.y = pos.y_val
        self.z = pos.z_val


# Класс для орбитального движения
class OrbitNavigator(Missions):
    def __init__(self, **kwargs):
        """Инициализация параметров миссии.

        Args:
            kwargs: Параметры орбитального движения:
                radius: радиус круга.
                altitude: высота полета.
                velocity: скорость дрона.
                iterations: количество кругов.
                center: список с координатами центра круга.
                snapshots: количество требуемых снимков.
        """
        self.radius = kwargs.get('radius')  # Радиус орбиты
        self.altitude = kwargs.get('altitude')  # Высота полета
        self.velocity = kwargs.get('velocity')  # Скорость дрона
        self.iterations = kwargs.get('iterations')  # Количество кругов
        self.snapshots = kwargs.get('snapshots')  # Количество снимков
        center = kwargs.get('center')  # Координаты центра орбиты
        self.snapshot_delta = None
        self.next_snapshot = None
        self.z = None
        self.snapshot_index = 0
        self.takeoff = False  # Флаг успешного взлета

        if self.snapshots is not None and self.snapshots > 0:
            self.snapshot_delta = 360 / self.snapshots  # Вычисляем интервал для снимков

        if self.iterations is not None and self.iterations <= 0:
            self.iterations = 1  # Устанавливаем минимальное количество итераций

        if len(center) != 2:
            raise Exception("Expecting '[x,y]' for the center direction vector")  # Проверка корректности центра

        # Нормализация центра
        cx = float(center[0])

        cy = float(center[1])
        length = math.sqrt((cx * cx) + (cy * cy))  # Длина вектора
        cx /= length  # Нормализуем x
        cy /= length  # Нормализуем y
        cx *= self.radius  # Масштабируем до радиуса
        cy *= self.radius  # Масштабируем до радиуса

        # Проверка на наличие необходимых параметров
        if (self.radius is None or self.altitude is None or self.velocity is None or self.iterations is None
                or self.snapshots is None or center is None):
            raise ValueError(
                "Отсутствуют необходимые параметры: radius, altitude, velocity, iterations, center  and snapshots!")

        self.client = airsim.MultirotorClient()  # Инициализация клиента AirSim
        self.client.confirmConnection()  # Подтверждение подключения
        self.client.enableApiControl(True)  # Включение API управления

        # Хранение текущего положения дрона
        self.home = self.client.getMultirotorState().kinematics_estimated.position

        # Логика для стабилизации позиции
        start = time.time()  # Время начала стабилизации
        count = 0  # Счетчик успеха стабилизации
        while count < 100:
            pos = self.client.getMultirotorState().kinematics_estimated.position  # Получение текущей позиции
            if abs(pos.z_val - self.home.z_val) > 1:  # Проверка на дрейф по вертикали
                count = 0
                self.home = pos  # Обновление домашней позиции
                if time.time() - start > 10:  # Время ожидания
                    logging.info("Drone position is drifting, we are waiting for it to settle down...")
                    start = time.time()  # Сброс времени
            else:
                count += 1  # Успешная стабилизация

        self.center = pos  # Установка центра орбиты
        self.center.x_val += cx  # Установка x центра
        self.center.y_val += cy  # Установка y центра


    def start(self):
        """Запустить выполнение миссии."""
        logging.info("Армирование дрона...")
        self.client.armDisarm(True)  # Армируем дрон

        # AirSim использует координаты NED, поэтому ось Z направлена вверх.
        start = self.client.getMultirotorState().kinematics_estimated.position  # Получение текущей позиции дрона
        landed = self.client.getMultirotorState().landed_state  # Определение, приземлен ли дрон
        if not self.takeoff and landed == airsim.LandedState.Landed:
            self.takeoff = True  # Установка флага взлета
            logging.info("Взлёт...")
            self.client.takeoffAsync().join()  # Запуск взлета
            start = self.client.getMultirotorState().kinematics_estimated.position  # Получение обновленной позиции после взлета
            z = -self.altitude + self.home.z_val  # Установка высоты
        else:
            logging.info("Уже летим, так что мы выйдем на орбиту на текущей высоте {}".format(start.z_val))
            z = start.z_val  # Используем текущую высоту

        logging.info("Подъём на позицию: {},{},{}".format(start.x_val, start.y_val, z))
        self.client.moveToPositionAsync(start.x_val, start.y_val, z,
                                        self.velocity).join()  # Переход к начальной позиции на высоте
        self.z = z

        logging.info("Набор скорости...")
        count = 0  # Счетчик итераций
        self.start_angle = None
        self.next_snapshot = None

        # ramp up time
        ramptime = self.radius / 10  # Время разгона
        self.start_time = time.time()  # Время начала разгона

        while count < self.iterations:
            if self.snapshots > 0 and not (self.snapshot_index < self.snapshots):
                break

            # Увеличение скорости плавно, чтобы избежать резкого старта
            now = time.time()
            speed = self.velocity
            diff = now - self.start_time
            if diff < ramptime:  # Если еще не разогнались до полной скорости
                speed = self.velocity * diff / ramptime
            elif ramptime > 0:
                logging.info("Дрон набрал полную скорость...")
                ramptime = 0  # Завершаем разгон

            lookahead_angle = speed / self.radius  # Угол опережения

            # вычисляем текущий угол
            pos = self.client.getMultirotorState().kinematics_estimated.position  # Получаем текущую позицию
            dx = pos.x_val - self.center.x_val  # Расстояние по оси x до центра
            dy = pos.y_val - self.center.y_val  # Расстояние по оси y до центра
            actual_radius = math.sqrt((dx * dx) + (dy * dy))  # Расчет фактического радиуса
            angle_to_center = math.atan2(dy, dx)  # Угол между позицией дрона и центром

            camera_heading = (angle_to_center - math.pi) * 180 / math.pi  # Направление камеры

            # вычисляем угол опережения
            lookahead_x = self.center.x_val + self.radius * math.cos(angle_to_center + lookahead_angle)
            lookahead_y = self.center.y_val + self.radius * math.sin(angle_to_center + lookahead_angle)

            vx = lookahead_x - pos.x_val  # Вертикальная скорость
            vy = lookahead_y - pos.y_val  # Горизонтальная скорость

            if self.track_orbits(angle_to_center * 180 / math.pi):  # Отслеживание кругов
                count += 1
                logging.info("Завершение {} круга".format(count))

            self.camera_heading = camera_heading  # Сохраняем направление камеры
            self.client.moveByVelocityZAsync(vx, vy, z, 1, airsim.DrivetrainType.MaxDegreeOfFreedom,
                                             airsim.YawMode(False, camera_heading))

        # Возвращаемся к начальной позиции
        self.client.moveToPositionAsync(start.x_val, start.y_val, z, self.velocity).join()
        logging.info("Миссия завершена. Дрон готов к следующей миссии или посадке.")



    def landed(self):
        """Обработать событие приземления."""
        # Даем дрону немного времени для стабилизации
        self.client.hoverAsync().join()
        time.sleep(2)

        # После зависания снова включаем управление API для следующего этапа полета
        self.client.enableApiControl(True)

        z = self.client.getMultirotorState().kinematics_estimated.position.z_val  # Текущая высота дрона

        # Если высота выше 5, опускаемся до 5
        if z < -5:
            logging.info("Снижаемся")
            self.client.moveToPositionAsync(0, 0, -5, 5).join()
            time.sleep(2)

        # Садимся на землю
        logging.info("Посадка...")
        self.client.landAsync().join()

        # Блокируем дрон после завершения миссии
        logging.info("Дрон заблокирован.")
        self.client.armDisarm(False)
        self.client.enableApiControl(False)


    def track_orbits(self, angle):
        """Отслеживание завершенных орбит.

        Args:
            angle: Угол, на котором находится дрон.

        Returns:
            bool: Возвращает True, если завершена орбита, иначе False.
        """
        # отслеживаем # завершенных орбит, чтобы избежать случайных колебаний
        if angle < 0:
            angle += 360

        if self.start_angle is None:
            self.start_angle = angle
            if self.snapshot_delta:
                self.next_snapshot = angle + self.snapshot_delta
            self.previous_angle = angle
            self.shifted = False
            self.previous_sign = None
            self.previous_diff = None
            self.quarter = False
            return False

        # Теперь мы просто должны смотреть на плавное пересечение от отрицательного до положительного
        if self.previous_angle is None:
            self.previous_angle = angle
            return False

        # Игнорируем переход с 360 на 0
        if self.previous_angle > 350 and angle < 10:
            if self.snapshot_delta and self.next_snapshot >= 360:
                self.next_snapshot -= 360
            return False

        diff = self.previous_angle - angle  # Разница между предыдущим и текущим углом
        crossing = False  # Переменная для отслеживания пересечения
        self.previous_angle = angle

        if self.snapshot_delta and angle > self.next_snapshot:
            logging.info("Снимок сделан на {} градусов".format(angle))  # Сообщение о снимке
            self.take_snapshot()  # Функция для захвата снимка
            self.next_snapshot += self.snapshot_delta  # Обновление следующего снимка

        diff = abs(angle - self.start_angle)
        if diff > 45:
            self.quarter = True  # Если прошли четверть круга

        if self.quarter and self.previous_diff is not None and diff != self.previous_diff:
            # следим за направлением, в котором изменяется разница
            direction = self.sign(self.previous_diff - diff)
            if self.previous_sign is None:
                self.previous_sign = direction
            elif self.previous_sign > 0 and direction < 0:
                if diff < 45:
                    self.quarter = False
                    if self.snapshots <= self.snapshot_index + 1:
                        crossing = True  # Пересечение обнаружено
            self.previous_sign = direction
        self.previous_diff = diff  # Обновляем предыдущую разницу

        return crossing


    def take_snapshot(self):
        """Захватывает снимок текущей позиции дрона."""
        # Получаем текущую позицию дрона
        pos = self.client.getMultirotorState().kinematics_estimated.position
        self.client.moveToPositionAsync(pos.x_val, pos.y_val, self.z, 0.5, 3, airsim.DrivetrainType.MaxDegreeOfFreedom,
                                        airsim.YawMode(False, self.camera_heading)).join()  # Устанавливаем yaw на 0
        responses = self.client.simGetImages(
            [airsim.ImageRequest("Downward_Camera", airsim.ImageType.Scene)])  # Получаем изображение с камеры
        response = responses[0]

        # Определяем папку для сохранения фото
        save_directory = 'PHOTO'

        # Убедитесь, что директория существует
        if not os.path.exists(save_directory):
            os.makedirs(save_directory)  # Создаем директорию, если ее нет

        # Создаем имя файла с указанием директории
        filename = os.path.join(save_directory, "photo_" + str(self.snapshot_index) + '.png')
        self.snapshot_index += 1  # Увеличиваем индекс снимка

        # Сохраняем изображение
        airsim.write_file(os.path.normpath(filename), response.image_data_uint8)  # Сохранение изображения
        logging.info("Снимок сохранён: {}".format(filename))  # Сообщение о сохранении снимка

        self.start_time = time.time()  # Обновляем время


    def sign(self, s):
        """Функция для определения знака числа.

        Args:
            s: Число, для которого нужно определить знак.

        Returns:
            int: -1, если число меньше 0, 1, если больше или равно 0.
        """
        if s < 0:
            return -1
        return 1


# Пример использования
if __name__ == "__main__":
    # Создание экземпляра класса SurveyNavigator и запуск миссии
    # mission = SurveyNavigator(boxsize=30, stripewidth=10, altitude=30, velocity=10)
    # mission.start()  # Запуск обследования
    # mission.landed()  # Приземление после завершения миссии

    ##  Альтернатива: создание экземпляра класса OrbitNavigator
    mission = OrbitNavigator(radius=50, altitude=30, velocity=10, iterations=1, center=[1, 0], snapshots=5)
    mission.start()
    mission.landed()
