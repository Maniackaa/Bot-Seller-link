import json
import time

from aiogram import Router, Bot, F
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Command, StateFilter, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove

from config_data.bot_conf import get_my_loggers, conf
from database.db import User
from keyboards.keyboards import start_kb, admin_start_kb, custom_kb
from lexicon.lexicon import LEXICON
from services.db_func import get_or_create_user, get_user_from_id, update_user, get_request_from_id, get_link_from_id, \
    get_reg_from_id, get_work_request_from_id, create_work_link
from services.func import get_users_with_uncofirmed_link, get_user_uncofirmed_link, get_unconfirmed_reg, \
    get_unconfirmed_work_req

logger, err_log = get_my_loggers()


class IsAdminPrivate(BaseFilter):
    def __init__(self) -> None:
        self.GROUP_ID = int(conf.tg_bot.GROUP_ID)

    async def __call__(self, message: Message, event_from_user, bot: Bot, *args, **kwargs) -> bool:
        if isinstance(message, CallbackQuery):
            message = message.message
        member = await bot.get_chat_member(chat_id=self.GROUP_ID, user_id=event_from_user.id)
        status = member.status
        is_moderator = status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
        return is_moderator and message.chat.type == 'private'


router = Router()
router.message.filter(IsAdminPrivate())
router.callback_query.filter(IsAdminPrivate())


class FSMAdminLink(StatesGroup):
    confirm = State()
    reject = State()


class FSMAdminReg(StatesGroup):
    confirm = State()
    reject = State()


@router.callback_query(F.data == 'cancel')
async def operation_in(callback: CallbackQuery, state: FSMContext, bot: Bot):
    logger.debug('admin start')
    await callback.message.delete()
    await callback.message.answer('Режим модератора', reply_markup=ReplyKeyboardRemove())
    await callback.message.answer('Главное меню модератора', reply_markup=admin_start_kb)


@router.message(Command(commands=["start"]))
async def process_start_command(message: Message, state: FSMContext):
    logger.debug('admin start')
    await message.answer('Режим модератора', reply_markup=ReplyKeyboardRemove())
    await message.answer('Главное меню модератора', reply_markup=admin_start_kb)


# Не подтвержденые ссылки
@router.callback_query(F.data == 'link_list')
async def link_list(callback: CallbackQuery, state: FSMContext, bot: Bot):
    users_with_uncofirmed_link = get_users_with_uncofirmed_link()
    btn = {}
    for user in users_with_uncofirmed_link:
        count = get_user_uncofirmed_link(user.id)
        count = len(count) if count else 0
        btn[f'{user.username or user.tg_id} ({count})'] = f'user_link_list:{user.id}'
    btn['Отмена'] = 'cancel'
    await callback.message.edit_text('Заявки.\nВыберите пользователя', reply_markup=custom_kb(1, btn))


@router.callback_query(F.data.startswith('user_link_list:'))
async def in_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.delete()
    user_id = int(callback.data.split('user_link_list:')[-1])
    user = get_user_from_id(user_id)
    text = f'Ссылки пользователя {user.username or user.tg_id} на модерации:\n'
    for link in user.links:
        if link.status == 'moderate':
            text += f'{link.id}. {link.link}\n'
    btn = {'Модерировать': f'moderate_link:{user_id}', 'Назад': 'link_list'}
    await callback.message.answer(text, reply_markup=custom_kb(2, btn))


