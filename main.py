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
st.title("🤖 Бот-Календарь")
st.info("Статус: Ожидание файла...")

# Настройки
API_TOKEN = "8646138607:AAEkoT_Jj_zixGYTti_r1fIjQOKH5_H45-U"
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    waiting_for_file = State()
    waiting_for_name = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Пришли файл с графиком, и я нарисую календарь.")
    await state.set_state(Form.waiting_for_file)

@dp.message(Form.waiting_for_file, F.document)
async def handle_document(message: types.Message, state: FSMContext):
    file_id = message.document.file_id
    file_name = f"{file_id}.xlsx"
    await bot.download_file((await bot.get_file(file_id)).file_path, file_name)
    await state.update_data(file_path=file_name)
    await message.answer("✅ Файл принят. Напиши фамилию.")
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
            await message.answer("❌ Сотрудник не найден.")
        else:
            row = result.iloc[0]
            dates = [c for c in df.columns if str(c).replace('.','').isdigit() or "май" in str(c).lower()]
            
            # РИСУЕМ КАЛЕНДАРЬ (стиль "Моя работа")
            cell_size = 100
            padding = 20
            cols_count = 7
            rows_count = (len(dates) // 7) + 1
            
            img_w = (cell_size * cols_count) + (padding * 2)
            img_h = (cell_size * rows_count) + 150
            
            img = Image.new('RGB', (img_w, img_h), color='#1C1E21')
            draw = ImageDraw.Draw(img)
            
            # Заголовок (Май 2026)
            draw.text((padding, 30), f"{name.upper()}", fill='#FFFFFF')
            draw.text((padding, 70), "МАЙ 2026", fill='#9DA0A5')
            
            # Дни недели
            weekdays = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
            for i, day in enumerate(weekdays):
                draw.text((padding + i*cell_size + 30, 110), day, fill='#5E6166')

            # Сетка дат
            for i, date_col in enumerate(dates):
                row_idx = i // 7
                col_idx = i % 7
                x = padding + col_idx * cell_size
                y = 150 + row_idx * cell_size
                
                # Число
                draw.text((x + 10, y + 10), str(date_col).split('.')[0], fill='#FFFFFF')
                
                # Смена (если есть)
                val = str(row[date_col]).strip()
                if val and val.lower() not in ['nan', '-', '']:
                    # Рисуем цветную плашку для смены
                    color = "#4CAF50" if "12" in val or "11" in val else "#FF7043"
                    draw.rounded_rectangle([x+10, y+40, x+90, y+70], radius=5, fill=color)
                    draw.text((x+20, y+45), val, fill='#FFFFFF')
            
            img_path = f"cal_{message.from_user.id}.png"
            img.save(img_path)
            await message.answer_photo(types.FSInputFile(img_path))
            if os.path.exists(img_path): os.remove(img_path)

    except Exception as e:
        await message.answer(f"Ошибка: {e}")
    finally:
        if file_path and os.path.exists(file_path): os.remove(file_path)
        await state.clear()

async def main():
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    asyncio.run(main())
