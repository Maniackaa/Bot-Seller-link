import asyncio

from aiogram import Dispatcher, types, Router, Bot, F
from aiogram.filters import Command, CommandStart, StateFilter, BaseFilter
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message, URLInputFile, ReplyKeyboardRemove

from aiogram.fsm.context import FSMContext

from config_data.bot_conf import get_my_loggers, conf
from database.db import User
from keyboards.keyboards import start_kb, contact_kb, admin_start_kb, custom_kb, menu_kb
from lexicon.lexicon import LEXICON
from services.db_func import get_or_create_user, update_user, create_request, get_request_from_id

logger, err_log = get_my_loggers()

router: Router = Router()


class FSMCheckUser(StatesGroup):
    age = State()
    exp = State()
    time = State()
    links = State()
    confirm = State()


@router.callback_query(F.data == 'cancel')
async def operation_in(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    await callback.message.delete()
    tg_user = callback.from_user
    print(tg_user)
    user: User = get_or_create_user(tg_user)
    print(user)
    if not user.is_active:
        await callback.message.answer('Сколько вам лет?')
        await state.set_state(FSMCheckUser.age)
    else:
        await callback.message.answer('Выберите раздел из меню', reply_markup=menu_kb)


@router.message(StateFilter(FSMCheckUser.age))
async def receive_age(message: Message, state: FSMContext):
    age = message.text.strip()
    await state.update_data(age=age)
    await message.answer('Какой опыт работы был раннее?')
    await state.set_state(FSMCheckUser.exp)


@router.message(StateFilter(FSMCheckUser.exp))
async def receive_exp(message: Message, state: FSMContext):
    exp = message.text.strip()
    await state.update_data(exp=exp)
    await message.answer('Пришлите ссылки на свои каналы (если нет напишите "нет")')
    await state.set_state(FSMCheckUser.links)


@router.message(StateFilter(FSMCheckUser.links))
async def receive_linx(message: Message, state: FSMContext):
    links = message.text.strip()
    await state.update_data(links=links)
    await message.answer('Сколько часов в день готовы уделять работе?')
    await state.set_state(FSMCheckUser.time)


@router.message(StateFilter(FSMCheckUser.time))
async def receive_time(message: Message, state: FSMContext):
    time = message.text.strip()
    await state.update_data(time=time)
    data = await state.get_data()
    text = 'Всё ли указано верно?\n\n'
    for row in data.values():
        text += row + '\n\n'
    confirm_btn = {
        'Отменить': 'cancel',
        'Отправить заявку': 'confirm'
    }
    await state.set_state(FSMCheckUser.confirm)
    await message.answer(text, reply_markup=custom_kb(2, confirm_btn))


def format_request(data):
    user: User = data['user']
    msg = (
        f'Заявка от {user.username} ({user.tg_id}):\n'
        f'Возраст:\n{data["age"]}\n\n'
        f'Опыт:\n{data["exp"]}\n\n'
        f'Ссылки:\n{data["links"]}\n\n'
        f'Возраст:\n{data["age"]}\n\n'
        f'Время:\n{data["time"]}\n'
    )
    return msg


@router.callback_query(StateFilter(FSMCheckUser.confirm), F.data == 'confirm')
async def in_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    try:
        await callback.message.delete_reply_markup()
        await callback.message.answer('Ваша завка отправлена. Ожидайте ответа.')
        data = await state.get_data()
        user = get_or_create_user(callback.from_user)
        data['user'] = user
        text = format_request(data)
        request_id = create_request(user, text)
        btn = {'Принять': f'confirm_user_{request_id}', 'Отклонить': f'reject_user_{request_id}'}
        request_msg = await bot.send_message(chat_id=conf.tg_bot.GROUP_ID, text=text, reply_markup=custom_kb(2, btn))
        request = get_request_from_id(request_id)
        request.set('msg', request_msg.model_dump_json())
        await state.clear()
    except Exception as err:
        logger.error(err)
        raise err
