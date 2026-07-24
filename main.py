import asyncio
import json
import requests


from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

bot = Bot('8844988250:AAEb_YjI_3JaTkyPE0cYaVYCdPTE_u8-xek')
API = "82744bb012d54bc69cb163431262307"


dp = Dispatcher()

waiting_weather = {}

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(f"Привет, {message.from_user.first_name}!")


# /weather
@dp.message(Command("weather"))
async def weather(message: Message):
    waiting_weather[message.chat.id] = True

    await message.answer(
        "Напиши название города.")

# текстовые сообщения
@dp.message(F.text)
async def text_messages(message: Message):

    text = message.text.lower().strip()

    if text == "привет":
        await message.answer(
            f"Привет, {message.from_user.first_name}!" )
        return

    elif text == "id":
        await message.answer(
            f"ID: {message.from_user.id}")
        return

    elif text in ["ты кто", "ты кто?"]:
        await message.answer( "Я цифровой житель Telegram. Работаю без выходных. Спрашивай, если надо ;)")
        return

    elif text == "бомгю":
        await message.answer("Бомгю? Из TXT? Хороший выбор! ;)" )
        return

    elif text == "тхт":
        await message.answer("Tomorrow X Together (TXT) — южнокорейская группа из пяти участников: Ёнджун, Субин, Бомгю, Тэхён и Хюнинкай.")
        return

    elif text in ["как дела", "как дела?"]:
        await message.answer( "У меня всё хорошо!"  )
        return

    elif text in ["что ты умеешь", "что ты умеешь?"]:
        await message.answer( "Я умею показывать погоду /weather и отвечать на некоторые сообщения.")
        return

    elif text == "погода":
        await message.answer("Напиши /weather")
        return
    elif text == "таллинн":
        await message.answer("Напиши с одной н, метеослужбы не хотят работать" )
        return

    # погода

    if waiting_weather.get(message.chat.id):
        city = text
        res = requests.get(
            f"https://api.weatherapi.com/v1/current.json?key={API}&q={city}&lang=ru" )

        if res.status_code == 200:
            data = res.json()
            temp = data["current"]["temp_c"]
            await message.answer(f"Погода сейчас: {temp}°C" )
        else:
            await message.answer("Город не найден. Попробуй написать другой." )

# Фото
@dp.message(F.photo)
async def photo(message: Message):

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                    text="Удалить фото",
                    callback_data="delete"  )]])
    await message.answer("Имба!",reply_markup=keyboard )

# Удаление фото
@dp.callback_query(F.data == "delete")
async def delete_photo(callback: CallbackQuery):
    await bot.delete_message( callback.message.chat.id,callback.message.message_id - 1 )
    await callback.answer()


# /help
@dp.message(Command("help"))
async def help_command(message: Message):

    await message.answer(
        "Команды:\n"
        "/start - запуск\n"
        "/weather - погода\n"
        "/help - помощь")

async def main():
    await dp.start_polling(
        bot,
        handle_signals=False
    )


if __name__ == "__main__":
    asyncio.run(main())