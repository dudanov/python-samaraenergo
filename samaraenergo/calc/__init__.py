from __future__ import annotations

import asyncio
import dataclasses as dc
import datetime as dt
import logging
from enum import STRICT, StrEnum
from typing import AsyncIterator, Awaitable, Iterator, Literal, Sequence, override

import aiohttp

_LOGGER = logging.getLogger(__name__)

type ZoneCost = tuple[dt.datetime, float]
type ZoneCostList = list[ZoneCost]

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
    def zones(self):
        """Количество зон тарифа"""
        return int(self.value) - 6


@dc.dataclass(frozen=True)
class CalculatorConfig:
    @property
    def asstring(self) -> str:
        return "".join(dc.astuple(self))

    @property
    def code(self) -> str: ...

    @staticmethod
    def from_string(config: str) -> CityConfig | CountryConfig:
        assert len(config) in [2, 4]
        position, tariff = Position(config[0]), Tariff(config[1])

        if position is Position.COUNTRY:
            assert len(config) == 2
            return CountryConfig(tariff)

        assert len(config) == 4
        return CityConfig(tariff, HeatingType(config[2]), StoveType(config[3]))


@dc.dataclass(frozen=True)
class CityConfig(CalculatorConfig):
    position: Literal[Position.CITY] = dc.field(default=Position.CITY, init=False)
    tariff: Tariff
    heating: HeatingType
    stove: StoveType

    @property
    @override
    def code(self):
        x1 = "Ц" if self.heating is HeatingType.CENTRAL else "Э"
        x2 = "Г" if self.stove is StoveType.GAS else "Э"

        return f"Г{self.tariff.zones}-{x1}О-{x2}П"


@dc.dataclass(frozen=True)
class CountryConfig(CalculatorConfig):
    position: Literal[Position.COUNTRY] = dc.field(default=Position.COUNTRY, init=False)
    tariff: Tariff

    @property
    @override
    def code(self):
        return f"С{self.tariff.zones}"


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
        config: str,
        *,
        session: aiohttp.ClientSession | None = None,
    ):
        return cls(
            CalculatorConfig.from_string(config),
            session=session,
        )

    @property
    def config(self) -> CityConfig | CountryConfig:
        """Текущая конфигурация"""
        return self._config

    @property
    def zones(self) -> int:
        """Количество зон текущего тарифа"""
        return self._config.tariff.zones

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

        Возвращает стоимость потребленной энергии.

        Параметры:
        - `*values`: потребление по зонам в соответствии с текущим тарифом.
        - `date`: дата расчетного периода. Если `None` - текущая дата.
        """

        if len(values) != self._config.tariff.zones:
            raise ValueError(
                "Количество значений потребления зон не соответствует текущему тарифу."
            )

        if any(x < 0 for x in values):
            raise ValueError("Значения не могут быть отрицательными.")

        if not any(values):
            return 0

        date = dt.date(date.year, date.month, date.day) if date else dt.date.today()

        if date < dt.date(2022, 1, 1):
            raise ValueError("Не поддерживаются даты ранее 1 января 2022 года.")

        data = {
            "action": "calculate",
            "UF_DATE": date.strftime("%d.%m.%Y"),
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

        _LOGGER.debug("Данные POST запроса: %s", data)

        async with self._session.post(URL, data=data) as x:
            json = await x.json(content_type="text/html")

        if json["Status"]:
            return float(json["Value"].replace(",", "."))

        raise ApiError("Ошибка запроса")

    def _cost_args(self) -> Iterator[list[int]]:
        zones = self.zones

        for idx in range(zones):
            lst = [0] * zones
            lst[idx] = 1

            yield lst

    def get_zones_cost(
        self,
        *,
        date: dt.date | None = None,
    ) -> Awaitable[list[float]]:
        """
        Запрос стоимости зон тарифа.

        Параметры:
        - `date`: дата расчетного периода. Если `None` - текущая дата.
        """

        date = date or dt.date.today()

        return asyncio.gather(*(self.request(*x, date=date) for x in self._cost_args()))

    async def _iter_costs(
        self, dates: Sequence[dt.datetime]
    ) -> AsyncIterator[ZoneCostList]:
        """Асинхронный генератор изменений стоимостей зон"""

        for args in self._cost_args():
            jobs = (self.request(*args, date=date) for date in dates)
            values = await asyncio.gather(*jobs)

            assert all(values)

            # Фильтр изменений стоимости
            result: ZoneCostList = []
            last_value = 0

            for date, value in zip(dates, values):
                if value != last_value:
                    result.append((date, (last_value := value)))

            yield result

    async def get_last_months_costs(
        self,
        months_or_start: int | dt.datetime,
        *,
        tzinfo: dt.tzinfo | None = None,
    ) -> list[ZoneCostList]:
        """
        Запрашивает изменения стоимостей зон тарифа за последние `months` месяцев.

        Параметры:
        - `months_or_start`: глубина истории изменения стоимости в количестве месяцев или стартовая дата.
        - `tzinfo`: часовой пояс. Если `None` - часовой пояс UTC.
        """

        dates: list[dt.datetime] = []
        now = dt.datetime.now(tzinfo)
        now = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if isinstance(months_or_start, int):
            assert months_or_start > 0

            y, m = divmod(months_or_start - 1, 12)
            y, m = now.year - y, now.month - m

            if m <= 0:
                y, m = y - 1, m + 12

            start = now.replace(y, m, 1)

        else:
            start = months_or_start.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )

        while start <= now:
            dates.append(start)
            year, month = start.year, start.month + 1

            if month > 12:
                year, month = year + 1, 1

            start = start.replace(year, month)

        return [x async for x in self._iter_costs(dates)]
