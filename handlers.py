from aiogram import Router, types, F
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from storage import DebtStorage
from operation_parser import parse_operation
from config import OWNER_ID

router = Router()
storage = DebtStorage()

class DebtStates(StatesGroup):
    awaiting_new_person = State()
    awaiting_operation = State()

def back_to_main_menu_button():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 Назад", callback_data="start")]
        ]
    )

@router.message(CommandStart())
@router.callback_query(F.data == "start")
async def cmd_start(message_or_cb, state: FSMContext = None):
    if isinstance(message_or_cb, types.CallbackQuery):
        message = message_or_cb.message
        if state: await state.clear()
    else:
        message = message_or_cb
        if message.from_user.id != OWNER_ID:
            return await message.answer("У вас нет доступа к этому боту.")
    buttons = [
        [types.InlineKeyboardButton(text="➕ Добавить", callback_data="add")],
        [types.InlineKeyboardButton(text="📊 Показать текущее", callback_data="show")],
    ]
    markup = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Привет! Что хочешь сделать?", reply_markup=markup)

@router.callback_query(F.data == "add")
async def handle_add_start(callback: types.CallbackQuery):
    people = storage.get_people()
    if not people:
        markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="➕ Новый должник", callback_data="new_person")],
                [types.InlineKeyboardButton(text="🔙 Назад", callback_data="start")]
            ]
        )
        return await callback.message.edit_text("Нет ни одного должника.\nХочешь добавить нового?", reply_markup=markup)

    buttons = [[types.InlineKeyboardButton(text=name, callback_data=f"add_person:{name}")] for name in people]
    buttons.append([types.InlineKeyboardButton(text="➕ Новый", callback_data="new_person")])
    markup = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("Кому добавить?", reply_markup=markup)

@router.callback_query(F.data == "new_person")
async def ask_new_person(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введи имя нового должника:", reply_markup=back_to_main_menu_button())
    await state.set_state(DebtStates.awaiting_new_person)

@router.message(StateFilter(DebtStates.awaiting_new_person), F.text)
async def save_new_person(message: types.Message, state: FSMContext):
    name = message.text.strip()
    storage.add_person(name)
    await state.update_data(current_person=name)
    await message.answer(f"Добавлен новый: {name}\nТеперь введи операцию в виде `+100 еда`:", reply_markup=back_to_main_menu_button())
    await state.set_state(DebtStates.awaiting_operation)

@router.callback_query(F.data.startswith("add_person:"))
async def ask_for_operation(callback: types.CallbackQuery, state: FSMContext):
    name = callback.data.split(":", 1)[1]
    await state.update_data(current_person=name)
    await callback.message.answer(f"Выбран {name}. Введи операцию в виде `+100 еда`:", reply_markup=back_to_main_menu_button())
    await state.set_state(DebtStates.awaiting_operation)

@router.message(StateFilter(DebtStates.awaiting_operation), F.text)
async def process_operation(message: types.Message, state: FSMContext):
    data = await state.get_data()
    person = data["current_person"]
    result = parse_operation(message.text)
    if not result:
        return await message.answer("Не понял операцию. Пример: `+100 за еду`. Попробуй ещё раз.", reply_markup=back_to_main_menu_button())
    amount, reason = result
    storage.add_operation(person, amount, reason)
    total = storage.get_total(person)
    buttons = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🔁 Добавить ещё", callback_data=f"add_person:{person}")],
            [types.InlineKeyboardButton(text="🔙 Назад", callback_data="start")]
        ]
    )
    await message.answer(
        f"✅ Добавлено {amount} для {person}. Причина: {reason or '—'}.\nТекущий долг: {total}",
        reply_markup=buttons
    )
    await state.clear()

@router.callback_query(F.data == "show")
async def handle_show_start(callback: types.CallbackQuery):
    people = storage.get_people()
    if not people:
        return await callback.message.answer("Нет ни одного должника.", reply_markup=back_to_main_menu_button())
    buttons = [[types.InlineKeyboardButton(text=name, callback_data=f"show_person:{name}")] for name in people]
    markup = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("Выбери человека:", reply_markup=markup)

@router.callback_query(F.data.startswith("show_person:"))
async def show_summary(callback: types.CallbackQuery):
    name = callback.data.split(":", 1)[1]
    total = storage.get_total(name)
    buttons = [[types.InlineKeyboardButton(text="🔍 Все операции", callback_data=f"view_ops:{name}:0")]]
    markup = types.InlineKeyboardMarkup(inline_keyboard=buttons + [[types.InlineKeyboardButton(text="🔙 Назад", callback_data="start")]])
    await callback.message.answer(f"💰 {name}.\nТекущий долг: {total}", reply_markup=markup)


async def show_operations_page(message: types.Message, name: str, page: int):
    ops = storage.get_operations(name)
    total_pages = (len(ops) - 1) // 10 + 1 if ops else 1
    ops_slice = list(enumerate(ops[page * 10: (page + 1) * 10], start=page * 10))

    text = f"📜 Все операции для {name} (страница {page + 1}/{total_pages}):\n"
    keyboard = []
    for idx, op in ops_slice:
        ts = op["timestamp"].split("T")[0]
        amt = op["amount"]
        reason = op["reason"] or "—"
        text += f"{ts} | {amt:>6} | {reason}\n"
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"❌ Удалить {amt} ({reason[:10]})",
                callback_data=f"del_op:{name}:{idx}:{page}"
            )
        ])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton(text="⬅ Назад", callback_data=f"view_ops:{name}:{page - 1}"))
    if (page + 1) * 10 < len(ops):
        nav_buttons.append(types.InlineKeyboardButton(text="➡ Вперёд", callback_data=f"view_ops:{name}:{page + 1}"))

    keyboard += [nav_buttons] if nav_buttons else []
    keyboard.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="start")])

    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data.startswith("view_ops:"))
async def view_operations(callback: types.CallbackQuery):
    _, name, page_str = callback.data.split(":", 2)
    await show_operations_page(callback.message, name, int(page_str))


@router.callback_query(F.data.startswith("del_op:"))
async def delete_operation(callback: types.CallbackQuery):
    _, name, idx_str, page_str = callback.data.split(":", 3)
    index = int(idx_str)
    page = int(page_str)

    ops = storage.get_operations(name)
    if 0 <= index < len(ops):
        amount = ops[index]["amount"]
        storage.remove_operation(name, index)
        await callback.answer(f"Удалена операция на {amount}")
    else:
        await callback.answer("Операция не найдена", show_alert=True)

    await show_operations_page(callback.message, name, page)
