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
    awaiting_show_person = State()


def main_reply_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="➕ Добавить"), types.KeyboardButton(text="📊 Показать текущее")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )

def reply_keyboard_with_names(names: list[str]) -> types.ReplyKeyboardMarkup:
    rows = [names[i:i+2] for i in range(0, len(names), 2)]
    rows.append(["🔙 Назад"])
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=name) for name in row] for row in rows],
        resize_keyboard=True
    )

def reply_keyboard_for_history(name: str, page: int) -> types.ReplyKeyboardMarkup:
    ops = storage.get_operations(name)
    total_pages = (len(ops) - 1) // 10 + 1
    ops_slice = list(enumerate(ops[page * 10:(page + 1) * 10], start=page * 10))

    buttons = [[f"удалить {idx}"] for idx, _ in ops_slice]

    nav_row = []
    if page > 0:
        nav_row.append("⬅")
    if (page + 1) * 10 < len(ops):
        nav_row.append("➡")
    if nav_row:
        buttons.append(nav_row)

    buttons.append(["🔙 Назад"])
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text=txt) for txt in row] for row in buttons],
        resize_keyboard=True
    )

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return await message.answer("У вас нет доступа к этому боту.")
    await state.clear()
    await message.answer("Привет! Что хочешь сделать?", reply_markup=main_reply_keyboard())

@router.message(F.text == "➕ Добавить")
async def handle_add(message: types.Message, state: FSMContext):
    people = storage.get_people()
    if not people:
        await message.answer("У тебя пока нет должников. Введи имя нового:")
        await state.set_state(DebtStates.awaiting_new_person)
    else:
        await message.answer(f"Введи имя должника (или новое)", reply_markup=reply_keyboard_with_names(people))
        await state.set_state(DebtStates.awaiting_new_person)

@router.message(DebtStates.awaiting_new_person, F.text)
async def save_or_select_person(message: types.Message, state: FSMContext):
    name = message.text.strip()
    storage.add_person(name)
    await state.update_data(current_person=name)
    await message.answer(f"Добавлен {name}. Теперь введи операцию в виде `+100 еда +200 чай`")
    await state.set_state(DebtStates.awaiting_operation)

@router.message(DebtStates.awaiting_operation, F.text)
async def process_operation(message: types.Message, state: FSMContext):
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
        f"✅ Добавлены операции:" + "\n".join(messages) + f"\n\nТекущий долг: {total}",
        reply_markup=main_reply_keyboard()
    )
    await state.clear()


@router.message(F.text == "📊 Показать текущее")
async def start_history_view(message: types.Message):
    people = storage.get_people()
    if not people:
        return await message.answer("Нет ни одного должника.", reply_markup=main_reply_keyboard())
    names = [types.InlineKeyboardButton(text=name, callback_data=f"history:{name}:0") for name in people]
    markup = types.InlineKeyboardMarkup(inline_keyboard=[[btn] for btn in names])
    await message.answer("Выбери должника:", reply_markup=markup)

@router.callback_query(F.data.startswith("history:"))
async def view_history(callback: types.CallbackQuery):
    _, name, page = callback.data.split(":")
    page = int(page)
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
        [
            types.InlineKeyboardButton(text=f"❌ Удалить {idx}", callback_data=f"delop:{name}:{idx}:{page}")
        ] for idx, _ in ops_slice
    ]

    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton(text="⬅", callback_data=f"history:{name}:{page - 1}"))
    if (page + 1) * 10 < len(ops):
        nav.append(types.InlineKeyboardButton(text="➡", callback_data=f"history:{name}:{page + 1}"))

    buttons.append(nav) if nav else None
    buttons.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="start")])

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("delop:"))
async def delete_op(callback: types.CallbackQuery):
    _, name, idx, page = callback.data.split(":")
    idx, page = int(idx), int(page)

    ops = storage.get_operations(name)
    if 0 <= idx < len(ops):
        amt = ops[idx]["amount"]
        storage.remove_operation(name, idx)
        await callback.answer(f"Удалена операция {amt:+}")
    else:
        await callback.answer("Операция не найдена", show_alert=True)

    # Перерисовываем ту же страницу
    callback.data = f"history:{name}:{page}"
    await view_history(callback)


@router.message(F.text == "📊 Показать текущее")
@router.message(DebtStates.awaiting_show_person, F.text)
async def show_summary(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if text == "🔙 Назад":
        await state.clear()
        return await cmd_start(message, state)
    elif text == "⬅" or text == "➡":
        data = await state.get_data()
        page = data.get("page", 0)
        name = data.get("current_person")

        if text == "⬅":
            page = max(page - 1, 0)
        else:
            page += 1

        await state.update_data(page=page)
    elif text.startswith("удалить"):
        data = await state.get_data()
        name = data["current_person"]
        page = data.get("page", 0)
        idx = int(text.split(" ", 1)[1])

        ops = storage.get_operations(name)
        if 0 <= idx < len(ops):
            storage.remove_operation(name, idx)
            await message.answer(f"Удалена операция {idx + 1}")
        else:
            await message.answer("Операция не найдена")

    else:
        name = text
        page = 0
        await state.update_data(current_person=name, page=page)

    # отрисовать историю
    data = await state.get_data()
    name = data["current_person"]
    page = data.get("page", 0)

    ops = storage.get_operations(name)
    total = storage.get_total(name)
    total_pages = (len(ops) - 1) // 10 + 1
    ops_slice = ops[page * 10:(page + 1) * 10]

    if not ops_slice:
        await message.answer("Нет операций на этой странице.")
    else:
        lines = []
        for idx, op in enumerate(ops_slice, start=page * 10):
            ts = op["timestamp"].split("T")[0]
            amt = op["amount"]
            reason = op["reason"] or "—"
            lines.append(f"{idx}) {ts} | {amt:+} | {reason}")
        text = f"📒 История по {name} (стр. {page + 1}/{total_pages}):\n" + "\n".join(lines) + f"\n\nИтог: {total}"

        await message.answer(text, reply_markup=reply_keyboard_for_history(name, page))