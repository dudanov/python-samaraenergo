from __future__ import annotations

import datetime as dt
import logging
import re
from decimal import Decimal
from functools import partial
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    PlainSerializer,
    RootModel,
    field_validator,
    model_validator,
)

_LOGGER = logging.getLogger(__name__)

_NONE_DATETIME = "/Date(253402214400000)/"
_RE_DATE = re.compile(r"\/Date\((\d+)000\)\/")


def _datetime_validator(data: Any) -> Any:
    if isinstance(data, dt.date):
        return data

    if data == _NONE_DATETIME:
        return None

    if m := _RE_DATE.fullmatch(data):
        return m.group(1)

    raise ValueError("Должна быть строка вида '/Date(milliseconds)/'")


def _datetime_serializer(x: dt.date | None) -> str:
    if x is None:
        return _NONE_DATETIME

    if not isinstance(x, dt.datetime):
        x = dt.datetime(x.year, x.month, x.day, tzinfo=dt.UTC)

    elif x.tzinfo is None:
        raise ValueError("naive datetime is not supported")

    return f"/Date({x.timestamp():.0f}000)/"


type _Date[T: dt.date] = Annotated[
    T | None,
    BeforeValidator(_datetime_validator),
    PlainSerializer(_datetime_serializer, return_type=str),
]

type Date = _Date[dt.date]
type DateTime = _Date[dt.datetime]


def _deferrable_validator(data: Any, *, multiple: bool) -> Any:
    """Валидатор моделей с отложенной загрузкой"""

    if not isinstance(data, dict):
        return data

    # для отложенных объектов вернем пустой список или `None`
    if "__deferred" in data:
        return [] if multiple else None

    try:
        return data["results"] if multiple else data

    except KeyError:
        raise ValueError("ожидается ключ 'results'")


type Deferrable[T: BaseModel] = Annotated[
    T | None, BeforeValidator(partial(_deferrable_validator, multiple=False))
]
"""Модель с отложенной загрузкой"""


type DeferrableList[T: BaseModel] = Annotated[
    list[T], BeforeValidator(partial(_deferrable_validator, multiple=True))
]
"""Список моделей с отложенной загрузкой"""


