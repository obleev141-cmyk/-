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
st.success("Статус: Бот запущен и ожидает сообщений")
st.info("Чтобы бот работал, эта вкладка браузера должна быть открыта.")

# --- НАСТРОЙКИ (ТОКЕН ВШИТ) ---
API_TOKEN = "8646138607:AAFSSiamq4LQ3TWBOnxw5izNRDZkjgFusCY"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Состояния
class Form(StatesGroup):
    waiting_for_file = State()
    waiting_for_name = State()

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Пришли мне файл Excel (.xlsx) с общим графиком.")
    await state.set_state(Form.waiting_for_file)

# Прием файла
@dp.message(Form.waiting_for_file, F.document)
async def handle_document(message: types.Message, state: FSMContext):
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_path = f"{file_id}.xlsx"
    
    await bot.download_file(file.file_path, file_path)
    await state.update_data(file_path=file_path)
    
    await message.answer("✅ Файл загружен! Теперь напиши фамилию работника.")
    await state.set_state(Form.waiting_for_name)

# Поиск и генерация картинки
@dp.message(Form.waiting_for_name)
async def handle_name(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    file_path = user_data.get('file_path')
    name_to_find = message.text.strip()

    try:
        df = pd.read_excel(file_path)
        col_fio = df.columns[0] # Первая колонка — ФИО
        
        # Поиск совпадения
        result = df[df[col_fio].astype(str).str.contains(name_to_find, case=False, na=False)]

        if result.empty:
            await message.answer(f"❌ Работник '{name_to_find}' не найден. Попробуй еще раз.")
        else:
            row = result.iloc[0]
            
            # Создаем картинку
            width = 700
            height = 120 + (len(df.columns) * 40)
            img = Image.new('RGB', (width, height), color='#1E1E1E') # Темная тема
            draw = ImageDraw.Draw(img)
            
            y = 40
            draw.text((40, y), f"ГРАФИК: {row[col_fio]}", fill='#00FF00') # Зеленый заголовок
            y += 60
            
            # Пишем данные
            for col in df.columns[1:]:
                val = str(row[col]) if pd.notna(row[col]) else "-"
                draw.text((40, y), f"{col}: {val}", fill='#FFFFFF')
                y += 35
            
            img_path = f"result_{message.from_user.id}.png"
            img.save(img_path)
            
            await message.answer_photo(types.FSInputFile(img_path), caption="Ваш персональный график!")
            if os.path.exists(img_path): os.remove(img_path)

    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}")
    finally:
        if file_path and os.path.exists(file_path): os.remove(file_path)
        await state.clear()

async def main():
    # handle_signals=False критически важен для деплоя в Streamlit Cloud
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        st.error(f"Бот отключился: {e}")
