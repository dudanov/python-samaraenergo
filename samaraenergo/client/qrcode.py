import io
import logging
from typing import Any, Mapping, cast

import PIL.Image
import pymupdf
from PIL.Image import Image, Palette

_LOGGER = logging.getLogger(__name__)


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
    data = cast(Mapping[str, Any], page.get_text("dict"))  # type: ignore[attr-defined]
    blocks = cast(list[Mapping[str, Any]], data["blocks"])

    for x in blocks:
        if img := x.get("image"):
            width, height = x["width"], x["height"]
            ratio = width / height

            if height < 400 and not (0.9 <= ratio <= 1.1):
                continue

            img = PIL.Image.open(io.BytesIO(img)).convert("RGB")

            _LOGGER.debug("Найдено изображение: %s", img)

            if ratio != 1:
                px = min(width, height)
                _LOGGER.debug("Обрезка в квадрат %dx%d пикселей", px, px)

                return img.crop((0, 0, px, px))

            return img

    raise FileNotFoundError("Не удалось найти QR-код в счете PDF")
