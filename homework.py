import logging
import os
import sys
import time
from http import HTTPStatus
from json import JSONDecodeError

import requests
import telegram
from dotenv import load_dotenv
from requests import RequestException
from telegram import TelegramError

from exceptions import BotException


load_dotenv()


PRACTICUM_TOKEN = os.getenv("PRAKTIKUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def send_message(bot, message):
    """Отправляет сообщение в телеграм."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
    except TelegramError as error:
        logger.error(error, exc_info=True)


def get_api_answer(current_timestamp):
    """Возвращает API ответ от Яндекс Практикум."""
    try:
        timestamp = current_timestamp or int(time.time())
        params = {'from_date': timestamp}
        headers = {'Authorization': f'OAuth {os.getenv("PRAKTIKUM_TOKEN")}'}
        homework_statuses = requests.get(
            ENDPOINT, headers=headers, params=params)
        if homework_statuses.status_code != HTTPStatus.OK:
            raise BotException("Пришел некорректный ответ от сервера")
        else:
            return homework_statuses.json()
    except RequestException as error:
        logger.error(error, exc_info=True)
    except JSONDecodeError as error:
        logger.error(error, exc_info=True)


def check_response(response):
    """Извлекает из словаря ответа сервера список домашних работ."""
    if not isinstance(response, dict):
        raise TypeError('Ответ response не в формате dict')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise BotException('По ключу Homeworks пришел не список')
    return homeworks[0]


def parse_status(homework):
    """Возвращает статус проверки домашней работы."""
    if 'homework_name' not in homework or 'status' not in homework:
        raise KeyError("Нет ключей 'homework_name' и/или 'status' в ответе")
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status:
        verdict = HOMEWORK_STATUSES[homework_status]
    else:
        verdict = 'Отсутствует статус домашней работы на сервере'
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка наличия констант в переменных окружения."""
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True


def main():
    """Основная логика работы бота."""
    logger.info('Запуск бота')
    if not check_tokens():
        logger.critical('Отсутствуют переменные окружения.')
        raise BotException('Программа принудительно остановлена.'
                           ' Отсутствуют переменные окружения.')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            response = check_response(get_api_answer(
                current_timestamp - RETRY_TIME - RETRY_TIME))
            if response:
                send_message(bot, parse_status(response))
                logger.info(
                    "Сообщение об изменении статуса проверки работы "
                    "отправлено")
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.error(message, exc_info=True)
            time.sleep(RETRY_TIME)
        else:
            logger.debug(
                "Цикл проверки статуса домашней работы завершен без ошибок")


if __name__ == '__main__':
    main()
