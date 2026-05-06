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

# --- ИНТЕРФЕЙС STREAMLIT ---
st.set_page_config(page_title="Бот-Конвертер")
st.title("📅 График: Фото ➔ Excel ➔ Календарь")

# Индикатор загрузки для пользователя
if 'ready' not in st.session_state:
    with st.spinner("⏳ Первая загрузка нейросети (3-5 минут)..."):
        try:
            @st.cache_resource
            def load_reader():
                return easyocr.Reader(['ru', 'en'], gpu=False)
            reader_obj = load_reader()
            st.session_state['ready'] = True
            st.success("✅ Нейросеть готова к работе!")
        except Exception as e:
            st.error(f"Ошибка при запуске: {e}")

# Данные бота
API_TOKEN = "8646138607:AAEkoT_Jj_zixGYTti_r1fIjQOKH5_H45-U"
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    waiting_for_data = State()
    waiting_for_name = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Пришли фото графика. Я сделаю из него Excel и календарь.")
    await state.set_state(Form.waiting_for_data)

@dp.message(Form.waiting_for_data, F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    photo_path = f"img_{photo.file_id}.jpg"
    await bot.download_file((await bot.get_file(photo.file_id)).file_path, photo_path)
    
    msg = await message.answer("⚙️ Распознаю таблицу и создаю Excel-файл...")
    
    try:
        reader = easyocr.Reader(['ru', 'en'], gpu=False)
        results = reader.readtext(photo_path)
        
        # Группировка по строкам
        lines = {}
        for (bbox, text, prob) in results:
            y_center = (bbox[0][1] + bbox[2][1]) // 2
            found = False
            for line_y in lines.keys():
                if abs(line_y - y_center) < 20:
                    lines[line_y].append((bbox[0][0], text))
                    found = True
                    break
            if not found:
                lines[y_center] = [(bbox[0][0], text)]

        table_data = []
        for y in sorted(lines.keys()):
            row = [t[1] for t in sorted(lines[y], key=lambda x: x[0])]
            table_data.append(row)
        
        excel_path = f"table_{message.from_user.id}.xlsx"
        pd.DataFrame(table_data).to_excel(excel_path, index=False, header=False)
        
        await message.answer_document(types.FSInputFile(excel_path), caption="📊 Вот твоя таблица из фото!")
        await state.update_data(raw_rows=table_data, excel_path=excel_path)
        await msg.edit_text("✅ Распознано! Теперь введи фамилию для картинки.")
        await state.set_state(Form.waiting_for_name)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        if os.path.exists(photo_path): os.remove(photo_path)

@dp.message(Form.waiting_for_name)
async def handle_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    rows = data.get('raw_rows', [])
    search_name = message.text.strip().lower()

    target_row, fio_final = None, ""
    for row in rows:
        match, score = process.extractOne(search_name, row)
        if score > 70:
            target_row, fio_final = row, match
            break

    if not target_row:
        await message.answer("❌ Фамилия не найдена.")
        return

    try:
        schedule = [x for x in target_row if x != fio_final and any(c.isdigit() for c in x)]
        
        # Отрисовка календаря
        cell_w, cell_h = 90, 80
        img = Image.new('RGB', (cell_w*7 + 30, cell_h*6 + 120), color='#1C1E21')
        draw = ImageDraw.Draw(img)
        draw.text((15, 20), f"СОТРУДНИК: {fio_final.upper()}", fill='#FFFFFF')

        for i in range(min(31, len(schedule))):
            r, c = i // 7, i % 7
            x, y = 15 + c*cell_w, 120 + r*cell_h
            val = schedule[i]
            is_work = any(c.isdigit() for c in val)
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
        if os.path.exists(data.get('excel_path', '')): os.remove(data.get('excel_path'))
        await state.clear()

async def main():
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    asyncio.run(main())
