import os
import asyncio
import streamlit as st
import pandas as pd
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from PIL import Image, ImageDraw

# --- ИНТЕРФЕЙС ---
st.title("🤖 Бот-График: СТАТУС OK")
st.success("Бот активен. Теперь он понимает выходные!")

API_TOKEN = "8646138607:AAEkoT_Jj_zixGYTti_r1fIjQOKH5_H45-U"
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    waiting_for_file = State()
    waiting_for_name = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Пришли Excel-файл с графиком, и я сделаю удобную картинку.")
    await state.set_state(Form.waiting_for_file)

@dp.message(Form.waiting_for_file, F.document)
async def handle_document(message: types.Message, state: FSMContext):
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_name = f"{file_id}.xlsx"
    await bot.download_file(file.file_path, file_name)
    await state.update_data(file_path=file_name)
    await message.answer("✅ Файл загружен! Теперь напиши фамилию.")
    await state.set_state(Form.waiting_for_name)

@dp.message(Form.waiting_for_name)
async def handle_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_path = data.get('file_path')
    name = message.text.strip()

    try:
        # Читаем файл и ищем строку с заголовками
        df_raw = pd.read_excel(file_path, header=None)
        header_idx = df_raw.count(axis=1).idxmax()
        df = df_raw.copy()
        df.columns = df.iloc[header_idx]
        df = df.drop(range(header_idx + 1)).reset_index(drop=True)
        
        col_fio = df.columns[0]
        result = df[df[col_fio].astype(str).str.contains(name, case=False, na=False)]

        if result.empty:
            await message.answer(f"❌ Работник '{name}' не найден.")
        else:
            row = result.iloc[0]
            
            # Отбираем только колонки с датами (где есть названия)
            valid_cols = [c for c in df.columns if pd.notna(c) and str(c).strip() != ""]
            
            # Настройки картинки
            width = 750
            height = 140 + (len(valid_cols) * 45)
            img = Image.new('RGB', (width, height), color='#121212') # Глубокий черный
            draw = ImageDraw.Draw(img)
            
            # Заголовок
            draw.text((50, 40), f"ГРАФИК: {str(row[col_fio]).upper()}", fill='#00E676')
            draw.line((50, 90, 700, 90), fill='#333333', width=1)
            
            y = 120
            for col in valid_cols[1:]: # Пропускаем колонку ФИО
                val = str(row[col]).strip()
                
                # ЛОГИКА ВЫХОДНЫХ: если пусто, NaN или прочерк
                if not val or val.lower() in ['nan', '-', 'none', '']:
                    display_text = "ВЫХОДНОЙ"
                    text_color = "#FF5252" # Красный для выходного
                else:
                    display_text = val
                    text_color = "#FFFFFF" # Белый для рабочих смен
                
                # Рисуем дату (слева) и статус (справа)
                draw.text((50, y), f"{col}:", fill='#9E9E9E')
                draw.text((250, y), display_text, fill=text_color)
                y += 40
            
            img_path = f"res_{message.from_user.id}.png"
            img.save(img_path)
            await message.answer_photo(types.FSInputFile(img_path), caption=f"Готово! Пустые дни отмечены как выходные.")
            if os.path.exists(img_path): os.remove(img_path)

    except Exception as e:
        await message.answer(f"⚠️ Ошибка обработки: {e}")
    finally:
        if file_path and os.path.exists(file_path): os.remove(file_path)
        await state.clear()

async def main():
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    asyncio.run(main())
