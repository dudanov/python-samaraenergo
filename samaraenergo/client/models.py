from __future__ import annotations

import datetime as dt
import logging
import re
from functools import partial
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    RootModel,
    field_validator,
    model_validator,
)

_LOGGER = logging.getLogger(__name__)

_RE_DATE = re.compile(r"\/Date\((\d+)000\)\/")
_NONE_TIMESTAMP = "253402214400"


def _datetime_validator(_str: str) -> str | None:
    if (m := _RE_DATE.fullmatch(_str)) and (m := m.group(1)):
        return m if m != _NONE_TIMESTAMP else None

    raise ValueError("Должна быть строка вида '/Date(milliseconds)/'")


Date = Annotated[dt.date | None, BeforeValidator(_datetime_validator)]
DateTime = Annotated[dt.datetime | None, BeforeValidator(_datetime_validator)]


def _deferrable_validator(data: Any, *, multiple: bool) -> Any:
    """Валидатор моделей с отложенной загрузкой"""

    if not isinstance(data, dict):
        raise ValueError("ожидается JSON объект")

    # для отложенных объектов вернем пустой список
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

    id: str = Field(alias="AccountID")
    """Идентификатор"""
    name: str = Field(alias="FullName")
    """ФИО пользователя личного кабинета"""
    address: Deferrable[AccountAddress] = Field(alias="StandardAccountAddress")
    """Адрес"""
    accounts: DeferrableList[ContractAccount] = Field(alias="ContractAccounts")
    """Аккаунты договоров"""
    payments: DeferrableList[PaymentDocument] = Field(alias="PaymentDocuments")
    """Документы об оплате"""


class AccountAddress(BaseModel):
    """"""

    address_id: str = Field(alias="AddressID")
    account_id: str = Field(alias="AccountID")
    info: AddressInfo = Field(alias="AddressInfo")
    # AccountAddressDependentFaxes:
    # AccountAddressDependentMobilePhones
    # AccountAddressDependentPhones
    # AccountAddressDependentEmails
    # AccountAddressUsages


class PaymentDocument(BaseModel):
    """Документ оплаты"""

    id: str = Field(alias="PaymentDocumentID")
    """Идентификатор"""
    date: Date = Field(alias="ExecutionDate")
    """Дата оплаты"""
    amount: float = Field(alias="Amount")
    """Сумма"""
    method: str = Field(alias="PaymentMethodDescription")
    """Метод оплаты"""


class ContractAccount(BaseModel):
    """Аккаунт договора"""

    id: str = Field(alias="ContractAccountID")
    """Идентификатор"""
    cost_1: float = Field(alias="Preisbtr1")
    """Стоимость КВт*ч, день"""
    cost_2: float = Field(alias="Preisbtr2")
    """Стоимость КВт*ч, ночь"""
    cost_3: float = Field(alias="Preisbtr3")
    """Стоимость КВт*ч, полупик"""
    cost_type: str = Field(alias="Ttypbez")
    """Тип тарифа"""
    pnum: str = Field(alias="Vkona")
    """Лицевой счет"""
    registered: int = Field(alias="Regcnt")
    """Кол-во прописанных"""
    lived: int = Field(alias="Livecnt")
    """Кол-во проживающих"""
    Homes: float = Field(alias="Homes")
    """Общая площадь, м2"""
    rooms: int = Field(alias="Roomcnt")
    """Кол-во комнат"""
    contracts: DeferrableList[Contract] = Field(alias="Contracts")
    """Договоры"""
    invoices: DeferrableList[Invoice] = Field(alias="Invoices")
    """Счета на оплату"""
    # address: AccountAddress


class Contract(BaseModel):
    """Договор"""

    id: str = Field(alias="ContractID")
    """Идентификатор"""
    start_date: Date = Field(alias="MoveInDate")
    """Дата заключения"""
    end_date: Date = Field(alias="MoveOutDate")
    """Дата расторжения"""
    devices: DeferrableList[Device] = Field(alias="Devices")
    """Приборы учета"""


class Device(BaseModel):
    """Прибор учета"""

    id: str = Field(alias="DeviceID")
    """Идентификатор"""
    serial: str = Field(alias="SerialNumber")
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
    Zwfakt: float
    """"""
    Baukltxt: str
    """"""
    LvProv: str
    """Год очередной поверки"""
    Plomba: str
    """Наличие пломбы"""
    address: str = Field(alias="LineAdr")
    """Место установки"""
    DevlocPltxt: str
    """Объект электроснабжения"""
    registers: DeferrableList[RegisterToRead] = Field(alias="RegistersToRead")
    """Регистры показаний для чтения"""
    values: DeferrableList[MeterReadingResult] = Field(alias="MeterReadingResults")
    """Показания"""


class RegisterToRead(BaseModel):
    """Регистр для чтения"""

    id: str = Field(alias="RegisterID")
    """Идентификатор"""
    last_value: float = Field(alias="PreviousMeterReadingResult")
    """Последние показания"""
    last_date: Date = Field(alias="PreviousMeterReadingDate")
    """Дата и время внесения последних показаний"""
    reason: str = Field(alias="ReasonText")
    """"""
    zone: str = Field(alias="Zwarttxt")
    """Зона"""


class MeterReadingResult(BaseModel):
    """Показание прибора"""

    id: str = Field(alias="MeterReadingResultID")
    """Идентификатор"""
    register_id: str = Field(alias="RegisterID")
    """ID регистра хранения счетчика (`1` - день, `2` - ночь, `3` - полупик)"""
    value: float = Field(alias="ReadingResult")
    """Показание"""
    date: DateTime = Field(alias="ReadingDateTime")
    """Дата и время предоставления данных"""
    zone: str = Field(alias="Zwarttxt")
    """Зона"""
    source: str = Field(alias="Text40")
    """Источник показаний"""
    accepted: bool = Field(alias="Prkrasch")
    """Принято к расчету"""

    @field_validator("accepted", mode="before")
    def is_empty(cls, value: str) -> bool:
        return bool(value)


class Premise(BaseModel):
    """Помещение установки прибора учета"""

    id: str = Field(alias="PremiseID")
    """ID"""
    PremiseTypeID: str
    """"""
    AddressInfo: AddressInfo
    """"""


class AddressInfo(BaseModel):
    """Адрес"""

    postal_code: str = Field(alias="PostalCode")
    """Индекс"""
    country: str = Field(alias="CountryName")
    """Страна"""
    region: str = Field(alias="RegionName")
    """Регион"""
    city: str = Field(alias="City")
    """Город"""
    street: str = Field(alias="Street")
    """Улица"""
    house: str = Field(alias="HouseNo")
    """Дом"""
    room: str = Field(alias="RoomNo")
    """Квартира"""


class Invoice(BaseModel):
    """Счет на оплату"""

    id: str = Field(alias="InvoiceID")
    """Идентификатор"""
    date: Date = Field(alias="InvoiceDate")
    """Дата выставления"""
    due_date: Date = Field(alias="DueDate")
    """Крайняя дата оплаты"""
    due: float = Field(alias="AmountDue")
    """Сумма к оплате"""
    paid: float = Field(alias="AmountPaid")
    """Оплаченная сумма"""
    remaining: float = Field(alias="AmountRemaining")
    """Оставшаяся сумма"""
    status: int = Field(alias="InvoiceStatusID")
