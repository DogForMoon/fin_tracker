"""Точный разбор и отображение рублей без преобразования в float."""

import re


def parse_amount(value: str) -> int:
    """Вернуть положительное количество копеек или ValueError."""
    if re.fullmatch(r"[0-9]+(?:[.,][0-9]{1,2})?", value) is None:
        raise ValueError("Введите сумму: 125, 125.5 или 125,50; минимум 0,01 ₽.")
    rubles, _, fraction = value.replace(",", ".").partition(".")
    amount = int(rubles) * 100 + int(fraction.ljust(2, "0"))
    if amount == 0:
        raise ValueError("Сумма должна быть не меньше 0,01 ₽.")
    return amount


def format_amount(amount_kopecks: int) -> str:
    """Отобразить копейки с двумя десятичными знаками и символом рубля."""
    rubles, kopecks = divmod(amount_kopecks, 100)
    return f"{rubles},{kopecks:02d} ₽"
