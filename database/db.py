import asyncio
import datetime
from typing import Sequence

from pydantic import json
from sqlalchemy import create_engine, ForeignKey, Date, String, DateTime, \
    Float, UniqueConstraint, Integer, LargeBinary, BLOB, select, ARRAY, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils.functions import database_exists, create_database

from config_data.bot_conf import conf, get_my_loggers, tz
from lexicon.lexicon import LEXICON

logger, err_log = get_my_loggers()

db_url = f"postgresql+psycopg2://{conf.db.db_user}:{conf.db.db_password}@{conf.db.db_host}:{conf.db.db_port}/{conf.db.database}"
engine = create_engine(db_url, echo=False)
Session = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    def set(self, key, value):
        _session = Session(expire_on_commit=False)
        with _session:
            setattr(self, key, value)
            _session.add(self)
            _session.commit()
            logger.debug(f'Изменено значение {key} на {value}')
            return self


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True,
                                    autoincrement=True)
    tg_id: Mapped[str] = mapped_column(String(30))
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    register_date: Mapped[datetime.datetime] = mapped_column(DateTime(), nullable=True)
    fio: Mapped[str] = mapped_column(String(200), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    cash: Mapped[int] = mapped_column(Integer(), default=0)
    tolerance: Mapped[list] = mapped_column(ARRAY(Integer), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer(), default=0)
    links: Mapped[list['Link']] = relationship(back_populates='owner', lazy='subquery')
    requests: Mapped[list['Request']] = relationship(back_populates='owner', lazy='subquery')
    work_link: Mapped[int] = mapped_column(ForeignKey('work_links.id', ondelete='CASCADE'), nullable=True)
    work_link_requests: Mapped[list['WorkLinkRequest']] = relationship(back_populates='owner', lazy='subquery')

    def __str__(self):
        return f'{self.id}. {self.username or "-"} ({self.fio}). Баланс {self.cash}'

    def __repr__(self):
        return f'{self.id}. {self.username or "-"} ({self.fio})'


class Request(Base):
    __tablename__ = 'requests'
    id: Mapped[int] = mapped_column(primary_key=True,
                                    autoincrement='auto')
    register_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True,
                                                default=lambda: datetime.datetime.now(tz=tz))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    owner: Mapped['User'] = relationship(back_populates='requests', lazy='subquery')
    text: Mapped[str] = mapped_column(String(4000), nullable=True)
    status: Mapped[int] = mapped_column(Integer(), default=0)
    reject_text: Mapped[str] = mapped_column(String(4000), nullable=True)
    msg: Mapped[json] = mapped_column(JSONB(), nullable=True)


class Link(Base):
    __tablename__ = 'links'
    id: Mapped[int] = mapped_column(primary_key=True,
                                    autoincrement='auto')
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    owner: Mapped['User'] = relationship(back_populates='links')
    register_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True,
                                                    default=lambda: datetime.datetime.now(tz=tz))
    link: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default='created')
    moderator_id: Mapped[int] = mapped_column(Integer(), nullable=True)
    cost: Mapped[int] = mapped_column(Integer(), default=0)
    msg: Mapped[json] = mapped_column(JSONB(), nullable=True)

    def __str__(self):
        return f'{self.id}. {self.link}'

    def __repr__(self):
        return f'{self.id}. {self.link}'


class WorkLink(Base):
    __tablename__ = 'work_links'
    id: Mapped[int] = mapped_column(primary_key=True,
                                    autoincrement='auto')
    register_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True,
                                                    default=lambda: datetime.datetime.now(tz=tz))
    link: Mapped[str] = mapped_column(String(1000))
    worker_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    moderator_id: Mapped[int] = mapped_column(Integer(), nullable=True)

    def __str__(self):
        return f'{self.id}. {self.link}'

    def __repr__(self):
        return f'{self.id}. {self.link}'


class WorkLinkRequest(Base):
    __tablename__ = 'work_link_requests'
    id: Mapped[int] = mapped_column(primary_key=True,
                                    autoincrement='auto')
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    owner: Mapped['User'] = relationship(back_populates='work_link_requests', lazy='subquery')
    register_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True,
                                                    default=lambda: datetime.datetime.now(tz=tz))

    status: Mapped[int] = mapped_column(Integer(), default=0)
    reject_text: Mapped[str] = mapped_column(String(4000), nullable=True)
    msg: Mapped[json] = mapped_column(JSONB(), nullable=True)

    def __str__(self):
        return f'{self.id}. {self.owner_id}'

    def __repr__(self):
        return f'{self.id}. {self.owner_id}'



if not database_exists(db_url):
    create_database(db_url)
Base.metadata.create_all(engine)
