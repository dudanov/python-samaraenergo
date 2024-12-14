from __future__ import annotations

import asyncio
import dataclasses as dc
import datetime as dt
import logging
from collections.abc import Iterator
from enum import STRICT, StrEnum
from typing import Literal, override

import aiohttp

_LOGGER = logging.getLogger(__name__)

URL = "https://www.samaraenergo.ru/fiz-licam/online-kalkulyator/"


class ApiError(Exception):
    pass


class Position(StrEnum, boundary=STRICT):
    """Тип местности"""

    CITY = "1"
    """Городское население в домах"""
    COUNTRY = "2"
    """Сельское население"""


class HeatingType(StrEnum, boundary=STRICT):
    """Тип помещения"""

    ELECTRIC = "3"
    """Оборудованное электроотопительными установками"""
    CENTRAL = "4"
    """Не оборудованное электроотопительными установками"""


class StoveType(StrEnum, boundary=STRICT):
    """Тип плиты"""

    GAS = "5"
    """Газовая"""
    ELECTRIC = "6"
    """Электрическая"""


class Tariff(StrEnum, boundary=STRICT):
    """Тариф"""

    ONE = "7"
    """Однотарифный"""
    TWO = "8"
    """Двухтарифный"""
    THREE = "9"
    """Трехтарифный"""

    @property
    def n_args(self):
        return int(self.value) - 6


@dc.dataclass(frozen=True)
class CalculatorConfig:
    pass

    @property
    def asstring(self) -> str:
        return "".join(dc.astuple(self))

    @property
    def name(self) -> str: ...

    @staticmethod
    def from_string(cfg: str) -> CityConfig | CountryConfig:
        position, tariff = Position(cfg[0]), Tariff(cfg[1])

        if position is Position.COUNTRY:
            return CountryConfig(position, tariff)

        return CityConfig(position, tariff, HeatingType(cfg[2]), StoveType(cfg[3]))


@dc.dataclass(frozen=True)
class CityConfig(CalculatorConfig):
    position: Literal[Position.CITY]
    tariff: Tariff
    heating: HeatingType
    stove: StoveType

    @property
    @override
    def name(self):
        x1 = "Ц" if self.heating is HeatingType.CENTRAL else "Э"
        x2 = "Г" if self.stove is StoveType.GAS else "Э"

        return f"Г{self.tariff.n_args}/{x1}О/{x2}П"


@dc.dataclass(frozen=True)
class CountryConfig(CalculatorConfig):
    position: Literal[Position.COUNTRY]
    tariff: Tariff

    @property
    @override
    def name(self):
        return f"С{self.tariff.n_args}"


class OnlineCalculator:
    def __init__(
        self,
        config: CityConfig | CountryConfig,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._config = config
        self._session = session or aiohttp.ClientSession()
        self._close_connector = not session

    @classmethod
    def from_string(
        cls,
        config_str: str,
        *,
        session: aiohttp.ClientSession | None = None,
    ):
        return cls(
            CalculatorConfig.from_string(config_str),
            session=session,
        )

    @property
    def config(self) -> CalculatorConfig:
        return self._config

    def _gen_args(self) -> Iterator[list[int]]:
        n = self._config.tariff.n_args

        for idx in range(n):
            lst = [0] * n
            lst[idx] = 1
            yield lst

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_t, exc_v, exc_tb):
        await self.close()

    async def close(self):
        if self._close_connector:
            await self._session.close()

    async def request(
        self,
        *values: float,
        date: dt.date | None = None,
    ) -> float:
        """
        Функция запроса к онлайн-калькулятору.

        Возвращает стоимость энергии.

        Параметры:
        - `*values`: значения потребления в соответствие с выбранным тарифом.
        - `date`: дата расчетного периода.
        """

        if not (1 <= (n := len(values)) <= 3):
            raise ValueError("Должно быть 1, 2 или 3 значения.")

        if any(x < 0 for x in values):
            raise ValueError("Значения не должны быть отрицательными.")

        if n != self._config.tariff.n_args:
            raise ValueError("Количество переданных значений не соответствует тарифу.")

        if not any(values):
            return 0

        data = {
            "action": "calculate",
            "UF_DATE": (date or dt.date.today()).strftime("%d.%m.%Y"),
            "UF_POSITION": self._config.position,
            "UF_TARIF": self._config.tariff,
            "START_PIK": 0,
            "END_PIK": values[0],
        }

        if self._config.position is Position.CITY:
            data["UF_TYPE_HOUSE"] = self._config.heating
            data["UF_TYPE_STOVE"] = self._config.stove

        if self._config.tariff is not Tariff.ONE:
            data["START_NOCH"] = 0
            data["END_NOCH"] = values[-1]

        if self._config.tariff is Tariff.THREE:
            data["START_POLUPIK"] = 0
            data["END_POLUPIK"] = values[1]

        _LOGGER.debug("POST request data: %s", data)

        async with self._session.post(URL, data=data) as x:
            json = await x.json(content_type="text/html")

        if json["Status"]:
            return float(json["Value"].replace(",", "."))

        raise ApiError("Request error")

    async def get_cost(
        self,
        *,
        date: dt.date | None = None,
    ) -> list[float]:
        """Запрос стоимости тарифа"""

        return await asyncio.gather(
            *(self.request(*x, date=date or dt.date.today()) for x in self._gen_args())
        )
