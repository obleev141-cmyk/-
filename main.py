import os
import asyncio
import streamlit as st
import pandas as pd
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from PIL import Image, ImageDraw

# --- ИНТЕРФЕЙС STREAMLIT ---
st.title("🤖 Бот-График")
st.success("Статус: Работает")
st.info("Не закрывай эту страницу, чтобы бот не отключился.")

# --- КОНФИГУРАЦИЯ (НОВЫЙ ТОКЕН) ---
API_TOKEN = "8646138607:AAEkoT_Jj_zixGYTti_r1fIjQOKH5_H45-U"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    waiting_for_file = State()
    waiting_for_name = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Пришли мне файл Excel (.xlsx) с графиком.")
    await state.set_state(Form.waiting_for_file)

@dp.message(Form.waiting_for_file, F.document)
async def handle_document(message: types.Message, state: FSMContext):
    if not message.document.file_name.lower().endswith(('.xlsx', '.xls')):
        await message.answer("❌ Пожалуйста, пришли именно файл Excel.")
        return
    
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_name = f"{file_id}.xlsx"
    await bot.download_file(file.file_path, file_name)
    
    await state.update_data(file_path=file_name)
    await message.answer("✅ Файл получен! Теперь напиши фамилию сотрудника.")
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
            await message.answer(f"❌ Работник '{name}' не найден.")
        else:
            row = result.iloc[0]
            # Создаем картинку
            width = 600
            height = 120 + (len(df.columns) * 40)
            img = Image.new('RGB', (width, height), color='#FFFFFF')
            draw = ImageDraw.Draw(img)
            
            y = 30
            draw.text((40, y), f"ГРАФИК: {row[col_fio]}", fill='#000000')
            y += 50
            
            for col in df.columns[1:]:
                val = str(row[col]) if pd.notna(row[col]) else "-"
                draw.text((40, y), f"• {col}: {val}", fill='#333333')
                y += 35
            
            img_path = f"graph_{message.from_user.id}.png"
            img.save(img_path)
            
            await message.answer_photo(types.FSInputFile(img_path), caption="Ваш график готов!")
            if os.path.exists(img_path): os.remove(img_path)

    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        await state.clear()

async def main():
    # handle_signals=False исправляет ошибку из твоих логов
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        st.error(f"Бот упал: {e}")
