from aiogram.types import KeyboardButton, ReplyKeyboardMarkup,\
    InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def custom_kb(width: int, buttons_dict: dict) -> InlineKeyboardMarkup:
    kb_builder: InlineKeyboardBuilder = InlineKeyboardBuilder()
    buttons = []
    for key, val in buttons_dict.items():
        callback_button = InlineKeyboardButton(
            text=key,
            callback_data=val)
        buttons.append(callback_button)
    kb_builder.row(*buttons, width=width)
    return kb_builder.as_markup()


start_kb_b = {
    '💰Отправить ссылку': 'send_link',
    '💼 Аккаунт': 'my_account',
    '🛠 Инструкция по работе': 'instructions',
    '🔗 Получить ссылку': 'give_link',
    '🆘 Обратиться в саппорт': 'support',
    # 'Купить аккаунт': 'buy_account',
    # 'Продать аккаунт': 'sell_account',
}
start_kb = custom_kb(1, start_kb_b)

kb_builder: ReplyKeyboardBuilder = ReplyKeyboardBuilder()
kb_list = [val for val in start_kb_b.keys()]
buttons: list[KeyboardButton] = [KeyboardButton(text=key) for key in kb_list]
kb_builder.row(*buttons, width=2)
menu_kb = kb_builder.as_markup(resize_keyboard=True)


admin_start_kb_b = {
    'Заявки на регистрацию': 'reg_list',
    'Заявки на проверку видео и зачисления баланса за них': 'link_list',
    # 'Заявки на покупку youtube акканута': 'buy_account_list',
    # 'Заявки на продажу аккаунта': 'sell_account_list',
    'Заявки на получение ссылки': 'req_work',
}
admin_start_kb = custom_kb(1, admin_start_kb_b)

contact_kb_buttons = [
    [KeyboardButton(
        text="Отправить номер телефона",
        request_contact=True
    )],
    ]

contact_kb: ReplyKeyboardMarkup = ReplyKeyboardMarkup(
    keyboard=contact_kb_buttons,
    resize_keyboard=True)


