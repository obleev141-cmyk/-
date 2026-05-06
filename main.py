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
st.title("📅 Бот-Календарь v2.0")
st.success("Статус: Оптимизирован")

API_TOKEN = "8646138607:AAEkoT_Jj_zixGYTti_r1fIjQOKH5_H45-U"
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    waiting_for_file = State()
    waiting_for_name = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Пришли файл Excel, и я нарисую компактный календарь.")
    await state.set_state(Form.waiting_for_file)

@dp.message(Form.waiting_for_file, F.document)
async def handle_document(message: types.Message, state: FSMContext):
    file_id = message.document.file_id
    file_path = f"{file_id}.xlsx"
    await bot.download_file((await bot.get_file(file_id)).file_path, file_path)
    await state.update_data(file_path=file_path)
    await message.answer("✅ Файл загружен. Введи фамилию сотрудника.")
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
            # Берем только колонки, похожие на даты
            dates = [c for c in df.columns if any(char.isdigit() for char in str(c))][:31]
            
            # РАЗМЕРЫ (Компактный вид)
            cell_w, cell_h = 90, 80
            padding = 15
            img_w = (cell_w * 7) + (padding * 2)
            img_h = (cell_h * 6) + 120
            
            img = Image.new('RGB', (img_w, img_h), color='#1C1E21')
            draw = ImageDraw.Draw(img)
            
            # Шапка
            draw.text((padding, 20), f"{name.upper()}", fill='#FFFFFF')
            draw.text((padding, 50), "МАЙ 2026", fill='#9DA0A5')
            
            # Дни недели
            days = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
            for i, d in enumerate(days):
                draw.text((padding + i*cell_w + 30, 85), d, fill='#5E6166')

            # Сетка
            for i, date_col in enumerate(dates):
                r, c = i // 7, i % 7
                x = padding + c * cell_w
                y = 120 + r * cell_h
                
                # Число (день месяца)
                day_num = str(date_col).split('.')[0].split(' ')[0]
                draw.text((x + 10, y + 5), day_num, fill='#FFFFFF')
                
                val = str(row[date_col]).strip().lower()
                is_work = val and val not in ['nan', '-', '', 'выходной']
                
                # Цвет плашки: Оранжевый - работа, Зеленый - выходной
                rect_color = "#FF7043" if is_work else "#4CAF50"
                draw.rounded_rectangle([x+5, y+30, x+85, y+65], radius=6, fill=rect_color)
                
                # Текст внутри плашки
                display_val = str(row[date_col]) if is_work else "ВЫХ"
                # Обрезаем длинные смены для компактности
                if len(display_val) > 8: display_val = display_val[:7] + ".."
                draw.text((x+15, y+38), display_val, fill='#FFFFFF')
            
            img_path = f"compact_{message.from_user.id}.png"
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
