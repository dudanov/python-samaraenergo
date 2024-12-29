from __future__ import annotations

import datetime as dt
import logging
import re
from decimal import Decimal
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


class _BaseModel(BaseModel):
    """Базовая модель шаблонной типизации"""


def _datetime_validator(data: Any) -> Any:
    if isinstance(data, dt.date):
        return data

    if data == _NONE_DATETIME:
        return None

    if m := _RE_DATE.fullmatch(data):
        return m.group(1)

    raise ValueError("must be string like '/Date(milliseconds)/'")


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


def _deferrable_validator(data: Any) -> Any:
    """Валидатор полей с отложенной загрузкой"""

    if not isinstance(data, dict):
        return data

    if "__deferred" in data:
        return

    return data.get("results", data)


type _Deferrable[T] = Annotated[T | None, BeforeValidator(_deferrable_validator)]
"""Базовый шаблонный тип поля с отложенной загрузкой"""

type Deferrable[T: _BaseModel] = _Deferrable[T]
"""Шаблонный тип поля модели с отложенной загрузкой"""

type DeferrableList[T: _BaseModel] = _Deferrable[list[T]]
"""Шаблонный тип поля списка моделей с отложенной загрузкой"""


class _ResponseModel[T](RootModel[T]):
    """Базовая корневая модель ответа на запрос"""

    @model_validator(mode="before")
    @classmethod
    def before_validator(cls, data: Any) -> Any:
        data = data["d"]
        return data.get("results", data)


class ResponseModel[T: _BaseModel](_ResponseModel[T]):
    """Модель ответа из одной корневой модели"""


class ResponseListModel[T: _BaseModel](_ResponseModel[list[T]]):
    """Модель ответа из корневого списка моделей"""


class Account(_BaseModel):
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


class AccountAddress(_BaseModel):
    """"""

    AccountID: str
    AddressID: str
    AddressInfo: AddressInfo
    # AccountAddressDependentEmails
    # AccountAddressDependentFaxes:
    # AccountAddressDependentMobilePhones
    # AccountAddressDependentPhones
    # AccountAddressUsages


class PaymentDocument(_BaseModel):
    """Документ оплаты"""

    Amount: Decimal
    """Сумма"""
    ExecutionDate: Date
    """Дата оплаты"""
    PaymentDocumentID: str
    """Идентификатор"""
    PaymentMethodDescription: str
    """Метод оплаты"""


class ContractAccount(_BaseModel):
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


class ContractConsumptionValue(_BaseModel):
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


class MeterReadingResult(_BaseModel):
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
    """ID регистра хранения счетчика (`001` - день, `002` - ночь, `003` - полупик)"""


class MeterReadingResult2(MeterReadingResult):
    """Показание прибора"""

    MeterReadingResultID: str
    """Идентификатор"""
    Prkrasch: bool
    """Принято к расчету"""
    Text40: str
    """Источник показаний"""
    Zwarttxt: str
    """Зона"""

    @field_validator("Prkrasch", mode="before")
    def is_empty(cls, value: str) -> bool:
        return bool(value)


class Contract(_BaseModel):
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


class Device(_BaseModel):
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
    MeterReadingResults: DeferrableList[MeterReadingResult2]
    """Показания"""


class RegisterToRead(_BaseModel):
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


class Premise(_BaseModel):
    """Помещение установки прибора учета"""

    AddressInfo: AddressInfo
    """"""
    PremiseID: str
    """ID"""
    PremiseTypeID: str
    """"""


class AddressInfo(_BaseModel):
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


class Invoice(_BaseModel):
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
