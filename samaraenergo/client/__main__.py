import asyncio
import json
import logging
from decimal import Decimal

from .client import SamaraEnergoClient

logging.basicConfig(level=logging.DEBUG)

with open("secrets.json") as f:
    secrets: dict[str, str] = json.load(f)


async def main():
    async with SamaraEnergoClient(secrets["login"], secrets["password"]) as cli:
        a = await cli.get_device_values("11712434")
        print(a)
        # rr = await cli.set_value(Decimal(12), Decimal(13), device_id="11712434")
        # print(rr)


asyncio.run(main())
