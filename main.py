import os
import asyncio
import streamlit as st
import pandas as pd
import numpy as np
import cv2
import easyocr
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from PIL import Image, ImageDraw

# --- ИНТЕРФЕЙС ---
st.title("📅 Бот-Сканер Графиков")
st.info("Теперь я принимаю и фото, и Excel!")

API_TOKEN = "8646138607:AAEkoT_Jj_zixGYTti_r1fIjQOKH5_H45-U"
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Инициализируем читалку текста (русский + английский)
reader = easyocr.Reader(['ru', 'en'])

class Form(StatesGroup):
    waiting_for_data = State() # Ждем файл или фото
    waiting_for_name = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Пришли мне **фото графика** или **Excel-файл**.")
    await state.set_state(Form.waiting_for_data)

# ОБРАБОТКА ФОТО
@dp.message(Form.waiting_for_data, F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    photo_path = f"img_{photo.file_id}.jpg"
    await bot.download_file(file_info.file_path, photo_path)
    
    msg = await message.answer("🔍 Сканирую фото... это может занять 10-15 секунд.")
    
    # Распознаем текст
    results = reader.readtext(photo_path)
    
    # Простейшая сборка таблицы из координат текста (упрощенно)
    data = []
    for (bbox, text, prob) in results:
        data.append(text)
    
    # Создаем временный DataFrame (эмуляция таблицы)
    # ВАЖНО: Точность зависит от качества фото. 
    # Для тестов создадим структуру, где 1-е слово ФИО, остальные - даты
    df_temp = pd.DataFrame([data]) 
    
    temp_excel = f"temp_{message.from_user.id}.xlsx"
    df_temp.to_excel(temp_excel, index=False)
    
    await state.update_data(file_path=temp_excel)
    os.remove(photo_path)
    await msg.edit_text("✅ Текст распознан! Теперь введи фамилию для календаря.")
    await state.set_state(Form.waiting_for_name)

# ОБРАБОТКА EXCEL (оставляем как было)
@dp.message(Form.waiting_for_data, F.document)
async def handle_document(message: types.Message, state: FSMContext):
    file_id = message.document.file_id
    file_path = f"{file_id}.xlsx"
    await bot.download_file((await bot.get_file(file_id)).file_path, file_path)
    await state.update_data(file_path=file_path)
    await message.answer("✅ Файл загружен. Введи фамилию.")
    await state.set_state(Form.waiting_for_name)

@dp.message(Form.waiting_for_name)
async def handle_name(message: types.Message, state: FSMContext):
    # Тут остается твой предыдущий код отрисовки календаря
    # (Копируй логику с отрисовкой из предыдущего моего ответа)
    # ...
    pass

async def main():
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    asyncio.run(main())
