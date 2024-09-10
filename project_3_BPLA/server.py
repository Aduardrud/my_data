from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta, datetime
from flask_cors import CORS
from flask_jwt_extended.exceptions import NoAuthorizationError
import logging
import psutil
from flask_caching import Cache

from missions import SurveyNavigator, OrbitNavigator

# Настройка логирования
logging.basicConfig(level=logging.INFO, filemode="w")

app = Flask(__name__)

CORS(app)  # Разрешаем все CORS запросы
app.config['JWT_SECRET_KEY'] = 'AbraKadabra'  # Секретный ключ для подписи токенов

# Настройка кэширования
cache = Cache(config={'CACHE_TYPE': 'simple'})
cache.init_app(app)

jwt = JWTManager(app)

users = {}  # Словарь для хранения пользователей
missions = {}  # Словарь для хранения активных миссий

@app.route('/api/system_info', methods=['GET'])
@cache.memoize(timeout=5)  # Кэшировать результат на 5 секунд
def get_system_info():
    """Возвращает информацию о системе (процентное использование ЦП, памяти и дискового пространства).
        Returns: dict: Словарь с информацией о системе.
        """
    cpu_percent = psutil.cpu_percent(interval=1)
    memory_percent = psutil.virtual_memory().percent
    disk_usage = psutil.disk_usage('/').percent
    return jsonify({'cpu_percent': cpu_percent, 'memory_percent': memory_percent, 'disk_usage': disk_usage})

@app.route('/api/register', methods=['POST'])
def register():
    """Регистрирует нового пользователя.
        Returns: tuple: Кортеж, содержащий JSON-ответ с сообщением и HTTP-статус.
        """
    print("Запрос получен на /api/register")  # Лог получения запроса
    try:
        json_data = request.json
        print("Полученные данные: ", json_data)  # Получаем данные из запроса в формате JSON
        if not json_data:
            return jsonify({'msg': 'Пустые данные'}), 400

        username = json_data.get('username')
        password = json_data.get('password')
        print(f"Данные запроса: username={username}, password={password}")


        if not username or not password:
            return jsonify({'msg': 'Некорректные данные'}), 400


        if username in users:
            return jsonify({'msg': f"Пользователь {username} уже существует."}), 400


        users[username] = password
        logging.info(f"Пользователь {username} успешно зарегистрирован.")
        return jsonify({'msg': f"Пользователь {username} успешно зарегистрирован."}), 201

    except Exception as e:
        print(f"Ошибка: {e}")
        return jsonify({'msg': 'Ошибка при обработке запроса'}), 500


@app.route('/api/login', methods=['POST'])
def login():
    """Выполняет вход пользователя и возвращает токен доступа.
       Returns: tuple: Кортеж, содержащий JSON-ответ с токеном доступа и HTTP-статус.
       """
    username = request.json.get('username')
    password = request.json.get('password')

    if users.get(username) != password:
        return jsonify({'msg': 'Неверные учетные данные'}), 401

    expiration = datetime.utcnow() + timedelta(hours=1)
    logging.info(f"Текущее время: {datetime.utcnow()}")
    logging.info(f"Токен действителен до: {expiration}")


    # Генерация токена
    access_token = create_access_token(identity=username, expires_delta=timedelta(hours=1))

    return jsonify(access_token=access_token, exp=expiration.timestamp()), 200


@app.route('/api/users', methods=['GET'])
@jwt_required()  # Проверка наличия токена в токенах
def get_users():
    """Возвращает список всех зарегистрированных пользователей.
        Returns: tuple: Кортеж, содержащий JSON-ответ со списком пользователей и HTTP-статус.
        """
    current_user = get_jwt_identity()
    logging.info(f"Текущий пользователь: {current_user}")  # Получаем данные из токена
    return jsonify(users), 200


@app.route('/api/survey_navigator/start', methods=['POST'])
@jwt_required()
def start_survey_navigator():
    """Запускает миссию дрона для выполнения съемки.
            Returns:
                tuple: Кортеж, содержащий JSON-ответ с сообщением и HTTP-статус.
            """
    try:
        current_user = get_jwt_identity()
        logging.info(f"Дрон запущен пользователем {current_user}")

        # Извлечение данных из запроса
        json_data = request.json
        if not json_data:
            return jsonify({'msg': 'Пустые данные в запросе'}), 400

        # Получение необходимых параметров из JSON
        boxsize = json_data.get('boxsize')
        stripewidth = json_data.get('stripewidth')
        altitude = json_data.get('altitude')
        velocity = json_data.get('velocity')

        # Проверка наличия всех необходимых параметров
        if not all([boxsize, stripewidth, altitude, velocity]):
            return jsonify({'msg': 'Отсутствуют необходимые параметры: boxsize, stripewidth, altitude и velocity'}), 400

        # Создание и запуск дрона
        mission = SurveyNavigator(boxsize=boxsize, stripewidth=stripewidth, altitude=altitude, velocity=velocity)
        mission.start()
        missions[current_user] = mission  # Сохраняем миссию для текущего пользователя
        return jsonify({'msg': 'Дрон запущен'}), 200

    except Exception as e:
        logging.error(f"Ошибка при запуске дрона: {e}")
        return jsonify({'msg': 'Ошибка при запуске дрона'}), 500


