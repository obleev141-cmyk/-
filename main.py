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
st.title("📅 Бот: Фото -> Excel")
st.info("Пришли фото, чтобы получить таблицу и календарь")

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
    await message.answer("👋 Привет! Пришли фото графика. Я превращу его в Excel и нарисую календарь.")
    await state.set_state(Form.waiting_for_data)

@dp.message(Form.waiting_for_data, F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    photo_path = f"img_{photo.file_id}.jpg"
    await bot.download_file((await bot.get_file(photo.file_id)).file_path, photo_path)
    
    msg = await message.answer("⚙️ Обрабатываю фото... Создаю Excel таблицу...")
    
    # OCR сканирование
    results = reader.readtext(photo_path)
    
    # Группировка текста в таблицу по строкам (Y-координата)
    lines = {}
    for (bbox, text, prob) in results:
        y_center = (bbox[0][1] + bbox[2][1]) // 2
        found_line = False
        for line_y in lines.keys():
            if abs(line_y - y_center) < 15:
                lines[line_y].append((bbox[0][0], text))
                found_line = True
                break
        if not found_line:
            lines[y_center] = [(bbox[0][0], text)]

    # Формируем список списков (ряды таблицы)
    table_data = []
    for y in sorted(lines.keys()):
        row = [t[1] for t in sorted(lines[y], key=lambda x: x[0])]
        table_data.append(row)
    
    # --- СОЗДАНИЕ И ОТПРАВКА EXCEL ---
    df = pd.DataFrame(table_data)
    excel_file = f"result_{message.from_user.id}.xlsx"
    df.to_excel(excel_file, index=False, header=False)
    
    # Отправляем файл пользователю
    input_file = types.FSInputFile(excel_file)
    await message.answer_document(input_file, caption="📊 Вот твой график в формате Excel!")
    
    # Сохраняем данные для отрисовки календаря
    await state.update_data(raw_rows=table_data, file_path=excel_file)
    os.remove(photo_path)
    
    await msg.edit_text("✅ Таблица готова! Теперь напиши фамилию, чтобы я нарисовал календарь.")
    await state.set_state(Form.waiting_for_name)

@dp.message(Form.waiting_for_name)
async def handle_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    rows = data.get('raw_rows', [])
    search_name = message.text.strip().lower()

    # Поиск фамилии в таблице
    target_row = None
    best_score = 0
    fio_found = ""

    for row in rows:
        match, score = process.extractOne(search_name, row)
        if score > 70 and score > best_score:
            best_score = score
            target_row = row
            fio_found = match

    if not target_row:
        await message.answer("❌ Фамилия не найдена. Попробуй еще раз.")
        return

    # Отрисовка календаря (как в предыдущих версиях)
    try:
        schedule = [x for x in target_row if x != fio_found and any(c.isdigit() for c in x)]
        
        cell_w, cell_h = 90, 80
        padding = 15
        img = Image.new('RGB', (cell_w*7 + padding*2, cell_h*6 + 120), color='#1C1E21')
        draw = ImageDraw.Draw(img)
        
        draw.text((padding, 20), f"СОТРУДНИК: {fio_found.upper()}", fill='#FFFFFF')
        draw.text((padding, 50), "КАЛЕНДАРЬ НА ОСНОВЕ ФОТО", fill='#9DA0A5')

        for i in range(31):
            r, c = i // 7, i % 7
            x, y = padding + c*cell_w, 120 + r*cell_h
            draw.text((x + 10, y + 5), str(i+1), fill='#FFFFFF')
            
            val = schedule[i] if i < len(schedule) else ""
            is_work = val and any(c.isdigit() for c in val)
            
            rect_color = "#FF7043" if is_work else "#4CAF50"
            draw.rounded_rectangle([x+5, y+30, x+85, y+65], radius=6, fill=rect_color)
            draw.text((x+15, y+38), val[:7] if is_work else "ВЫХ", fill='#FFFFFF')

        img_path = f"cal_{message.from_user.id}.png"
        img.save(img_path)
        await message.answer_photo(types.FSInputFile(img_path))
        os.remove(img_path)

    except Exception as e:
        await message.answer(f"⚠️ Ошибка графики: {e}")
    finally:
        # Удаляем Excel файл после завершения работы
        excel_path = data.get('file_path')
        if excel_path and os.path.exists(excel_path):
            os.remove(excel_path)
        await state.clear()

async def main():
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    asyncio.run(main())
