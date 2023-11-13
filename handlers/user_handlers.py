import asyncio

from aiogram import Dispatcher, types, Router, Bot, F
from aiogram.filters import Command, CommandStart, StateFilter, BaseFilter
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message, URLInputFile, ReplyKeyboardRemove, Chat

from aiogram.fsm.context import FSMContext

from config_data.bot_conf import get_my_loggers, conf
from database.db import User
from handlers.new_user import FSMCheckUser
from keyboards.keyboards import start_kb, contact_kb, admin_start_kb, custom_kb, menu_kb, kb_list
from lexicon.lexicon import LEXICON
from services.db_func import get_or_create_user, update_user, create_links, get_link_from_id, create_work_link_request, \
    get_work_request_from_id, create_cash_outs, get_cash_out_from_id
from services.func import get_all_time_cash, get_all_worked_link

logger, err_log = get_my_loggers()


class IsPrivate(BaseFilter):
    async def __call__(self, message: Message | CallbackQuery) -> bool:
        if isinstance(message, CallbackQuery):
            message = message.message
        # print(f'Проверка на частность: {message.chat.type}\n')
        return message.chat.type == 'private'


router: Router = Router()
router.message.filter(IsPrivate())


class FSMUser(StatesGroup):
    send_link = State()

class FSMCash(StatesGroup):
    cost = State()


@router.message(Command(commands=["start"]))
async def process_start_command(message: Message, state: FSMContext):
    logger.debug('new')
    try:
        await state.clear()
        tg_user = message.from_user
        user: User = get_or_create_user(tg_user)
        if not user.is_active:
            await message.answer('Сколько вам лет?')
            await state.set_state(FSMCheckUser.age)
        else:
            await message.answer('Выберите раздел в меню', reply_markup=menu_kb)
    except Exception as err:
        logger.error(err)


# @router.callback_query(F.data == 'support')
# async def support(callback: CallbackQuery, state: FSMContext, bot: Bot):
#     text = LEXICON.get('support')
#     await callback.message.edit_text(text, reply_markup=start_kb)
@router.message(F.text == kb_list[4])
async def support(message: Message, state: FSMContext):
    text = LEXICON.get('support')
    await message.answer(text)


# @router.callback_query(F.data == 'instructions')
# async def instructions(callback: CallbackQuery, state: FSMContext, bot: Bot):
#     text = LEXICON.get('instructions')
#     await callback.message.edit_text(text, reply_markup=start_kb)
@router.message(F.text == kb_list[2])
async def instructions(message: Message, state: FSMContext):
    text = LEXICON.get('instructions')
    await message.answer(text)


def get_link_text(data):
    return 'data'


# @router.callback_query(F.data == 'send_link')
# async def send_link(callback: CallbackQuery, state: FSMContext, bot: Bot):
#     await callback.message.edit_text('Вставьте ссылки')
#     await state.set_state(FSMUser.send_link)
@router.message(F.text == kb_list[0])
async def instructions(message: Message, state: FSMContext):
    await message.answer('Вставьте ссылки (одна ссылка на строке)', reply_markup=ReplyKeyboardRemove())
    await state.set_state(FSMUser.send_link)


@router.message(StateFilter(FSMUser.send_link))
async def receive_link(message: Message, state: FSMContext):
    raw_links = message.text.split('\n')
    raw_links = [link.strip() for link in raw_links]
    links = []
    for link in raw_links:
        if 'http' in link:
            links.append(link)
    if links:
        await state.update_data(links=links)
        confirm_btn = {
            'Отменить': 'cancel',
            'Отправить': 'link_confirm'
        }
        text = 'Подтвердите отправку ссылок:\n'
        text += '\n'.join(links)
        await message.answer(text, reply_markup=custom_kb(2, confirm_btn))
    else:
        await message.answer('Не корректные сылки', reply_markup=menu_kb)
        await state.clear()


