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
st.set_page_config(page_title="Конвертер Графиков")
st.title("🤖 Бот: Фото ➔ Excel")

# Статус загрузки
status = st.empty()
status.info("⏳ Загрузка системы... Подождите пару минут.")

# Настройки бота
API_TOKEN = "8646138607:AAEkoT_Jj_zixGYTti_r1fIjQOKH5_H45-U"
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Кэшируем нейросеть для экономии памяти
@st.cache_resource
def get_ocr():
    return easyocr.Reader(['ru', 'en'], gpu=False)

class Form(StatesGroup):
    waiting_for_data = State()
    waiting_for_name = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Пришли фото графика. Я сделаю из него таблицу Excel и календарь.")
    await state.set_state(Form.waiting_for_data)

@dp.message(Form.waiting_for_data, F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    path = f"img_{photo.file_id}.jpg"
    await bot.download_file((await bot.get_file(photo.file_id)).file_path, path)
    
    msg = await message.answer("🔍 Читаю текст и создаю Excel...")
    
    try:
        reader = get_ocr()
        results = reader.readtext(path)
        
        # Группируем текст по строкам (Y-координата)
        lines = {}
        for (bbox, text, prob) in results:
            y = (bbox[0][1] + bbox[2][1]) // 2
            found = False
            for line_y in lines.keys():
                if abs(line_y - y) < 20:
                    lines[line_y].append((bbox[0][0], text))
                    found = True
                    break
            if not found: lines[y] = [(bbox[0][0], text)]

        table_data = []
        for y in sorted(lines.keys()):
            table_data.append([t[1] for t in sorted(lines[y], key=lambda x: x[0])])
        
        excel_path = f"table_{message.from_user.id}.xlsx"
        pd.DataFrame(table_data).to_excel(excel_path, index=False, header=False)
        
        await message.answer_document(types.FSInputFile(excel_path), caption="📊 Твой график в Excel!")
        await state.update_data(raw_rows=table_data, excel_path=excel_path)
        await msg.edit_text("✅ Готово! Теперь введи фамилию.")
        await state.set_state(Form.waiting_for_name)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
    finally:
        if os.path.exists(path): os.remove(path)

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
        # Извлекаем только смены (где есть цифры)
        schedule = [x for x in target_row if x != fio_final and any(c.isdigit() for c in x)]
        
        # Рисуем календарь
        w, h = 660, 600
        img = Image.new('RGB', (w, h), color='#1C1E21')
        draw = ImageDraw.Draw(img)
        draw.text((20, 20), f"СОТРУДНИК: {fio_final.upper()}", fill='#FFFFFF')

        for i in range(min(31, len(schedule))):
            r, c = i // 7, i % 7
            x, y = 20 + c*90, 100 + r*80
            val = schedule[i]
            is_work = any(c.isdigit() for c in val)
            color = "#FF7043" if is_work else "#4CAF50"
            draw.rounded_rectangle([x, y+25, x+80, y+55], radius=5, fill=color)
            draw.text((x+5, y), str(i+1), fill='#9DA0A5')
            draw.text((x+10, y+32), val[:7] if is_work else "ВЫХ", fill='#FFFFFF')

        img_p = f"cal_{message.from_user.id}.png"
        img.save(img_p)
        await message.answer_photo(types.FSInputFile(img_p))
        os.remove(img_p)
    except Exception as e:
        await message.answer(f"Ошибка картинки: {e}")
    finally:
        if os.path.exists(data.get('excel_path', '')): os.remove(data.get('excel_path'))
        await state.clear()

async def main():
    status.success("✅ Бот запущен! Пиши /start в Telegram.")
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    asyncio.run(main())
