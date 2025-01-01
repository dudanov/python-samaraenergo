import asyncio
import json
import logging
from decimal import Decimal

from .client import SamaraEnergoClient
from .qrcode import find_qrcode

logging.basicConfig(level=logging.DEBUG)

with open("secrets.json") as f:
    secrets: dict[str, str] = json.load(f)


async def main():
    async with SamaraEnergoClient(secrets["login"], secrets["password"]) as cli:
        a = await cli.get_invoices("10887247")
        print(a)
        a = await cli.get_invoice_pdf(a[0].InvoiceID)
        a = find_qrcode(a)
        print(a)
        # rr = await cli.set_value(Decimal(12), Decimal(13), device_id="11712434")
        # print(rr)


asyncio.run(main())
