from aiogram import Router, Bot, F
from aiogram.filters import Command, StateFilter, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove

from config_data.bot_conf import get_my_loggers, conf
from database.db import User
from keyboards.keyboards import start_kb, menu_kb
from lexicon.lexicon import LEXICON
from services.db_func import get_or_create_user, get_user_from_id, update_user, get_request_from_id, get_link_from_id, \
    get_work_request_from_id, create_work_link

logger, err_log = get_my_loggers()


class IsAdmin(BaseFilter):
    def __init__(self) -> None:
        self.admins = conf.tg_bot.admin_ids

    async def __call__(self, message: Message) -> bool:
        # print(f'Проверка на админа\n'
        #       f'{message}\n'
        #       f'{message.from_user.id} in {self.admins}\n'
        #       f'{str(message.from_user.id) in self.admins}')
        return str(message.from_user.id) in self.admins


class IsFromGroup(BaseFilter):
    def __init__(self) -> None:
        self.moderator_chat_id = conf.tg_bot.GROUP_ID

    async def __call__(self, message: Message | CallbackQuery) -> bool:
        if isinstance(message, CallbackQuery):
            message = message.message
        # print(f'Проверка на группу\n'
        #       f'{message.chat.id} == {self.moderator_chat_id}\n' )
        return str(message.chat.id) in self.moderator_chat_id


router = Router()
router.message.filter(IsFromGroup())
router.callback_query.filter(IsFromGroup())


class FSMAdmin(StatesGroup):
    a = State()
    reject = State()


class FSMLink(StatesGroup):
    confirm = State()
    reject = State()


@router.message(Command(commands=["start"]))
async def process_start_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer('Состояние сброшено')


@router.callback_query(F.data.startswith('confirm_user_'))
async def in_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    logger.debug(callback.data)
    request_id = int(callback.data.split('confirm_user_')[-1])
    request = get_request_from_id(request_id)
    user = get_user_from_id(request.user_id)
    update_user(user, {'is_active': 1})
    request.set('status', 1)
    await bot.send_message(chat_id=user.tg_id, text='Ваша заяка одобрена')
    await bot.send_message(chat_id=user.tg_id, text='выберите раздел:', reply_markup=menu_kb)
    await callback.message.edit_reply_markup(None)
    await callback.message.edit_text(text=callback.message.text + f'<b>\n\nОдобрено</b> {callback.from_user.username or callback.from_user.id}')
    await state.clear()


