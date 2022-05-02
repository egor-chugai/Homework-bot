import os
import logging
from http import HTTPStatus
from logging.handlers import RotatingFileHandler
import telegram
import requests
import time
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('my_logger.log',
                              maxBytes=50000000,
                              backupCount=5)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def send_message(bot, message):
    """Sends a message to Telegram chat."""
    logger.info('Начало отправки сообщения')
    chat_id = TELEGRAM_CHAT_ID
    text = message
    try:
        bot.send_message(chat_id, text)
    except Exception as error:
        raise Exception(f'Сбой при отправке сообщения: {error}')
    else:
        logger.info('Удачная отправка сообщения')


def get_api_answer(current_timestamp):
    """Makes a request to the only endpoint of the API service."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            raise Exception(f'Недоступность эндпойнта '
                            f'{homework_statuses.status_code}')
        else:
            return homework_statuses.json()
    except Exception as error:
        raise Exception(f'Сбой при запросе к эндпойнту: {error}')


def check_response(response):
    """Checks the API response for correctness."""
    if not isinstance(response, dict):
        raise TypeError(f'По запросу к эндпойнту '
                        f'возвращается не словарь: {type(response)}')
    try:
        homeworks_value = response.get('homeworks')
        if not isinstance(homeworks_value, list):
            raise TypeError(f'По ключу homeworks возвращается '
                            f'не список: {type(homeworks_value)}')
        return homeworks_value
    except Exception as error:
        raise Exception(f'Отсутствие ожидаемых '
                        f'ключей в ответе API: {error}')


def parse_status(homework):
    """Gets the status of homework."""
    name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Недокументированный статус '
                         f'домашней работы {status}')
    return (f'Изменился статус проверки '
            f'работы "{name}". {HOMEWORK_VERDICTS[status]}')


def check_tokens():
    """Checks the availability of environment variables."""
    logger.info('Начинаем проверку обязательных '
                'переменных окружения')
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """The main logic of the bot."""
    if not check_tokens():
        logger.critical('Отсутствует одна из обязательных '
                        'переменных окружения')
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            if check_response(response):
                homework = check_response(response)
                if parse_status(homework[0]) != message:
                    message = parse_status(homework[0])
                    send_message(bot, message)
            else:
                current_timestamp = response.get("current_date")
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
