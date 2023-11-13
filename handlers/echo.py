from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, Chat

from config_data.bot_conf import get_my_loggers

logger, err_log = get_my_loggers()

router: Router = Router()


# Последний эхо-фильтр
@router.message()
async def send_echo(message: Message):
    print('echo message:', message.text)
    print(message.content_type)
    logger.debug(message.chat)

@router.callback_query()
async def send_echo(callback: CallbackQuery):
    print('echo callback:', callback.data)

