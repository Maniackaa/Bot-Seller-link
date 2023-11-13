import asyncio
import datetime

from sqlalchemy import select, delete

from config_data.bot_conf import get_my_loggers
from database.db import Session, User, Request, Link, WorkLinkRequest, WorkLink

logger, err_log = get_my_loggers()


def check_user(id):
    """Возвращает найденных пользователей по tg_id"""
    # logger.debug(f'Ищем юзера {id}')
    with Session() as session:
        user: User = session.query(User).filter(User.tg_id == str(id)).one_or_none()
        # logger.debug(f'Результат: {user}')
        return user


# def get_user_from_id(pk) -> User:
#     """Возвращает найденного пользователя по id"""
#     # logger.debug(f'Ищем юзера {id}')
#     with Session() as session:
#         user: User = session.query(User).filter(User.id == pk).one_or_none()
#         # logger.debug(f'Результат: {user}')
#         return user


def get_user_from_id(pk) -> User:
    session = Session(expire_on_commit=False)
    with session:
        q = select(User).filter(User.id == pk)
        user = session.execute(q).scalars().one_or_none()
        return user


def get_or_create_user(user) -> User:
    """Из юзера ТГ возвращает сущестующего User ли создает его"""
    try:
        tg_id = user.id
        username = user.username
        logger.debug(f'username {username}')
        old_user = check_user(tg_id)
        if old_user:
            logger.debug('Пользователь есть в базе')
            return old_user
        logger.debug('Добавляем пользователя')
        with Session() as session:
            new_user = User(tg_id=tg_id,
                            username=username,
                            register_date=datetime.datetime.now()
                            )
            session.add(new_user)
            session.commit()
            logger.debug(f'Пользователь создан: {new_user}')
        return new_user
    except Exception as err:
        err_log.error('Пользователь не создан', exc_info=True)


def update_user(user: User, data: dict):
    try:
        logger.debug(f'Обновляем {user}: {data}')
        session = Session()
        with session:
            user: User = session.query(User).filter(User.id == user.id).first()
            for key, val in data.items():
                setattr(user, key, val)
            session.commit()
            logger.debug(f'Юзер обновлен {user}')
    except Exception as err:
        err_log.error(f'Ошибка обновления юзера {user}: {err}')


def create_request(user: User, text):
    logger.debug(f'Сохраняем запрос')
    session = Session()
    with session:
        request = Request(
            user_id=user.id,
            text=text
        )
        session.add(request)
        session.commit()
        logger.debug('Запрос сохранен')
        return request.id


def get_request_from_id(pk) -> Request:
    with Session() as session:
        req: Request = session.query(Request).filter(Request.id == pk).one_or_none()
        return req


def create_links(user: User, links: list):
    session = Session()
    with session:
        link_ids = []
        for link in links:
            link = Link(owner_id=user.id,
                        link=link)
            session.add(link)
            session.commit()
            link_ids.append(link.id)
        logger.debug('Запрос сохранен')
        return link_ids


def create_work_link_request(user: User):
    session = Session()
    with session:
        work = WorkLinkRequest(owner_id=user.id)
        session.add(work)
        session.commit()
        logger.debug('Запрос сохранен')
        return work.id


def create_work_link(user_id, link, moderator_id):
    session = Session()
    with session:
        work = WorkLink(worker_id=user_id,
                        link=link,
                        moderator_id=moderator_id)
        session.add(work)
        session.commit()
        logger.debug('Запрос сохранен')
        return work.id


def get_link_from_id(pk) -> Link:
    session = Session()
    with session:
        q = select(Link).filter(Link.id == pk)
        link = session.execute(q).scalars().one_or_none()
        return link


def get_reg_from_id(pk) -> Request:
    session = Session()
    with session:
        q = select(Request).filter(Request.id == pk)
        reg = session.execute(q).scalars().one_or_none()
        return reg


def get_work_request_from_id(pk) -> WorkLinkRequest:
    session = Session()
    with session:
        q = select(WorkLinkRequest).filter(WorkLinkRequest.id == pk)
        reg = session.execute(q).scalars().one_or_none()
        return reg

if __name__ == '__main__':
    pass
    client = get_user_from_id(1)
    # print(client)
    new_cash = client.cash + 100
    client = client.set('cash', new_cash)
    print(client)
    # r = get_request_from_id(1)
    # print(r)
    # r.set('reject_text', 'text')
    # asyncio.run(update_operation_in(['оступле333ние 1']))

