import asyncio
import json
import logging

from .client import SamaraEnergoClient

logging.basicConfig(level=logging.DEBUG)

with open("secrets.json") as f:
    secrets: dict[str, str] = json.load(f)


async def main():
    async with SamaraEnergoClient(secrets["login"], secrets["password"]) as cli:
        a = await cli.get_info()
        print(a)


asyncio.run(main())
