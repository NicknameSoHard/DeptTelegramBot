from aiogram import types

from enums import Btn


def create_main_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=Btn.ADD.value),  types.KeyboardButton(text=Btn.SHOW.value)],
            [types.KeyboardButton(text=Btn.EXPORT.value)],
        ],
        resize_keyboard=True
    )

def create_names_keyboard(names: list[str]) -> types.ReplyKeyboardMarkup:
    rows = [names[i:i+2] for i in range(0, len(names), 2)]
    rows.append([Btn.NEW.value, Btn.BACK.value])
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=name) for name in row] for row in rows],
        resize_keyboard=True
    )

def create_back_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=Btn.BACK.value)]],
        resize_keyboard=True
    )