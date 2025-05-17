from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from storage import DebtStorage
from operation_parser import parse_operations
from config import OWNER_ID

router = Router()
storage = DebtStorage()

class DebtStates(StatesGroup):
    awaiting_new_person = State()
    awaiting_operation = State()

def main_reply_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="➕ Добавить"), types.KeyboardButton(text="📊 Показать текущее")]
        ],
        resize_keyboard=True
    )

def reply_keyboard_with_names(names: list[str]) -> types.ReplyKeyboardMarkup:
    rows = [names[i:i+2] for i in range(0, len(names), 2)]
    rows.append(["➕ Новый", "🔙 Назад"])
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=name) for name in row] for row in rows],
        resize_keyboard=True
    )

def reply_keyboard_back_only():
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="🔙 Назад")]],
        resize_keyboard=True
    )

async def send_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Привет! Что хочешь сделать?", reply_markup=main_reply_keyboard())

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return await message.answer("У вас нет доступа к этому боту.")
    await send_main_menu(message, state)

@router.message(F.text == "➕ Добавить")
async def handle_add(message: types.Message, state: FSMContext):
    people = storage.get_people()
    if not people:
        await message.answer("У тебя пока нет должников. Введи имя нового:")
        await state.set_state(DebtStates.awaiting_new_person)
    else:
        await message.answer("Выбери должника или создай нового:", reply_markup=reply_keyboard_with_names(people))
        await state.set_state(DebtStates.awaiting_new_person)

@router.message(DebtStates.awaiting_new_person, F.text)
async def save_or_select_person(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if name == "🔙 Назад":
        return await send_main_menu(message, state)
    elif name == "➕ Новый":
        await message.answer("Введи имя нового должника:")
        return
    else:
        storage.add_person(name)
        await state.update_data(current_person=name)
        await message.answer(
            f"Выбран {name}. Теперь введи операцию в виде `+100 еда +200 чай`",
            reply_markup=reply_keyboard_back_only()
        )
        await state.set_state(DebtStates.awaiting_operation)

@router.message(DebtStates.awaiting_operation, F.text)
async def process_operation(message: types.Message, state: FSMContext):
    if message.text.strip() == "🔙 Назад":
        return await send_main_menu(message, state)

    operations = parse_operations(message.text)
    if not operations:
        return await message.answer("Не понял ни одной операции. Пример: `+100 еда +200 чай`")

    data = await state.get_data()
    person = data["current_person"]

    messages = []
    for amount, reason in operations:
        storage.add_operation(person, amount, reason)
        messages.append(f"{amount:+} — {reason or '—'}")

    total = storage.get_total(person)
    await message.answer(
        f"✅ Добавлены операции:" +
        "\n".join(messages) +
        f"\n\nТекущий долг: {total}",
        reply_markup=main_reply_keyboard()
    )
    await state.clear()

@router.message(F.text == "📊 Показать текущее")
async def show_history_menu(message: types.Message):
    people = storage.get_people()
    if not people:
        return await message.answer("Нет ни одного должника.")
    buttons = [[types.InlineKeyboardButton(text=name, callback_data=f"history:{name}:0")] for name in people]
    markup = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выбери должника для просмотра:", reply_markup=markup)

async def render_history_page(name: str, page: int, message: types.Message):
    ops = storage.get_operations(name)
    total_pages = (len(ops) - 1) // 10 + 1
    ops_slice = list(enumerate(ops[page * 10:(page + 1) * 10], start=page * 10))

    text = f"📒 История по {name} (стр. {page+1}/{total_pages}):\n"
    for idx, op in ops_slice:
        ts = op['timestamp'].split("T")[0]
        amt = op['amount']
        reason = op['reason'] or "—"
        text += f"{idx}) {ts} | {amt:+} | {reason}\n"

    buttons = [
        [types.InlineKeyboardButton(text=f"❌ Удалить {idx}", callback_data=f"delop:{name}:{idx}:{page}")]
        for idx, _ in ops_slice
    ]

    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton(text="⬅", callback_data=f"history:{name}:{page - 1}"))
    if (page + 1) * 10 < len(ops):
        nav.append(types.InlineKeyboardButton(text="➡", callback_data=f"history:{name}:{page + 1}"))

    if nav:
        buttons.append(nav)

    buttons.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    markup = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.edit_text(text, reply_markup=markup)

@router.callback_query(F.data.startswith("history:"))
async def view_history(callback: types.CallbackQuery):
    _, name, page = callback.data.split(":")
    await render_history_page(name, int(page), callback.message)

@router.callback_query(F.data.startswith("delop:"))
async def delete_op(callback: types.CallbackQuery):
    _, name, idx, page = callback.data.split(":")
    idx, page = int(idx), int(page)
    ops = storage.get_operations(name)
    if 0 <= idx < len(ops):
        storage.remove_operation(name, idx)
    await render_history_page(name, page, callback.message)

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await send_main_menu(callback.message, state)