@router.callback_query(StateFilter(FSMUser.send_link), F.data == 'link_confirm')
async def link_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.edit_reply_markup(None)
    data = await state.get_data()
    links = data.get('links')
    user = get_or_create_user(callback.from_user)
    link_ids = create_links(user, links)
    # await callback.message.delete()
    # Отправка на модерацию:
    for link_id in link_ids:
        link = get_link_from_id(link_id)
        text = f'Ссылка № {link_id} от {user.username or user.tg_id}:\n{link.link}'
        btn = {'Подтвердить': f'link_confirm_{link_id}', 'Отклонить': f'link_reject_{link_id}'}
        msg = await bot.send_message(chat_id=conf.tg_bot.GROUP_ID, text=text, reply_markup=custom_kb(2, btn))
        logger.debug(f'Ссылка {link_id} отправлена на модерацию')
        link.set('msg', msg.model_dump_json())
        link.set('status', 'moderate')
        await asyncio.sleep(0.2)
    await callback.message.answer('Ссылки отправлены на модерацию', reply_markup=menu_kb)
    # await callback.message.answer('Чат для модераторов: https://t.me/+llTdzJJuK0kwN2My')
    await state.clear()


# Аккаунт
def get_all_worked_link_count(user):
    pass


@router.message(F.text == kb_list[1])
async def send_link(message: Message, state: FSMContext, bot: Bot):
    user = get_or_create_user(message.from_user)
    alltime_cash = get_all_time_cash(user)
    text = 'Ваш аккаунт\n'
    text += f'Текущий баланс: {user.cash}\n'
    text += f'Общий баланс: {alltime_cash}\n'
    links = get_all_worked_link(user)
    links_text = '\n'.join([link.link for link in links])
    text += f'Кол-во ссылок: {len(links)}\n{links_text}'
    btn = {
        'Заказать выплату': 'cash_out',
        # 'Пополнить баланс': 'cash_in',
        'Назад': 'cancel'
    }
    await message.answer(text=text, reply_markup=custom_kb(1, btn))