@router.callback_query(F.data.startswith('reject_user_'))
async def reject(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await state.set_state(FSMAdmin.reject)
    request_id = int(callback.data.split('reject_user_')[-1])
    await state.update_data(request_id=request_id, msg=callback.message)
    await callback.message.edit_reply_markup(None)
    await callback.message.answer('Укажите причину:')


@router.message(StateFilter(FSMAdmin.reject))
async def operation_cost(message: Message, state: FSMContext, bot: Bot):
    reject_text = message.text.strip()
    data = await state.get_data()
    msg = data['msg']
    request_id = data['request_id']
    request = get_request_from_id(request_id)
    client = get_user_from_id(request.user_id)
    request.set('status', -1)
    request.set('reject_text', reject_text)
    await bot.send_message(chat_id=client.tg_id, text=f'Ваша заяка отклонена:\n{reject_text}')
    await msg.edit_text(text=msg.text + f'<b>\n\nОтклонено {message.from_user.username or message.from_user.id}\n{reject_text}</b>')
    await state.clear()


# Подтверждение ссылок
@router.callback_query(F.data.startswith('link_confirm_'))
async def link_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    logger.debug(callback.data)
    await state.set_state(FSMLink.confirm)
    await state.update_data(msg=callback.message)
    link_id = int(callback.data.split('link_confirm_')[-1])
    await state.update_data(link_id=link_id)
    await callback.message.answer(f'Подтверждение ссылки № {link_id}:\nВведите сумму')


@router.message(StateFilter(FSMLink.confirm))
async def link_confirm_cost(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    link_id = data['link_id']
    try:
        moderator = get_or_create_user(message.from_user)
        cost = int(message.text.strip())
        link = get_link_from_id(link_id)
        link.set('status', 'confirmed')
        link.set('moderator_id', moderator.id)
        link.set('cost', cost)
        msg = data['msg']
        link = get_link_from_id(link_id)
        await bot.edit_message_text(text=msg.text + f'\nПринято {moderator.username or moderator.tg_id} ({cost})',
                                    chat_id=conf.tg_bot.GROUP_ID, message_id=msg.message_id)
        await message.answer(f'Cсылка № {link.id} принята:\n{link.link}\n\nСтоимость: {cost}.')
        client = get_user_from_id(link.owner_id)
        new_cash = client.cash + cost
        client.set('cash', new_cash)
        await bot.send_message(chat_id=client.tg_id, text=f'Ваша ссылка № {link.id} принята:\n{link.link}\n\nСтоимость: {cost}. Баланс: {client.cash}')
    except Exception as err:
        logger.error(err)
        await message.answer(f'Подтверждение ссылки № {link_id}:\nВведите сумму')
        raise err




# Отклонение ссылок

@router.callback_query(F.data.startswith('link_reject_'))
async def link_reject_(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await state.set_state(FSMLink.reject)
    await state.update_data(msg=callback.message)
    link_id = int(callback.data.split('link_reject_')[-1])
    await state.update_data(link_id=link_id)
    await callback.message.answer(f'Отлонение ссылки № {link_id}:\nВведите прчину')


@router.message(StateFilter(FSMLink.reject))
async def link_confirm_cost(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    link_id = data['link_id']
    moderator = get_or_create_user(message.from_user)
    verdict = message.text.strip()
    link = get_link_from_id(link_id)
    link.set('status', 'rejected')
    link.set('moderator_id', moderator.id)
    msg = data['msg']
    link = get_link_from_id(link_id)
    await bot.edit_message_text(text=msg.text + f'\nОтклонено {moderator.username or moderator.tg_id}\n({verdict})',
                                chat_id=conf.tg_bot.GROUP_ID, message_id=msg.message_id)
    await message.answer(f'Cсылка № {link.id} отклонена:\n{link.link}\n\nПричина: {verdict}.')
    client = get_user_from_id(link.owner_id)
    await bot.send_message(chat_id=client.tg_id, text=f'Ваша ссылка № {link.id} отклонена:\n{link.link}\n\nПричина:\n{verdict}.')
    await state.clear()
#
# @router.callback_query(F.data.startswith('link_reject_'))
# async def link_reject(callback: CallbackQuery, state: FSMContext, bot: Bot):
#     logger.debug(callback.data)
#     await state.update_data(msg=callback.message)
#     link_id = int(callback.data.split('link_reject_')[-1])
#     link = get_link_from_id(link_id)
#     client = get_user_from_id(link.owner_id)
#     msg = callback.message
#     moderator = get_or_create_user(callback.from_user)
#     link.set('status', 'rejected')
#     link.set('moderator_id', moderator.id)
#     link = get_link_from_id(link_id)
#     await bot.edit_message_text(text=msg.text + f'\nОтклонено {moderator.username or moderator.tg_id}',
#                                 chat_id=conf.tg_bot.GROUP_ID, message_id=msg.message_id)
#     await bot.send_message(chat_id=client.tg_id, text=f'Ваша ссылка отклонена!\n{link.link}')
#     await state.clear()


# Заявки на рабочую ссылку **********************
class FSMChatWorkReg(StatesGroup):
    confirm = State()
    reject = State()


@router.callback_query(F.data.startswith('reject_req_work:'))
async def group_reject_work_reg(callback: CallbackQuery, state: FSMContext, bot: Bot):
    print(callback.data)
    await state.set_state(FSMChatWorkReg.reject)
    request_id = int(callback.data.split('reject_req_work:')[-1])
    await state.update_data(request_id=request_id, msg=callback.message)
    await callback.message.answer('Укажите причину:')


@router.message(StateFilter(FSMChatWorkReg.reject))
async def operation_cost(message: Message, state: FSMContext, bot: Bot):
    reject_text = message.text.strip()
    data = await state.get_data()
    request_id = data['request_id']
    request = get_work_request_from_id(request_id)
    client = get_user_from_id(request.owner_id)
    request.set('status', -1)
    request.set('reject_text', reject_text)
    request = get_work_request_from_id(request_id)
    msg = data['msg']
    await state.clear()
    await bot.send_message(chat_id=client.tg_id, text=f'Ваша заяка на выдачу рабочей ссылки отклонена:\n{reject_text}')
    await message.answer(text=f'Заявка отклонена\n{request.reject_text}')
    await state.clear()
    await msg.edit_text(text=msg.text + f'<b>\n\nОтклонено {message.from_user.username or message.from_user.id}\n{reject_text}</b>')


@router.callback_query(F.data.startswith('confirm_req_work:'))
async def work_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    logger.debug(callback.data)
    request_id = int(callback.data.split('confirm_req_work:')[-1])
    await callback.message.answer('Укажите рабочую ссылку')
    await state.set_state(FSMChatWorkReg.confirm)
    await state.update_data(request_id=request_id, msg=callback.message)


@router.message(StateFilter(FSMChatWorkReg.confirm))
async def link_confirm_cost(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    request_id = data['request_id']
    worklink = message.text.strip()
    moderator = get_or_create_user(message.from_user)
    request = get_work_request_from_id(request_id)
    request.set('status', 1)
    request.set('moderator_id', moderator.id)
    msg = data['msg']
    request = get_work_request_from_id(request_id)
    await message.answer(f'Заявка на выдачу ссылки № {request.id} принята. {worklink}')
    # Отправка клиенту
    client = get_user_from_id(request.owner_id)
    create_work_link(user_id=client.id, link=worklink, moderator_id=moderator.id)
    await bot.send_message(chat_id=client.tg_id,
                           text=f'Ваша Заявка № {request.id} принята:\n{worklink}')
    # Меняем сообщение в группе
    await bot.edit_message_text(text=msg.text + f'\nПринято {moderator.username or moderator.tg_id}\n{worklink}',
                                chat_id=conf.tg_bot.GROUP_ID, message_id=msg.message_id)
