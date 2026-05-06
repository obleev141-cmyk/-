import os
import asyncio
import streamlit as st
import pandas as pd
import easyocr
import numpy as np
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from PIL import Image, ImageDraw
from thefuzz import process

# --- ИНТЕРФЕЙС STREAMLIT ---
st.title("📅 Бот-Конвертер: Фото в Excel")
st.success("Система готова к работе")

API_TOKEN = "8646138607:AAEkoT_Jj_zixGYTti_r1fIjQOKH5_H45-U"
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Загрузка нейросети
@st.cache_resource
def load_reader():
    return easyocr.Reader(['ru', 'en'])

reader = load_reader()

class Form(StatesGroup):
    waiting_for_data = State()
    waiting_for_name = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Пришли **фото графика**. Я сделаю из него Excel и нарисую календарь.")
    await state.set_state(Form.waiting_for_data)

@dp.message(Form.waiting_for_data, F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    photo_path = f"img_{photo.file_id}.jpg"
    await bot.download_file((await bot.get_file(photo.file_id)).file_path, photo_path)
    
    msg = await message.answer("⚙️ Сканирую фото и создаю таблицу...")
    
    # Распознавание
    results = reader.readtext(photo_path)
    
    # Группировка в строки по координате Y
    lines = {}
    for (bbox, text, prob) in results:
        y_center = (bbox[0][1] + bbox[2][1]) // 2
        found = False
        for line_y in lines.keys():
            if abs(line_y - y_center) < 20: # Порог для объединения в строку
                lines[line_y].append((bbox[0][0], text))
                found = True
                break
        if not found:
            lines[y_center] = [(bbox[0][0], text)]

    table_data = []
    for y in sorted(lines.keys()):
        row = [t[1] for t in sorted(lines[y], key=lambda x: x[0])]
        table_data.append(row)
    
    # Генерируем Excel
    df = pd.DataFrame(table_data)
    excel_path = f"table_{message.from_user.id}.xlsx"
    df.to_excel(excel_path, index=False, header=False)
    
    await message.answer_document(types.FSInputFile(excel_path), caption="📊 Твой график в Excel!")
    
    await state.update_data(raw_rows=table_data, excel_path=excel_path)
    os.remove(photo_path)
    await msg.edit_text("✅ Таблица готова! Теперь введи фамилию.")
    await state.set_state(Form.waiting_for_name)

@dp.message(Form.waiting_for_name)
async def handle_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    rows = data.get('raw_rows', [])
    search_name = message.text.strip().lower()

    target_row = None
    fio_final = ""
    
    for row in rows:
        match, score = process.extractOne(search_name, row)
        if score > 70:
            target_row = row
            fio_final = match
            break

    if not target_row:
        await message.answer("❌ Фамилия не найдена. Проверь Excel, который я скинул выше.")
        return

    try:
        # Смены - это всё, где есть цифры
        schedule = [x for x in target_row if x != fio_final and any(c.isdigit() for c in x)]
        
        # Отрисовка
        cell_w, cell_h = 90, 80
        img = Image.new('RGB', (cell_w*7 + 30, cell_h*6 + 120), color='#1C1E21')
        draw = ImageDraw.Draw(img)
        draw.text((15, 20), f"СОТРУДНИК: {fio_final.upper()}", fill='#FFFFFF')

        for i in range(31):
            r, c = i // 7, i % 7
            x, y = 15 + c*cell_w, 120 + r*cell_h
            
            val = schedule[i] if i < len(schedule) else ""
            is_work = val and any(c.isdigit() for c in val)
            
            color = "#FF7043" if is_work else "#4CAF50"
            draw.rounded_rectangle([x+5, y+30, x+85, y+65], radius=6, fill=color)
            draw.text((x+10, y+5), str(i+1), fill='#FFFFFF')
            draw.text((x+15, y+38), val[:7] if is_work else "ВЫХ", fill='#FFFFFF')

        img_path = f"cal_{message.from_user.id}.png"
        img.save(img_path)
        await message.answer_photo(types.FSInputFile(img_path))
        os.remove(img_path)
    except Exception as e:
        await message.answer(f"Ошибка графики: {e}")
    finally:
        if os.path.exists(data.get('excel_path')): os.remove(data.get('excel_path'))
        await state.clear()

async def main():
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    asyncio.run(main())
