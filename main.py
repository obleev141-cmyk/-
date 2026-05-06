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

# --- ИНТЕРФЕЙС STREAMLIT ---
st.title("📅 Бот-График: Фото + Excel")
st.success("Статус: Работает")

API_TOKEN = "8646138607:AAEkoT_Jj_zixGYTti_r1fIjQOKH5_H45-U"
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Инициализация OCR (сканера)
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['ru', 'en'])

reader = load_ocr()

class Form(StatesGroup):
    waiting_for_data = State()
    waiting_for_name = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Пришли **фото графика** или **Excel-файл**.")
    await state.set_state(Form.waiting_for_data)

# ОБРАБОТКА ФОТО (OCR)
@dp.message(Form.waiting_for_data, F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    file_path = f"img_{photo.file_id}.jpg"
    await bot.download_file((await bot.get_file(photo.file_id)).file_path, file_path)
    
    msg = await message.answer("🔍 Сканирую фото... (первый раз может занять минуту)")
    
    # Распознаем текст и пытаемся создать таблицу
    results = reader.readtext(file_path, detail=0)
    df_temp = pd.DataFrame([results]) # Упрощенная сборка
    
    excel_path = f"temp_{message.from_user.id}.xlsx"
    df_temp.to_excel(excel_path, index=False)
    
    await state.update_data(file_path=excel_path)
    os.remove(file_path)
    await msg.edit_text("✅ Фото распознано! Введи фамилию.")
    await state.set_state(Form.waiting_for_name)

# ОБРАБОТКА EXCEL
@dp.message(Form.waiting_for_data, F.document)
async def handle_document(message: types.Message, state: FSMContext):
    file_id = message.document.file_id
    file_path = f"{file_id}.xlsx"
    await bot.download_file((await bot.get_file(file_id)).file_path, file_path)
    await state.update_data(file_path=file_path)
    await message.answer("✅ Файл принят. Введи фамилию.")
    await state.set_state(Form.waiting_for_name)

@dp.message(Form.waiting_for_name)
async def handle_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_path = data.get('file_path')
    name = message.text.strip()

    try:
        df_raw = pd.read_excel(file_path, header=None)
        header_idx = df_raw.count(axis=1).idxmax()
        df = df_raw.iloc[header_idx:].copy()
        df.columns = df.iloc[0]
        df = df[1:].reset_index(drop=True)
        
        col_fio = df.columns[0]
        result = df[df[col_fio].astype(str).str.contains(name, case=False, na=False)]

        if result.empty:
            await message.answer(f"❌ '{name}' не найден.")
        else:
            row = result.iloc[0]
            dates = [c for c in df.columns if any(char.isdigit() for char in str(c))][:31]
            
            # РАЗМЕРЫ
            cell_w, cell_h = 90, 80
            padding = 15
            img = Image.new('RGB', (cell_w*7 + padding*2, cell_h*6 + 120), color='#1C1E21')
            draw = ImageDraw.Draw(img)
            
            draw.text((padding, 20), f"{name.upper()}", fill='#FFFFFF')
            draw.text((padding, 50), "ГРАФИК НА МЕСЯЦ", fill='#9DA0A5')
            
            days = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
            for i, d in enumerate(days):
                draw.text((padding + i*cell_w + 30, 85), d, fill='#5E6166')

            for i, date_col in enumerate(dates):
                r, c = i // 7, i % 7
                x, y = padding + c*cell_w, 120 + r*cell_h
                
                day_num = str(date_col).split('.')[0].split(' ')[0]
                draw.text((x + 10, y + 5), day_num, fill='#FFFFFF')
                
                val = str(row[date_col]).strip().lower()
                # Если ячейка не пустая и не "выходной" — это работа
                is_work = val and val not in ['nan', '-', '', 'выходной', 'в']
                
                rect_color = "#FF7043" if is_work else "#4CAF50" # Оранж - работа, Зеленый - вых
                draw.rounded_rectangle([x+5, y+30, x+85, y+65], radius=6, fill=rect_color)
                
                display_val = str(row[date_col]) if is_work else "ВЫХ"
                if len(display_val) > 8: display_val = display_val[:7] + ".."
                draw.text((x+15, y+38), display_val, fill='#FFFFFF')
            
            img_path = f"res_{message.from_user.id}.png"
            img.save(img_path)
            await message.answer_photo(types.FSInputFile(img_path))
            if os.path.exists(img_path): os.remove(img_path)

    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}")
    finally:
        if file_path and os.path.exists(file_path): os.remove(file_path)
        await state.clear()

async def main():
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    asyncio.run(main())
