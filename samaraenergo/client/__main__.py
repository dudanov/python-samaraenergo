import asyncio
import datetime as dt
import json
import logging
from decimal import Decimal
from zoneinfo import ZoneInfo

from .client import SamaraEnergoClient

logging.basicConfig(level=logging.DEBUG)

with open("secrets.json") as f:
    secrets: dict[str, str] = json.load(f)


async def main():
    async with SamaraEnergoClient(secrets["login"], secrets["password"]) as cli:
        # a = await cli.get_info()
        # print(a)
        await cli.set_value(
            Decimal(12),
            Decimal(13),
            device_id="11712434",
            datetime=dt.datetime.now(ZoneInfo("Europe/Samara")),
        )


asyncio.run(main())
