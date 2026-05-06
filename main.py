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
st.set_page_config(page_title="Бот-График")
st.title("📅 Календарь из Excel")
st.success("Стабильная версия запущена!")

API_TOKEN = "8646138607:AAEkoT_Jj_zixGYTti_r1fIjQOKH5_H45-U"
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    waiting_for_file = State()
    waiting_for_name = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Пришли Excel-файл с графиком.")
    await state.set_state(Form.waiting_for_file)

@dp.message(Form.waiting_for_file, F.document)
async def handle_document(message: types.Message, state: FSMContext):
    file_id = message.document.file_id
    file_path = f"{file_id}.xlsx"
    await bot.download_file((await bot.get_file(file_id)).file_path, file_path)
    await state.update_data(file_path=file_path)
    await message.answer("✅ Файл получен. Напиши фамилию сотрудника.")
    await state.set_state(Form.waiting_for_name)

@dp.message(Form.waiting_for_name)
async def handle_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_path = data.get('file_path')
    name = message.text.strip()

    try:
        # Читаем Excel и ищем строку заголовка (где даты)
        df_raw = pd.read_excel(file_path, header=None)
        header_idx = df_raw.count(axis=1).idxmax()
        df = df_raw.iloc[header_idx:].copy()
        df.columns = df.iloc[0]
        df = df[1:].reset_index(drop=True)
        
        col_fio = df.columns[0]
        result = df[df[col_fio].astype(str).str.contains(name, case=False, na=False)]

        if result.empty:
            await message.answer(f"❌ '{name}' не найден в списке.")
        else:
            row = result.iloc[0]
            # Отбираем колонки, которые похожи на даты (1, 2, 3...)
            dates = [c for c in df.columns if any(char.isdigit() for char in str(c))][:31]
            
            # РИСУЕМ КОМПАКТНЫЙ КАЛЕНДАРЬ
            cell_w, cell_h = 90, 80
            padding = 20
            img = Image.new('RGB', (cell_w*7 + padding*2, cell_h*6 + 120), color='#1C1E21')
            draw = ImageDraw.Draw(img)
            
            draw.text((padding, 30), f"СОТРУДНИК: {str(row[col_fio]).upper()}", fill='#FFFFFF')
            draw.text((padding, 60), "ГРАФИК НА МЕСЯЦ (МАЙ)", fill='#9DA0A5')

            # Сетка дат
            for i, date_col in enumerate(dates):
                r, c = i // 7, i % 7
                x, y = padding + c*cell_w, 120 + r*cell_h
                
                val = str(row[date_col]).strip()
                # Логика: если ячейка пустая/прочерк — выходной
                is_work = val and val.lower() not in ['nan', '-', '', 'в', 'выходной']
                
                color = "#FF7043" if is_work else "#4CAF50" # Оранжевый/Зеленый
                draw.rounded_rectangle([x+5, y+30, x+85, y+65], radius=8, fill=color)
                
                # Число и текст смены
                draw.text((x+10, y+5), str(date_col).split('.')[0], fill='#FFFFFF')
                display_text = val if is_work else "ВЫХ"
                draw.text((x+15, y+38), display_text[:7], fill='#FFFFFF')

            img_path = f"res_{message.from_user.id}.png"
            img.save(img_path)
            await message.answer_photo(types.FSInputFile(img_path))
            if os.path.exists(img_path): os.remove(img_path)

    except Exception as e:
        await message.answer(f"⚠️ Ошибка файла: {e}")
    finally:
        if file_path and os.path.exists(file_path): os.remove(file_path)
        await state.clear()

async def main():
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    asyncio.run(main())
