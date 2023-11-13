from typing import Sequence

from sqlalchemy import select, func

from database.db import User, Session, Link, Request, WorkLinkRequest, WorkLink
from services.db_func import get_user_from_id


def get_all_time_cash(owner: User):
    """Подсчет суммы стоимости всех ссылок"""
    session = Session()
    with session:
        q = select(func.sum(Link.cost)).where(Link.owner_id == owner.id)
        cash = session.execute(q).scalar()
        return cash or 0


def get_all_worked_link(owner: User) -> Sequence[WorkLink]:
    """Подсчет ссылок"""
    session = Session()
    with session:
        q = select(WorkLink).where(WorkLink.worker_id == owner.id)
        links = session.execute(q).scalars().all()
        return links

# user = get_user_from_id(1)
# print(user)
# print(get_all_link_count(user))


def get_users_with_uncofirmed_link(limit=10) -> Sequence[User]:
    """
    Возвращает пользователей у которых есть ссылки со статусом 'moderate'
    :return:
    """
    session = Session()
    with session:
        q = select(User).where(User.links.any(status='moderate')).limit(limit)
        users = session.execute(q).scalars().all()
        return users


def get_user_uncofirmed_link(user_id: int) -> Sequence[User]:
    """
    Возвращает ссылки юзера со статусом 'moderate'
    :return:
    """
    session = Session()
    with session:
        q = select(User).where(User.id == user_id).where(User.links.any(status='moderate'))
        links = session.execute(q).scalars().all()
        return links


def get_unconfirmed_reg(limit=5) -> Sequence[Request]:
    session = Session()
    with session:
        q = select(Request).where(Request.status == 0).limit(limit)
        regs = session.execute(q).scalars().all()
        return regs


def get_unconfirmed_work_req(limit=5) -> Sequence[WorkLinkRequest]:
    session = Session()
    with session:
        q = select(WorkLinkRequest).where(WorkLinkRequest.status == 0).limit(limit)
        regs = session.execute(q).scalars().all()
        return regs