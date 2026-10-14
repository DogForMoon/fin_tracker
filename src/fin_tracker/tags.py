"""Правила отображения и уникальности пользовательских тегов."""


def normalize_tag_name(name: str) -> str:
    """Ключ уникальности; внутренние пробелы сохраняются."""
    normalized = name.strip().casefold()
    if not normalized:
        raise ValueError("Название тега не должно быть пустым.")
    return normalized
