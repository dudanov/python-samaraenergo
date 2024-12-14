import asyncio
import dataclasses as dc
import datetime as dt
import logging
from collections.abc import Iterator
from enum import STRICT, StrEnum
from types import UnionType
from typing import Any, cast, get_args

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


@dc.dataclass(frozen=True, kw_only=True)
class CalculatorConfig:
    position: Position
    tariff: Tariff
    heating: HeatingType | None = None
    stove: StoveType | None = None

    @property
    def short(self):
        """Короткая запись конфигурации"""

        if self.position is Position.COUNTRY:
            return f"С{self.tariff.n_args}"

        x1 = "Ц" if self.heating is HeatingType.CENTRAL else "Э"
        x2 = "Г" if self.stove is StoveType.GAS else "Э"

        return f"Г{self.tariff.n_args}/{x1}О/{x2}П"

    @classmethod
    def from_config_str(cls, config_str: str):
        kwargs: dict[str, Any] = {}

        for k, v in zip(dc.fields(cls), config_str):
            if isinstance(tp := k.type, UnionType):
                tp = get_args(tp)[0]

            kwargs[k.name] = cast(type, tp)(v)

        return cls(**kwargs)

    @property
    def config_str(self) -> str:
        return "".join(filter(None, dc.astuple(self)))


class OnlineCalculator:
    def __init__(
        self,
        config: CalculatorConfig,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._config = config
        self._session = session or aiohttp.ClientSession()
        self._close_connector = not session

    @classmethod
    def from_config_str(
        cls,
        config_str: str,
        *,
        session: aiohttp.ClientSession | None = None,
    ):
        return cls(
            CalculatorConfig.from_config_str(config_str),
            session=session,
        )

    @property
    def config(self) -> CalculatorConfig:
        return self._config

    def _gen_args(self) -> Iterator[tuple[int, ...]]:
        n = self._config.tariff.n_args

        for idx in range(n):
            lst = [0] * n
            lst[idx] = 1

            yield tuple(lst)

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
