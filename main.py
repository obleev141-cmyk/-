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
from thefuzz import process # Для нечеткого поиска фамилий

# --- ИНТЕРФЕЙС ---
st.title("📅 Бот-График: Умный поиск")

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
    await message.answer("👋 Привет! Пришли фото графика. Я постараюсь распознать фамилии, даже если фото не очень четкое.")
    await state.set_state(Form.waiting_for_data)

@dp.message(Form.waiting_for_data, F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    file_path = f"img_{photo.file_id}.jpg"
    await bot.download_file((await bot.get_file(photo.file_id)).file_path, file_path)
    
    msg = await message.answer("🔍 Читаю фамилии на фото...")
    
    # Распознаем текст
    results = reader.readtext(file_path, detail=0)
    
    # Пытаемся собрать данные. Если это фото, мы просто берем все найденные слова
    # и превращаем их в длинный список для поиска.
    df_temp = pd.DataFrame({'text': results})
    
    excel_path = f"temp_{message.from_user.id}.xlsx"
    df_temp.to_excel(excel_path, index=False)
    
    await state.update_data(file_path=excel_path, raw_text=results)
    os.remove(file_path)
    await msg.edit_text("✅ Текст считан! Введи фамилию для поиска.")
    await state.set_state(Form.waiting_for_name)

@dp.message(Form.waiting_for_name)
async def handle_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_path = data.get('file_path')
    raw_text = data.get('raw_text', [])
    search_name = message.text.strip()

    try:
        # НЕЧЕТКИЙ ПОИСК: ищем самое похожее слово среди распознанных
        # score_cutoff=60 означает, что совпадение должно быть минимум на 60%
        best_match = process.extractOne(search_name, raw_text, score_cutoff=60)

        if not best_match:
            await message.answer(f"❌ Не удалось найти фамилию '{search_name}' на фото. Попробуй сфотографировать четче или напиши фамилию иначе.")
        else:
            found_name = best_match[0]
            await message.answer(f"🔎 Нашел похожее на фото: **{found_name}** (совпадение {best_match[1]}%)")
            
            # Далее идет твоя логика отрисовки календаря
            # Для фото-режима мы просто выведем ближайшие 10 слов после фамилии как смены
            idx = raw_text.index(found_name)
            schedule = raw_text[idx+1 : idx+32] # Берем следующие 31 слово как дни
            
            # Компактная отрисовка (упрощенная для фото)
            img = Image.new('RGB', (800, 600), color='#1C1E21')
            draw = ImageDraw.Draw(img)
            draw.text((20, 20), f"ГРАФИК: {found_name.upper()}", fill='#FFFFFF')
            
            y = 80
            x = 20
            for i, day_val in enumerate(schedule):
                is_work = any(char.isdigit() for char in day_val)
                color = "#FF7043" if is_work else "#4CAF50"
                
                draw.rectangle([x, y, x+100, y+40], fill=color)
                draw.text((x+5, y+10), f"{i+1}: {day_val[:8]}", fill='#FFFFFF')
                
                x += 110
                if (i+1) % 7 == 0:
                    x = 20
                    y += 50
            
            img_path = f"res_{message.from_user.id}.png"
            img.save(img_path)
            await message.answer_photo(types.FSInputFile(img_path))
            os.remove(img_path)

    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {e}")
    finally:
        if file_path and os.path.exists(file_path): os.remove(file_path)
        await state.clear()

async def main():
    await dp.start_polling(bot, handle_signals=False)

if __name__ == "__main__":
    asyncio.run(main())
