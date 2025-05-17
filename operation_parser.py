import re


def parse_operation(text: str):
    pattern = r'([+-]?)\s*(\d+(?:[.,]?\d+)?)([кK]?)\s*(.*)?'
    match = re.match(pattern, text.strip())
    if not match:
        return None

    sign, number, multiplier, reason = match.groups()
    amount = float(number.replace(',', '.'))

    if multiplier.lower() == 'к':
        amount *= 1000

    amount = int(amount)
    if sign == '-':
        amount = -amount

    return amount, reason.strip()