class ResponseModel[T: BaseModel](RootModel[list[T]]):
    """Корневая модель ответа на запросы"""

    @model_validator(mode="before")
    @classmethod
    def before_validator(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("ожидается JSON объект")

        try:
            return data["d"]["results"]

        except KeyError:
            raise ValueError("ожидаются последовательные ключи: 'd' и 'results'")


class Account(BaseModel):
    """Аккаунт личного кабинета"""

    AccountID: str
    """Идентификатор"""
    FullName: str
    """ФИО пользователя личного кабинета"""
    StandardAccountAddress: Deferrable[AccountAddress]
    """Адрес"""
    ContractAccounts: DeferrableList[ContractAccount]
    """Аккаунты договоров"""
    PaymentDocuments: DeferrableList[PaymentDocument]
    """Документы об оплате"""


class AccountAddress(BaseModel):
    """"""

    AddressID: str
    AccountID: str
    AddressInfo: AddressInfo
    # AccountAddressDependentFaxes:
    # AccountAddressDependentMobilePhones
    # AccountAddressDependentPhones
    # AccountAddressDependentEmails
    # AccountAddressUsages


class PaymentDocument(BaseModel):
    """Документ оплаты"""

    PaymentDocumentID: str
    """Идентификатор"""
    ExecutionDate: Date
    """Дата оплаты"""
    Amount: Decimal
    """Сумма"""
    PaymentMethodDescription: str
    """Метод оплаты"""


class ContractAccount(BaseModel):
    """Аккаунт договора"""

    ContractAccountID: str
    """Идентификатор"""
    Preisbtr1: Decimal
    """Стоимость КВт*ч, день"""
    Preisbtr2: Decimal
    """Стоимость КВт*ч, ночь"""
    Preisbtr3: Decimal
    """Стоимость КВт*ч, полупик"""
    Ttypbez: str
    """Тип тарифа"""
    Vkona: str
    """Лицевой счет"""
    Regcnt: Decimal
    """Кол-во прописанных"""
    Livecnt: Decimal
    """Кол-во проживающих"""
    Homes: Decimal
    """Общая площадь, м2"""
    Roomcnt: int
    """Кол-во комнат"""
    Contracts: DeferrableList[Contract]
    """Договоры"""
    Invoices: DeferrableList[Invoice]
    """Счета на оплату"""


class ContractConsumptionValue(BaseModel):
    ContractID: str
    """Идентификатор"""
    StartDate: Date
    """Начало расчетного периода"""
    EndDate: Date
    """Конец расчетного периода"""
    BilledAmount: Decimal
    """Сумма"""
    ConsumptionValue: Decimal
    """Энергия"""


class MeterReadingResult(BaseModel):
    DependentMeterReadingResults: DeferrableList[MeterReadingResult]
    ReadingDateTime: DateTime
    DeviceID: str
    MeterReadingNoteID: str
    RegisterID: str
    ReadingResult: Decimal


class MeterReadingResult2(BaseModel):
    """Показание прибора"""

    MeterReadingResultID: str
    """Идентификатор"""
    RegisterID: str
    """ID регистра хранения счетчика (`001` - день, `002` - ночь, `003` - полупик)"""
    ReadingResult: Decimal
    """Показание"""
    ReadingDateTime: DateTime
    """Дата и время предоставления данных"""
    Zwarttxt: str
    """Зона"""
    Text40: str
    """Источник показаний"""
    Prkrasch: bool
    """Принято к расчету"""

    @field_validator("Prkrasch", mode="before")
    def is_empty(cls, value: str) -> bool:
        return bool(value)


class Contract(BaseModel):
    """Договор"""

    ContractID: str
    """Идентификатор"""
    MoveInDate: Date
    """Дата заключения"""
    MoveOutDate: Date
    """Дата расторжения"""
    Devices: DeferrableList[Device]
    """Приборы учета"""
    ContractConsumptionValues: DeferrableList[ContractConsumptionValue]


class Device(BaseModel):
    """Прибор учета"""

    DeviceID: str
    """Идентификатор"""
    SerialNumber: str
    """Серийный номер"""
    Vbsarttext: str
    """Тип дома"""
    Text30: str
    """"""
    Einbdat1: str
    """"""
    Uitext: str
    """"""
    GridName: str
    """Наименование сетевой организации"""
    Bgljahr: str
    """Год предыдущей поверки"""
    Bauform: str
    """Тип прибора учета"""
    Vlzeitt: str
    """Межповерочный интервал"""
    Stanzvor: str
    """Знаки до запятой"""
    Stanznac: str
    """Знаки после запятой"""
    Zwfakt: Decimal
    """"""
    Baukltxt: str
    """"""
    LvProv: str
    """Год очередной поверки"""
    Plomba: str
    """Наличие пломбы"""
    LineAdr: str
    """Место установки"""
    DevlocPltxt: str
    """Объект электроснабжения"""
    RegistersToRead: DeferrableList[RegisterToRead]
    """Регистры показаний для чтения"""
    MeterReadingResults: DeferrableList[MeterReadingResult]
    """Показания"""


class RegisterToRead(BaseModel):
    """Регистр для чтения"""

    RegisterID: str
    """Идентификатор"""
    PreviousMeterReadingResult: Decimal
    """Последние показания"""
    PreviousMeterReadingDate: Date
    """Дата и время внесения последних показаний"""
    ReasonText: str
    """"""
    Zwarttxt: str
    """Зона"""


class Premise(BaseModel):
    """Помещение установки прибора учета"""

    PremiseID: str
    """ID"""
    PremiseTypeID: str
    """"""
    AddressInfo: AddressInfo
    """"""


class AddressInfo(BaseModel):
    """Адрес"""

    PostalCode: str
    """Индекс"""
    CountryName: str
    """Страна"""
    RegionName: str
    """Регион"""
    City: str
    """Город"""
    Street: str
    """Улица"""
    HouseNo: str
    """Дом"""
    RoomNo: str
    """Квартира"""


class Invoice(BaseModel):
    """Счет на оплату"""

    InvoiceID: str
    """Идентификатор"""
    InvoiceDate: Date
    """Дата выставления"""
    DueDate: Date
    """Крайняя дата оплаты"""
    AmountDue: Decimal
    """Сумма к оплате"""
    AmountPaid: Decimal
    """Оплаченная сумма"""
    AmountRemaining: Decimal
    """Оставшаяся сумма"""
    InvoiceStatusID: str
