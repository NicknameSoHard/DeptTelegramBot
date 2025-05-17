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

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, force_user_id: int = None):
    user_id = force_user_id or message.from_user.id
    if user_id != OWNER_ID:
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
        names = "\n".join(people)
        await message.answer(f"Введи имя должника (или новое):\n{names}")
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
        f"✅ Добавлены операции:" +
        "\n".join(messages) +
        f"\n\nТекущий долг: {total}",
        reply_markup=main_reply_keyboard()
    )
    await state.clear()

@router.message(F.text == "📊 Показать текущее")
async def start_history_view(message: types.Message):
    people = storage.get_people()
    if not people:
        return await message.answer("Нет ни одного должника.")
    buttons = [[types.InlineKeyboardButton(text=name, callback_data=f"history:{name}:0")] for name in people]
    markup = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выбери должника для просмотра:", reply_markup=markup)

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
    await callback.message.edit_text(text, reply_markup=markup)

@router.callback_query(F.data.startswith("delop:"))
async def delete_op(callback: types.CallbackQuery):
    _, name, idx, page = callback.data.split(":")
    idx, page = int(idx), int(page)

    ops = storage.get_operations(name)
    if 0 <= idx < len(ops):
        storage.remove_operation(name, idx)

    # просто перерисовываем ту же страницу
    await view_history(types.CallbackQuery(
        id=callback.id,
        from_user=callback.from_user,
        chat_instance=callback.chat_instance,
        message=callback.message,
        data=f"history:{name}:{page}"
    ))

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await cmd_start(callback.message, state, force_user_id=callback.from_user.id)