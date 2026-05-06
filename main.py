import os
import asyncio
import streamlit as st
import pandas as pd
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from PIL import Image, ImageDraw

# --- ИНТЕРФЕЙС STREAMLIT (Чтобы бот не засыпал) ---
st.title("🤖 Бот-График")
st.write("Статус: Работает")

# --- ВСТАВЬ СВОЙ ТОКЕН ТУТ ---
API_TOKEN = "8646138607:AAFSSiamq4LQ3TWBOnxw5izNRDZkjgFusCY"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    waiting_for_file = State()
    waiting_for_name = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("Привет! Пришли мне Excel-файл (.xlsx) с графиком.")
    await state.set_state(Form.waiting_for_file)

@dp.message(Form.waiting_for_file, F.document)
async def handle_document(message: types.Message, state: FSMContext):
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_path = f"{file_id}.xlsx"
    await bot.download_file(file.file_path, file_path)
    await state.update_data(file_path=file_path)
    await message.answer("Файл получен! Напиши фамилию сотрудника.")
    await state.set_state(Form.waiting_for_name)

@dp.message(Form.waiting_for_name)
async def handle_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_path = data.get('file_path')
    name = message.text.strip()
    try:
        df = pd.read_excel(file_path)
        col_fio = df.columns[0]
        result = df[df[col_fio].astype(str).str.contains(name, case=False, na=False)]
        if result.empty:
            await message.answer("Сотрудник не найден.")
        else:
            row = result.iloc[0]
            img = Image.new('RGB', (600, 400), color='#FFFFFF')
            d = ImageDraw.Draw(img)
            y = 20
            for col in df.columns:
                d.text((20, y), f"{col}: {row[col]}", fill='#000000')
                y += 30
            img_path = f"{name}.png"
            img.save(img_path)
            await message.answer_photo(types.FSInputFile(img_path))
            os.remove(img_path)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
    finally:
        if os.path.exists(file_path): os.remove(file_path)
        await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
