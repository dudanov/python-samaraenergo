import asyncio
import datetime as dt
import json
import logging
from zoneinfo import ZoneInfo

from .client import SamaraEnergoClient
from .models import MeterReadingResult

rr = MeterReadingResult(
    DependentMeterReadingResults=[],
    ReadingDateTime=dt.datetime.now(ZoneInfo("Europe/Samara")),
    DeviceID="",
    MeterReadingNoteID="",
    RegisterID="",
    ReadingResult=4.4,
)

tt = rr.model_dump_json(indent=4)
print(tt)

logging.basicConfig(level=logging.DEBUG)

with open("secrets.json") as f:
    secrets: dict[str, str] = json.load(f)


async def main():
    async with SamaraEnergoClient(secrets["login"], secrets["password"]) as cli:
        a = await cli.get_info()
        print(a)


asyncio.run(main())
