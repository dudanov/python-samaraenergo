import datetime as dt
import json
import logging
from collections import ChainMap
from decimal import Decimal
from time import perf_counter
from typing import Awaitable, Final

import aiohttp
import yarl

from .models import (
    Account,
    Invoice,
    MeterReadingResult,
    MeterReadingResult2,
    PaymentDocument,
    ResponseListModel,
    ResponseModel,
)

_LOGGER: Final = logging.getLogger(__name__)

_BASE_URL: Final = yarl.URL(
    "https://lk.samaraenergo.ru/sap/opu/odata/sap/Z_ERP_UTILITIES_UMC_SRV_01"
)

_HEADER_ACCEPT_JSON: Final = {"Accept": "application/json"}
_HEADER_CONTENT_JSON: Final = {"Content-Type": "application/json"}
_X_CSRF_TOKEN: Final = "x-csrf-token"


def _dump(data: bytes):
    obj = json.loads(data.decode())
    s = json.dumps(obj, ensure_ascii=False, indent=4)

    with open("research/test.json", "w", encoding="utf-8") as f:
        f.write(s)


class SamaraEnergoClient:
    """
    Клиент личного кабинета абонента СамараЭнерго.
    """

    def __init__(
        self,
        user: str,
        password: str,
        *,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """
        Создает клиент личного кабинета СамараЭнерго.

        Параметры:
        - `user`: идентификатор личного счета.
        - `password`: пароль.
        - `session`: готовый объект `aiohttp.ClientSession`.
        - `close_connector`: закрытие коннектора.
        """

        self._BASE_PARAMS: Final = {
            "sap-user": user,
            "sap-password": password,
            "sap-language": "RU",
        }

        self._cli = session or aiohttp.ClientSession()
        self._close_connector = not session

    async def close(self) -> None:
        await self._cli.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        if self._close_connector:
            await self._cli.close()

    async def _get(self, path: str, *expand: str) -> bytes:
        url, params = _BASE_URL.joinpath(path), self._BASE_PARAMS
        headers = None if path.endswith("$value") else _HEADER_ACCEPT_JSON

        if expand:
            params = ChainMap(params, {"$expand": ",".join(expand)})

        async with self._cli.get(
            url=url,
            params=params,
            headers=headers,
            raise_for_status=True,
        ) as x:
            return await x.read()

    def _account_get(self, path: str, account: int, *expand: str) -> Awaitable[bytes]:
        return self._get(f"Accounts('{account}')/{path}", *expand)

    async def get_invoices(self, account: int) -> list[Invoice]:
        """Запрос всех счетов по аккаунту"""

        x = await self._account_get("Invoices", account)
        x = ResponseListModel[Invoice].model_validate_json(x)

        return x.root

    def get_invoice_pdf(self, invoice_id: str) -> Awaitable[bytes]:
        """Запрос счета в формате PDF"""

        return self._get(f"Invoices(InvoiceID='{invoice_id}')/InvoicePDF/$value")

    async def get_payments(self, account: int) -> list[PaymentDocument]:
        """Запрос информации об оплатах"""

        x = await self._account_get("PaymentDocuments", account)
        x = ResponseListModel[PaymentDocument].model_validate_json(x)

        return x.root

    def get_payment_pdf(self, payment_id: str) -> Awaitable[bytes]:
        """Запрос документа, подтверждающего оплату"""

        return self._get(f"OpbelPDFS(Adr='',Email='D',Invid='{payment_id}')/$value")

    async def get_info(self) -> list[Account]:
        tm = perf_counter()

        x = await self._get(
            "Accounts",  # лицевые счета
            # "StandardAccountAddress",
            # "PaymentDocuments",  # документы об оплате
            "ContractAccounts/Invoices",  # счета на оплату
            # "ContractAccounts/Contracts/ContractConsumptionValues",  # биллинговое потребление энергии
            "ContractAccounts/Contracts/Devices/RegistersToRead",  # регистры приборов учета
            # "ContractAccounts/Contracts/Devices/MeterReadingResults",  # показания счетчиков
        )

        tm2 = perf_counter()
        _LOGGER.debug("Fetching time: %f", tm2 - tm)
        _dump(x)

        x = ResponseListModel[Account].model_validate_json(x)

        _LOGGER.debug("Validation time: %f", perf_counter() - tm2)

        return x.root

    async def _fetch_csrf_token(self) -> dict[str, str]:
        """Запрашивает токен CSRF и возвращает HTTP заголовок"""

        async with self._cli.head(
            url=_BASE_URL,
            params=self._BASE_PARAMS,
            headers={_X_CSRF_TOKEN: "Fetch"},
            raise_for_status=True,
        ) as x:
            return {_X_CSRF_TOKEN: x.headers[_X_CSRF_TOKEN]}

    async def set_value(self, *values: Decimal, device_id: str):
        """"""
        assert 1 <= len(values) <= 3
        now = dt.datetime.now(dt.UTC)

        results = [
            MeterReadingResult(
                DependentMeterReadingResults=[],
                ReadingDateTime=now,
                DeviceID=device_id,
                MeterReadingNoteID="920",  # мобильный личный кабинет
                RegisterID=f"{id:03}",
                ReadingResult=value,
            )
            for id, value in enumerate(values, 1)
        ]

        primary, *secondary = results
        primary.DependentMeterReadingResults = secondary
        json_str = primary.model_dump_json()

        headers = ChainMap(
            _HEADER_ACCEPT_JSON,
            _HEADER_CONTENT_JSON,
            await self._fetch_csrf_token(),
        )

        async with self._cli.post(
            _BASE_URL.joinpath("MeterReadingResults"),
            params=self._BASE_PARAMS,
            data=json_str,
            headers=headers,
            raise_for_status=True,
        ) as x:
            result = await x.read()

        _dump(result)
        result = ResponseModel[MeterReadingResult2].model_validate_json(result)
        return result.root