# Купить Аккаунт
@router.callback_query(F.data == 'buy_account')
async def buy_account(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user = get_or_create_user(callback.from_user)
    text = 'Доступные каналы:\n'
    btn = {
        'Купить': 'cash_out',
        'Назад': 'cancel'
    }
    await callback.message.edit_text(text=text, reply_markup=custom_kb(1, btn))


# Продать Аккаунт **********************************************
class FSMSellAccount(StatesGroup):
    input = State()
    keys = [
        'Ссылка на канал',
        'Год создания',
        'Сумма',
    ]


@router.callback_query(F.data == 'sell_account')
async def sell_account(callback: CallbackQuery, state: FSMContext, bot: Bot):
    text = 'Здесь вы можете продать канал'
    btn = {
        'Оставить заявку на продажу': 'sell_account:0',
        'Назад': 'cancel'
    }
    await callback.message.edit_text(text=text, reply_markup=custom_kb(1, btn))


@router.callback_query(F.data.startswith('sell_account:'))
async def sell_account(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(FSMSellAccount.input)
    text = FSMSellAccount.keys[0]
    await state.update_data(index=0)
    await callback.message.answer(text=text)
    await state.set_state(FSMSellAccount.input)


def get_sell_account_request_text(message, data):
    answers = data.get('answers')
    request = f'Заявка на продажу канала от @{message.from_user.username or message.from_user.id}:\n\n'
    for key_index, key in enumerate(FSMSellAccount.keys):
        request += f'{key}: {answers[key_index]}\n\n'
    return request


@router.message(StateFilter(FSMSellAccount.input))
async def sell_account(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    answers = data.get('answers', [])
    answer = message.text
    index = data['index']
    if index == 1:
        try:
            if int(answer.strip()) >= 2016:
                await message.answer('Год должен быть меньше 2016')
                return
        except Exception as err:
            await message.answer('Год должен быть меньше 2016')
            return

    answers.append(answer)
    index += 1
    await state.update_data(index=index, answers=answers)
    if index < len(FSMSellAccount.keys):
        text = FSMSellAccount.keys[index]
        await message.answer(text)
    else:
        print('Конец')
        request = get_sell_account_request_text(message, data)
        btn = {
            'Подтвердить': 'sell_account_confirm',
            'Отменить': 'cancel'
        }
        await message.answer(f'Подтвердите заявку:\n\n{request}', reply_markup=custom_kb(2, btn))


@router.callback_query(F.data == 'sell_account_confirm')
async def sell_account_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    request = get_sell_account_request_text(callback.message, data)
    await callback.message.edit_reply_markup(None)
    await bot.send_message(chat_id=conf.tg_bot.GROUP_ID, text=request)
    await callback.message.answer('Ваша заявка отправлена')
# Конец блока Продать Аккаунт ****************************************************


# Запрос на получение рабочей ссылки
@router.message(F.text == kb_list[3])
async def instructions(message: Message, state: FSMContext):
    btn = {
        'Подтвердить': 'work_link_confirm',
        'Отменить': 'cancel'
    }
    await message.answer(f'Отправить заявку?', reply_markup=custom_kb(2, btn))


@router.callback_query(F.data == 'work_link_confirm')
async def sell_account_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user = get_or_create_user(callback.from_user)
    work_id = create_work_link_request(user)
    btn = {'Подтвердить': f'confirm_req_work:{work_id}', 'Отклонить': f'reject_req_work:{work_id}'}
    text = f'Заявка на рабочую ссылку № {work_id} от @{callback.message.from_user.username or callback.message.from_user.id}'
    msg = await bot.send_message(chat_id=conf.tg_bot.GROUP_ID, text=text, reply_markup=custom_kb(2, btn))
    work_request = get_work_request_from_id(work_id)
    work_request.set('msg', msg.model_dump_json())
    await callback.message.answer('Ваша заявка отправлена')
    await callback.message.delete()


# Запрос на вывод средств
@router.callback_query(F.data == 'cash_out')
async def sell_account_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    btn = {
        'Подтвердить': 'cash_out_confirm',
        'Отменить': 'cancel'
    }
    user = get_or_create_user(callback.from_user)

    cash = user.cash
    text = f'Ваш баланс: {cash}\nОставить заявку на вывод?'
    if cash >= 1000:
        await callback.message.edit_text(text, reply_markup=custom_kb(2, btn))
    else:
        await callback.message.answer('Минимальная сумма вывода 1000 р.')


@router.callback_query(F.data == 'cash_out_confirm')
async def cash_conf(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.delete()
    await state.set_state(FSMCash.cost)
    await callback.message.answer('Введите сумму')


@router.message(StateFilter(FSMCash.cost))
async def cash_cost(message: Message, state: FSMContext):
    cost = message.text.strip()
    try:
        cost = int(cost)
        if cost >= 1000:
            btn = {
                'Подтвердить': f'cash_out_send',
                'Отменить': 'cancel'
            }
            await state.update_data(cost=cost)
            await message.answer(f'Отправить заявку на вывод {cost} р.?', reply_markup=custom_kb(2, btn))
        else:
            await message.answer(f'Сумма должна быть не менее 1000 р.')
    except Exception as err:
        await message.answer('Некорректная сумма. Введите корректную сумму')


@router.callback_query(F.data == 'cash_out_send')
async def cash_conf(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.delete()
    data = await state.get_data()
    cost = data['cost']
    user = get_or_create_user(callback.from_user)
    cash_out_id = create_cash_outs(user.id, cost)
    btn = {'Подтвердить': f'cash_out_confirm:{cash_out_id}',
           'Отклонить': f'cash_out_reject:{cash_out_id}'}
    await callback.message.answer(f'Ваша заявка № {cash_out_id} на вывод {cost} р. отправлена')
    text = f'Заявка № {cash_out_id} на вывод {cost} р. от @{user.username or user.tg_id}'
    msg = await bot.send_message(chat_id=conf.tg_bot.GROUP_ID, text=text, reply_markup=custom_kb(2, btn))
    cash_out = get_cash_out_from_id(cash_out_id)
    cash_out.set('msg', msg.model_dump_json())
    await state.clear()