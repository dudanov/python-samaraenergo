import asyncio
import datetime as dt
import logging
import sys

from . import (
    CalculatorConfig,
    HeatingType,
    OnlineCalculator,
    Position,
    StoveType,
    Tariff,
)

logging.basicConfig(level=logging.DEBUG)


async def main():
    config = CalculatorConfig(
        position=Position.CITY,
        tariff=Tariff.TWO,
        heating=HeatingType.CENTRAL,
        stove=StoveType.GAS,
    )

    print(f"Config: {config}")
    print(f"Config as string: {config.config_str}")

    async with OnlineCalculator(config) as calc:
        print(await calc.get_cost(date=dt.date(2024, 1, 1)))

    async with OnlineCalculator.from_config_str(config.config_str) as calc:
        print(await calc.get_cost(date=dt.date(2024, 7, 1)))


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

asyncio.run(main())
