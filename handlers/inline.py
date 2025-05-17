from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from enums import Btn
from storage import storage

router = Router()

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

    buttons.append([types.InlineKeyboardButton(text=Btn.BACK.value, callback_data="back_to_menu")])
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
    from handlers.reply import send_main_menu
    await send_main_menu(callback.message, state)