@router.callback_query(F.data.startswith('moderate_link:'))
async def moderate_link(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.delete()
    user_id = int(callback.data.split('moderate_link:')[-1])
    user = get_user_from_id(user_id)
    for link in user.links:
        if link.status == 'moderate':
            btn = {'Подтвердить': f'link_confirm_{link.id}', 'Отклонить': f'link_reject_{link.id}'}
            text = f'Ссылка № {link.id} от {user.username or user.tg_id}:\n{link.link}'
            await callback.message.answer(text, reply_markup=custom_kb(2, btn))


@router.callback_query(F.data.startswith('link_confirm_'))
async def admin_link_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    logger.debug(callback.data)
    await state.set_state(FSMAdminLink.confirm)

    link_id = int(callback.data.split('link_confirm_')[-1])
    await state.update_data(link_id=link_id, private_msg=callback.message)
    await callback.message.answer(f'Подтверждение ссылки № {link_id}:\nВведите сумму')


@router.message(StateFilter(FSMAdminLink.confirm))
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
        link = get_link_from_id(link_id)
        msg = Message(**json.loads(link.msg))
        msg = Message.model_validate(msg).as_(bot)
        # Меняем сообщение вличке
        private_msg: Message = data['private_msg']
        await private_msg.delete()
        await message.answer(f'Cсылка № {link.id} принята:\n{link.link}\n\nСтоимость: {cost}.')
        # Отправка клиенту
        client = get_user_from_id(link.owner_id)
        new_cash = client.cash + cost
        client.set('cash', new_cash)
        await bot.send_message(chat_id=client.tg_id,
                               text=f'Ваша ссылка № {link.id} принята:\n{link.link}\n\nСтоимость: {cost}. Баланс: {client.cash}')
        # Меняем сообщение в группе
        await bot.edit_message_text(text=msg.text + f'\nПринято {moderator.username or moderator.tg_id} ({cost})',
                                    chat_id=conf.tg_bot.GROUP_ID, message_id=msg.message_id)
    except Exception as err:
        logger.error(err, exc_info=True)
        await message.answer(f'Подтверждение ссылки № {link_id}:\nВведите сумму')
        raise err


# Отклонение ссылок
@router.callback_query(F.data.startswith('link_reject_'))
async def link_reject(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.delete()
    await state.set_state(FSMAdminLink.reject)
    link_id = int(callback.data.split('link_reject_')[-1])
    await state.update_data(link_id=link_id)
    await callback.message.answer(f'Отлонение ссылки № {link_id}:\nВведите прчину')


@router.message(StateFilter(FSMAdminLink.reject))
async def link_reject(message: Message, state: FSMContext, bot: Bot):
    verdict = message.text.strip()
    data = await state.get_data()
    link_id = data['link_id']
    link = get_link_from_id(link_id)
    client = get_user_from_id(link.owner_id)
    moderator = get_or_create_user(message.from_user)
    link.set('status', 'rejected')
    link.set('moderator_id', moderator.id)
    link = get_link_from_id(link_id)
    msg = Message(**json.loads(link.msg))
    msg = Message.model_validate(msg).as_(bot)
    await bot.send_message(chat_id=client.tg_id, text=f'Ваша ссылка отклонена!\n{link.link}\nПричина:\n{verdict}')
    await bot.edit_message_text(text=msg.text + f'\nОтклонено {moderator.username or moderator.tg_id}\nПричина:\n{verdict}',
                                chat_id=conf.tg_bot.GROUP_ID, message_id=msg.message_id)
    await message.answer(text=f'Ссылка отклонена!\n{link.link}\nПричина:\n{verdict}', reply_markup=admin_start_kb)
    await state.clear()

# Завяки на регистрацию (РЕГЗАЯВКА) ****************************
@router.callback_query(F.data == 'reg_list')
async def reg_list(callback: CallbackQuery, state: FSMContext, bot: Bot):
    uncofirmed_reg = get_unconfirmed_reg()
    btn = {}
    text = 'Заявки:\n'
    for reg in uncofirmed_reg:
        text += f'{reg.id}. {reg.text}\n'
        btn[f'Принять {reg.id} {reg.owner.username}'] = f'confirm_reg:{reg.id}'
        btn[f'Отклонить {reg.id} {reg.owner.username}'] = f'reject_reg:{reg.id}'
    btn['Отмена'] = 'cancel'
    await callback.message.edit_text(text=text, reply_markup=custom_kb(2, btn))


@router.callback_query(F.data.startswith('reject_reg:'))
async def reject_reg(callback: CallbackQuery, state: FSMContext, bot: Bot):
    print(callback.data)
    await callback.message.delete()
    await state.set_state(FSMAdminReg.reject)
    request_id = int(callback.data.split('reject_reg:')[-1])
    await state.update_data(request_id=request_id)
    await callback.message.answer('Укажите причину:')


@router.message(StateFilter(FSMAdminReg.reject))
async def operation_cost(message: Message, state: FSMContext, bot: Bot):
    reject_text = message.text.strip()
    data = await state.get_data()
    request_id = data['request_id']
    request = get_request_from_id(request_id)
    client = get_user_from_id(request.user_id)
    request.set('status', -1)
    request.set('reject_text', reject_text)
    reg = get_reg_from_id(request_id)
    msg = Message(**json.loads(reg.msg))
    msg = Message.model_validate(msg).as_(bot)
    await state.clear()
    await bot.send_message(chat_id=client.tg_id, text=f'Ваша заяка отклонена:\n{reject_text}')
    await message.answer(text=f'Заявка отклонена\n{reg.text}')
    await state.clear()
    await msg.edit_text(text=msg.text + f'<b>\n\nОтклонено {message.from_user.username or message.from_user.id}\n{reject_text}</b>')


@router.callback_query(F.data.startswith('confirm_reg:'))
async def in_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    logger.debug(callback.data)
    request_id = int(callback.data.split('confirm_reg:')[-1])
    request = get_request_from_id(request_id)
    user = request.owner
    update_user(user, {'is_active': 1})
    request.set('status', 1)
    await bot.send_message(chat_id=user.tg_id, text='Ваша заяка одобрена')
    msg = Message(**json.loads(request.msg))
    msg = Message.model_validate(msg).as_(bot)
    btn = {}
    text = 'Заявки:\n'
    uncofirmed_reg = get_unconfirmed_reg()
    for reg in uncofirmed_reg:
        text += f'{reg.id}. {reg.text}\n'
        btn[f'Принять {reg.id} {reg.owner.username}'] = f'confirm_reg:{reg.id}'
        btn[f'Отклонить {reg.id} {reg.owner.username}'] = f'reject_reg:{reg.id}'
    btn['Отмена'] = 'cancel'
    await callback.message.answer(text=text, reply_markup=custom_kb(2, btn))
    await state.clear()
    await msg.edit_text(text=msg.text + f'<b>\n\nОдобрено</b> {callback.from_user.username or callback.from_user.id}')


# Заявки на рабочие ссылки
@router.callback_query(F.data == 'req_work')
async def reg_list(callback: CallbackQuery, state: FSMContext, bot: Bot):
    uncofirmed_work_req = get_unconfirmed_work_req()
    btn = {}
    text = 'Заявки на рабочие ссылки:\n'
    for reg in uncofirmed_work_req:
        text += f'{reg.id}. {reg.owner.username or reg.owner.tg_id}\n'
        btn[f'Принять {reg.id} {reg.owner.username}'] = f'confirm_req_work:{reg.id}'
        btn[f'Отклонить {reg.id} {reg.owner.username}'] = f'reject_req_work:{reg.id}'
    btn['Отмена'] = 'cancel'
    await callback.message.edit_text(text=text, reply_markup=custom_kb(2, btn))


class FSMAdminWorkReg(StatesGroup):
    confirm = State()
    reject = State()


@router.callback_query(F.data.startswith('reject_req_work:'))
async def reject_reg(callback: CallbackQuery, state: FSMContext, bot: Bot):
    print(callback.data)
    await callback.message.delete()
    await state.set_state(FSMAdminWorkReg.reject)
    request_id = int(callback.data.split('reject_req_work:')[-1])
    await state.update_data(request_id=request_id)
    await callback.message.answer('Укажите причину:')


@router.message(StateFilter(FSMAdminWorkReg.reject))
async def operation_cost(message: Message, state: FSMContext, bot: Bot):
    reject_text = message.text.strip()
    data = await state.get_data()
    request_id = data['request_id']
    print(request_id)
    request = get_work_request_from_id(request_id)
    print(request)
    client = get_user_from_id(request.owner_id)
    print(client)
    request.set('status', -1)
    request.set('reject_text', reject_text)
    request = get_work_request_from_id(request_id)
    msg = Message(**json.loads(request.msg))
    msg = Message.model_validate(msg).as_(bot)
    await state.clear()
    await bot.send_message(chat_id=client.tg_id, text=f'Ваша заяка на выдачу рабочей ссылки отклонена:\n{reject_text}')
    await message.answer(text=f'Заявка отклонена\n{request.reject_text}', reply_markup=admin_start_kb)
    await state.clear()
    await msg.edit_text(text=msg.text + f'<b>\n\nОтклонено {message.from_user.username or message.from_user.id}\n{reject_text}</b>')


@router.callback_query(F.data.startswith('confirm_req_work:'))
async def work_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    logger.debug(callback.data)
    request_id = int(callback.data.split('confirm_req_work:')[-1])
    await callback.message.answer('Укажите рабочую ссылку')
    await state.set_state(FSMAdminWorkReg.confirm)
    await state.update_data(request_id=request_id, private_msg=callback.message)
    # user = request.owner
    # request.set('status', 1)
    # await bot.send_message(chat_id=user.tg_id, text='Ваша заяка на выдачу рабочей ссылки одобрена')
    # msg = Message(**json.loads(request.msg))
    # msg = Message.model_validate(msg).as_(bot)
    # uncofirmed_work_req = get_unconfirmed_work_req()
    # btn = {}
    # text = 'Заявки на рабочие ссылки:\n'
    # for reg in uncofirmed_work_req:
    #     text += f'{reg.id}. {reg.owner.username or reg.owner.tg_id}\n'
    #     btn[f'Принять {reg.id} {reg.owner.username}'] = f'confirm_req_work:{reg.id}'
    #     btn[f'Отклонить {reg.id} {reg.owner.username}'] = f'reject_req_work:{reg.id}'
    # btn['Отмена'] = 'cancel'
    # await callback.message.edit_text(text=text, reply_markup=custom_kb(2, btn))
    # await state.clear()
    # await msg.edit_text(text=msg.text + f'<b>\n\nОдобрено</b> {callback.from_user.username or callback.from_user.id}')


@router.message(StateFilter(FSMAdminWorkReg.confirm))
async def link_confirm_cost(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    request_id = data['request_id']
    worklink = message.text.strip()
    moderator = get_or_create_user(message.from_user)
    request = get_work_request_from_id(request_id)
    request.set('status', 1)
    request.set('moderator_id', moderator.id)
    request = get_work_request_from_id(request_id)
    msg = Message(**json.loads(request.msg))
    msg = Message.model_validate(msg).as_(bot)
    # Меняем сообщение вличке
    private_msg: Message = data['private_msg']
    await private_msg.delete()
    request = get_work_request_from_id(request_id)
    await message.answer(f'Заявка № {request.id} принята. {worklink}')
    create_work_link(user_id=request.owner_id, link=worklink, moderator_id=moderator.id)
    # Отправка клиенту
    client = get_user_from_id(request.owner_id)
    await bot.send_message(chat_id=client.tg_id,
                           text=f'Ваша Заявка № {request.id} принята:\n{worklink}')
    # Меняем сообщение в группе
    await bot.edit_message_text(text=msg.text + f'\nПринято {moderator.username or moderator.tg_id}\n{worklink}',
                                chat_id=conf.tg_bot.GROUP_ID, message_id=msg.message_id)