@app.route('/api/survey_navigator/land', methods=['POST'])
@jwt_required()
def land_survey_navigator():
    """Останавливает миссию дрона выполнения обзорной съемки.
        Returns:
            tuple: Кортеж, содержащий JSON-ответ с сообщением и HTTP-статус.
        """
    try:
        current_user = get_jwt_identity()
        logging.info(f"Попытка посадить дрон пользователем {current_user}")

        # Получаем миссию текущего пользователя
        mission = missions.get(current_user)
        if mission is None:
            return jsonify({'msg': 'Нет активной миссии для остановки'}), 400

        mission.landed()  # Останавливаем миссию дрона
        del missions[current_user]  # Удаляем миссию после остановки
        logging.info(f"Дрон остановлен пользователем {current_user}")
        return jsonify({'msg': 'Дрон остановлен'}), 200

    except Exception as e:
        logging.error(f"Ошибка при остановке дрона: {e}")
        return jsonify({'msg': 'Ошибка при остановке дрона'}), 500


@app.route('/api/orbit_navigator/start', methods=['POST'])
@jwt_required()
def start_orbit_navigator():
    """Запускает миссию дрона для выполнения съемки.
        Returns:
            tuple: Кортеж, содержащий JSON-ответ с сообщением и HTTP-статус.
        """
    try:
        current_user = get_jwt_identity()
        logging.info(f"Дрон запущен пользователем {current_user}")

        # Извлечение данных из запроса
        json_data = request.json
        if not json_data:
            return jsonify({'msg': 'Пустые данные в запросе'}), 400

        # Получение необходимых параметров из JSON
        radius = json_data.get('radius')
        altitude = json_data.get('altitude')
        velocity = json_data.get('velocity')
        iterations = json_data.get('iterations')
        center = json_data.get('center')
        snapshots = json_data.get('snapshots')

        # Проверка наличия всех необходимых параметров
        if not all([radius, altitude, velocity, iterations, center, snapshots]):
            return jsonify({
                               'msg': 'Отсутствуют необходимые параметры: radius, altitude, velocity, iterations, center и snapshots'}), 400

        # Создание и запуск дрона
        mission = OrbitNavigator(radius=radius, altitude=altitude, velocity=velocity, iterations=iterations,
                                 center=center, snapshots=snapshots)
        mission.start()
        missions[current_user] = mission  # Сохраняем миссию для текущего пользователя
        return jsonify({'msg': 'Миссия выполнена'}), 200

    except Exception as e:
        logging.error(f"Ошибка при запуске дрона: {e}")
        return jsonify({'msg': 'Ошибка при запуске дрона'}), 500

@app.route('/api/orbit_navigator/land', methods=['POST'])
@jwt_required()
def land_orbit_navigator():
    """Останавливает миссию дрона выполнения съемки.
        Returns:
            tuple: Кортеж, содержащий JSON-ответ с сообщением и HTTP-статус.
        """
    try:
        current_user = get_jwt_identity()
        logging.info(f"Попытка посадить дрон пользователем {current_user}")

        # Получаем миссию текущего пользователя
        mission = missions.get(current_user)
        if mission is None:
            return jsonify({'msg': 'Нет активной миссии для остановки'}), 400

        mission.landed()  # Останавливаем миссию дрона
        del missions[current_user]  # Удаляем миссию после остановки
        logging.info(f"Дрон остановлен пользователем {current_user}")
        return jsonify({'msg': 'Дрон остановлен'}), 200

    except Exception as e:
        logging.error(f"Ошибка при остановке дрона: {e}")
        return jsonify({'msg': 'Ошибка при остановке дрона'}), 500


@app.errorhandler(NoAuthorizationError)
def handle_auth_error(e):
    """Обрабатывает ошибку авторизации, когда токен не найден или недействителен.
        Args:
            e (NoAuthorizationError): Ошибка авторизации.
        """
    logging.info("Ошибка авторизации: токен не найден или недействителен")



if __name__ == '__main__':
    app.run(port=5000)