from aiogram import F, Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import OWNER_ID
from enums import Btn
from handlers.keyboard import (create_back_keyboard, create_main_keyboard,
                               create_names_keyboard)
from operation_parser import parse_operations
from storage import storage

router = Router()

class DebtStates(StatesGroup):
    awaiting_new_person = State()
    awaiting_operation = State()
    awaiting_history_person = State()

async def send_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer('Привет! Что хочешь сделать?', reply_markup=create_main_keyboard())

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return await message.answer('У вас нет доступа к этому боту.')
    await send_main_menu(message, state)

@router.message(F.text == Btn.ADD.value)
async def handle_add(message: types.Message, state: FSMContext):
    people = storage.get_people()
    if not people:
        await message.answer('У тебя пока нет должников. Введи имя нового:')
        await state.set_state(DebtStates.awaiting_new_person)
    else:
        await message.answer('Выбери должника или создай нового:', reply_markup=create_names_keyboard(people))
        await state.set_state(DebtStates.awaiting_new_person)

@router.message(DebtStates.awaiting_new_person, F.text)
async def save_or_select_person(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if name == Btn.BACK.value:
        return await send_main_menu(message, state)
    elif name == Btn.NEW.value:
        await message.answer('Введи имя нового должника:')
        return
    else:
        storage.add_person(name)
        await state.update_data(current_person=name)
        await message.answer(
            f'Выбран {name}. Теперь введи операцию в виде `+100 еда +200 чай`',
            reply_markup=create_back_keyboard()
        )
        await state.set_state(DebtStates.awaiting_operation)

@router.message(DebtStates.awaiting_operation, F.text)
async def process_operation(message: types.Message, state: FSMContext):
    if message.text.strip() == Btn.BACK.value:
        return await send_main_menu(message, state)

    operations = parse_operations(message.text)
    if not operations:
        return await message.answer('Не понял ни одной операции. Пример: `+100 еда +200 чай`')

    data = await state.get_data()
    person = data['current_person']

    messages = [f"{amount:+} — {reason or '—'}" for amount, reason in operations]
    for amount, reason in operations:
        storage.add_operation(person, amount, reason)

    total = storage.get_total(person)
    await message.answer(
        f'✅ Добавлены операции:\n' +
        '\n'.join(messages) +
        f'\n\nТекущий долг: {total}',
        reply_markup=create_main_keyboard()
    )
    await state.clear()

@router.message(F.text == Btn.SHOW.value)
async def handle_show(message: types.Message):
    people = storage.get_people()
    if not people:
        return await message.answer('Нет ни одного должника.')
    buttons = [[types.InlineKeyboardButton(text=name, callback_data=f'history:{name}:0')] for name in people]
    markup = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer('Выбери должника для просмотра:', reply_markup=markup)