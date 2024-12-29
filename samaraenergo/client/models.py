from __future__ import annotations

import datetime as dt
import logging
import re
from decimal import Decimal
from functools import partial
from typing import Annotated, Any, Final

from pydantic import (
    BaseModel,
    BeforeValidator,
    PlainSerializer,
    RootModel,
    field_validator,
    model_validator,
)

_LOGGER: Final = logging.getLogger(__name__)

_NONE_DATETIME: Final = "/Date(253402214400000)/"
_RE_DATE: Final = re.compile(r"\/Date\((\d+)000\)\/")


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
    ContractAccounts: DeferrableList[ContractAccount]
    """Аккаунты договоров"""
    FullName: str
    """ФИО пользователя личного кабинета"""
    PaymentDocuments: DeferrableList[PaymentDocument]
    """Документы об оплате"""
    StandardAccountAddress: Deferrable[AccountAddress]
    """Адрес"""


class AccountAddress(BaseModel):
    """"""

    AccountID: str
    AddressID: str
    AddressInfo: AddressInfo
    # AccountAddressDependentEmails
    # AccountAddressDependentFaxes:
    # AccountAddressDependentMobilePhones
    # AccountAddressDependentPhones
    # AccountAddressUsages


class PaymentDocument(BaseModel):
    """Документ оплаты"""

    Amount: Decimal
    """Сумма"""
    ExecutionDate: Date
    """Дата оплаты"""
    PaymentDocumentID: str
    """Идентификатор"""
    PaymentMethodDescription: str
    """Метод оплаты"""


class ContractAccount(BaseModel):
    """Аккаунт договора"""

    ContractAccountID: str
    """Идентификатор"""
    Contracts: DeferrableList[Contract]
    """Договоры"""
    Homes: Decimal
    """Общая площадь, м2"""
    Invoices: DeferrableList[Invoice]
    """Счета на оплату"""
    Livecnt: Decimal
    """Кол-во проживающих"""
    Preisbtr1: Decimal
    """Стоимость КВт*ч, день"""
    Preisbtr2: Decimal
    """Стоимость КВт*ч, ночь"""
    Preisbtr3: Decimal
    """Стоимость КВт*ч, полупик"""
    Regcnt: Decimal
    """Кол-во прописанных"""
    Roomcnt: int
    """Кол-во комнат"""
    Ttypbez: str
    """Тип тарифа"""
    Vkona: str
    """Лицевой счет"""


class ContractConsumptionValue(BaseModel):
    BilledAmount: Decimal
    """Сумма"""
    ConsumptionValue: Decimal
    """Энергия"""
    ContractID: str
    """Идентификатор"""
    EndDate: Date
    """Конец расчетного периода"""
    StartDate: Date
    """Начало расчетного периода"""


class MeterReadingResult(BaseModel):
    """
    Объект передачи данных о потреблении энергии.
    Путь POST запроса: 'MeterReadingResults'
    """

    DependentMeterReadingResults: DeferrableList[MeterReadingResult]
    """Связанные показания"""
    DeviceID: str
    """Идентификатор прибора учета"""
    MeterReadingNoteID: str
    """Источник передачи. 920: мобильный личный кабинет, 01: оценка результата считывания"""
    ReadingDateTime: DateTime
    """Дата и время чтения показания"""
    ReadingResult: Decimal
    """Показание"""
    RegisterID: str
    """Идентификатор регистра прибора учета"""


class MeterReadingResult2(BaseModel):
    """Показание прибора"""

    MeterReadingResultID: str
    """Идентификатор"""
    Prkrasch: bool
    """Принято к расчету"""
    ReadingDateTime: DateTime
    """Дата и время предоставления данных"""
    ReadingResult: Decimal
    """Показание"""
    RegisterID: str
    """ID регистра хранения счетчика (`001` - день, `002` - ночь, `003` - полупик)"""
    Text40: str
    """Источник показаний"""
    Zwarttxt: str
    """Зона"""

    @field_validator("Prkrasch", mode="before")
    def is_empty(cls, value: str) -> bool:
        return bool(value)


class Contract(BaseModel):
    """Договор"""

    ContractConsumptionValues: DeferrableList[ContractConsumptionValue]
    """"""
    ContractID: str
    """Идентификатор"""
    Devices: DeferrableList[Device]
    """Приборы учета"""
    MoveInDate: Date
    """Дата заключения"""
    MoveOutDate: Date
    """Дата расторжения"""


class Device(BaseModel):
    """Прибор учета"""

    DeviceID: str
    """Идентификатор прибора учета"""
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

    AddressInfo: AddressInfo
    """"""
    PremiseID: str
    """ID"""
    PremiseTypeID: str
    """"""


class AddressInfo(BaseModel):
    """Адрес"""

    City: str
    """Город"""
    CountryName: str
    """Страна"""
    HouseNo: str
    """Дом"""
    PostalCode: str
    """Индекс"""
    RegionName: str
    """Регион"""
    RoomNo: str
    """Квартира"""
    Street: str
    """Улица"""


class Invoice(BaseModel):
    """Счет на оплату"""

    AmountDue: Decimal
    """Сумма к оплате"""
    AmountPaid: Decimal
    """Оплаченная сумма"""
    AmountRemaining: Decimal
    """Оставшаяся сумма"""
    DueDate: Date
    """Крайняя дата оплаты"""
    InvoiceDate: Date
    """Дата выставления"""
    InvoiceID: str
    """Идентификатор"""
    InvoiceStatusID: str
    """Идентификатор статуса"""
