import re


def parse_operations(text: str):
    # Убираем стартовое число без знака, если оно есть
    if re.match(r'^\s*\d+[кK]?', text):
        text = '+' + text.lstrip()

    # Основной парсинг: ищем группы "+ 100 причина" / "-1.2к лекарства"
    pattern = r'([+-])\s*(\d+(?:[.,]?\d+)?)([кК]?)\s*([^\+\-]*)'
    matches = re.findall(pattern, text)

    result = []
    for sign, num, multiplier, reason in matches:
        amount = float(num.replace(",", "."))
        if multiplier.lower() == 'к':
            amount *= 1000
        amount = int(amount)
        if sign == '-':
            amount = -amount
        result.append((amount, reason.strip()))

    return result if result else None
