import os
import asyncio
import streamlit as st
import pandas as pd
import easyocr
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from PIL import Image, ImageDraw
from thefuzz import process

# --- ИНТЕРФЕЙС ---
st.title("📅 Бот-Сканер: Календарь")
st.success("Система распознавания фамилий готова")

API_TOKEN = "8646138607:AAEkoT_Jj_zixGYTti_r1fIjQOKH5_H45-U"
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['ru', 'en'])

reader = load_ocr()

class Form(StatesGroup):
    waiting_for_data = State()
    waiting_for_name = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Пришли **фото графика** или **Excel**.")
    await state.set_state(Form.waiting_for_data)

@dp.message(Form.waiting_for_data, F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    file_path = f"img_{photo.file_id}.jpg"
    await bot.download_file((await bot.get_file(photo.file_id)).file_path, file_path)
    
    msg = await message.answer("🔍 Анализирую структуру таблицы...")
    
    # Читаем текст с координатами (detail=1)
    results = reader.readtext(file_path)
    
    # Группируем текст по строкам (если координаты Y близки)
    lines = {}
    for (bbox, text, prob) in results:
        y_center = (bbox[0][1] + bbox[2][1]) // 2
        found_line = False
        for line_y in lines.keys():
            if abs(line_y - y_center) < 15: # Порог объединения в одну строку
                lines[line_y].append((bbox[0][0], text))
                found_line = True
                break
        if not found_line:
            lines[y_center] = [(bbox[0][0], text)]

    # Сортируем слова в каждой строке слева направо
    formatted_data = []
    for y in sorted(lines.keys()):
        line_text = [t[1] for t in sorted(lines[y], key=lambda x: x[0])]
        formatted_data.append(line_text)
    
    await state.update_data(raw_rows=formatted_data)
    os.remove(file_path)
    await msg.edit_text("✅ Фото обработано. Введи фамилию.")
    await state.set_state(Form.waiting_for_name)

@dp.message(Form.waiting_for_name)
async def handle_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    rows = data.get('raw_rows', [])
    search_name = message.text.strip().lower()

    target_row = None
    best_score = 0
    
    # Ищем строку, где есть наша фамилия
    for row in rows:
        # Проверяем каждое слово в строке на сходство с фамилией
        match, score = process.extractOne(search_name, row)
        if score > 70 and score > best_score:
            best_score = score
            target_row = row

    if not target_row:
        await message.answer("❌ Не удалось найти такую фамилию на фото.")
        return

    # Отрисовка
    try:
        # Убираем саму фамилию из данных, оставляем только цифры/смены
        fio_in_row, _ = process.extractOne(search_name, target_row)
        schedule = [x for x in target_row if x != fio_in_row and any(c.isdigit() for c in x)]
        
        # РАЗМЕРЫ (Компактный вид)
        cell_w, cell_h = 90, 80
        padding = 15
        img = Image.new('RGB', (cell_w*7 + padding*2, cell_h*6 + 120), color='#1C1E21')
        draw = ImageDraw.Draw(img)
        
        draw.text((padding, 20), f"СОТРУДНИК: {fio_in_row.upper()}", fill='#FFFFFF')
        draw.text((padding, 50), "МАЙ 2026", fill='#9DA0A5')

        # Сетка
        for i in range(31):
            r, c = i // 7, i % 7
            x, y = padding + c*cell_w, 120 + r*cell_h
            
            draw.text((x + 10, y + 5), str(i+1), fill='#FFFFFF')
            
            # Если данных меньше 31, ставим выходной
            val = schedule[i] if i < len(schedule) else ""
            is_work = val and any(c.isdigit() for c in val)
            
            rect_color = "#FF7043" if is_work else "#4CAF50" # Оранж - работа, Зеленый - вых
            draw.rounded_rectangle([x+5, y+30, x+85, y+65], radius=6, fill=rect_color)
            
            display_val = val if is_work else "ВЫХ"
            draw.text((x+15, y+38), display_val[:7], fill='#FFFFFF')

        img_path = f"cal_{message.from_user.id}.png"
        img.save(img_path)
        await message.answer_photo(types.FSInputFile(img_path))
        os.remove(img_path)

    except Exception as e:
        await message.answer(f"⚠️ Ошибка отрисовки: {e}")
    finally:
        await state.clear()

async def main():
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    asyncio.run(main())
