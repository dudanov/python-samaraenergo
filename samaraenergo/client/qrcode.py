import io
import logging
import re
from decimal import Decimal
from typing import Any, Final, Mapping, cast

import PIL.Image
import pymupdf
from PIL.Image import Image, Palette

_LOGGER: Final = logging.getLogger(__name__)
_RE_AMOUNT: Final = re.compile(r"Итого к оплате: (.+) руб.")


def save_to_png(img: Image) -> bytes:
    bio = io.BytesIO()
    img = img.convert("P", palette=Palette.WEB)
    img.save(bio, format="png", optimize=True)

    return bio.getvalue()


def find_qrcode(pdf: bytes) -> Image:
    # PDF счета СамараЭнерго не сохраняют QR-коды как картинку с `xref` ссылкой.
    # Поэтому получаем доступ к данным всех объектов на низком уровне
    # и ищем самостоятельно.

    page = pymupdf.open(stream=pdf).load_page(0)

    text: str = page.get_text("text")  # type: ignore[attr-defined]
    print(text)

    if m := _RE_AMOUNT.search(text):
        summ = Decimal(m.group(1).replace(".", "").replace(",", "."))
        _LOGGER.debug("Найдена сумма оплаты счета: %s", summ)
        print(summ)

    blocks = cast(list[Mapping[str, Any]], page.get_text("dict")["blocks"])  # type: ignore[attr-defined]

    for x in blocks:
        if not (img := x.get("image")):
            continue

        width, height = x["width"], x["height"]

        if (height < 400) or not (0.9 <= (ratio := width / height) <= 1.1):
            continue

        img = PIL.Image.open(io.BytesIO(img)).convert("RGB")

        _LOGGER.debug("Найдено изображение: %s", img)

        if ratio == 1:
            return img

        px = min(width, height)
        _LOGGER.debug("Обрезка в квадрат %dx%d пикселей", px, px)

        return img.crop((0, 0, px, px))

    raise FileNotFoundError("Не удалось найти QR-код в счете PDF")
