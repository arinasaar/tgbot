import random
import asyncio
import requests
import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery


bot = Bot('8844988250:AAEb_YjI_3JaTkyPE0cYaVYCdPTE_u8-xek')
API = "82744bb012d54bc69cb163431262307"
TMDB_API = "d4b7b76e9645c6c06a74c731449c6361"

dp = Dispatcher()

waiting_weather = {}

MOVIE_GENRES = {
    28: "Боевик",
    12: "Приключения",
    16: "Мультфильм",
    35: "Комедия",
    80: "Криминал",
    99: "Документальный",
    18: "Драма",
    10751: "Семейный",
    14: "Фэнтези",
    27: "Ужасы",
    9648: "Детектив",
    10749: "Мелодрама",
    878: "Фантастика",
    53: "Триллер",
}

# Страны для "дорамы" — не только Корея, но и другие азиатские сериалы
DRAMA_COUNTRIES = ["KR", "JP", "CN", "TW", "TH"]

KURYANA_BASE = "https://kuryana.tbdh.app"  # неофициальный API-скрейпер MyDramaList


async def get_mdl_info(session: aiohttp.ClientSession, title: str) -> dict | None:
  
    try:
        async with session.get(
                f"{KURYANA_BASE}/search/q/{title}",
                timeout=aiohttp.ClientTimeout(total=5)
        ) as res:
            if res.status != 200:
                return None
            search_data = await res.json()

        dramas = search_data.get("results", {}).get("dramas", [])
        if not dramas:
            return None

        slug = dramas[0].get("slug")
        if not slug:
            return None

        async with session.get(
                f"{KURYANA_BASE}/id/{slug}",
                timeout=aiohttp.ClientTimeout(total=5)
        ) as res:
            if res.status != 200:
                return None
            details = await res.json()

        synopsis = details.get("synopsis")
        mdl_rating = details.get("rating")
        if not synopsis:
            return None

        return {"synopsis": synopsis, "rating": mdl_rating}

    except Exception:
        return None


async def translate_to_ru(session: aiohttp.ClientSession, text: str) -> str:
    """Переводит английский текст на русский через бесплатный MyMemory API.
    Если перевод не удался — возвращает исходный текст."""
    if not text:
        return text

    try:
        async with session.get(
                "https://api.mymemory.translated.net/get",
                params={"q": text[:500], "langpair": "en|ru"}
        ) as res:
            if res.status == 200:
                data = await res.json()
                translated = data.get("responseData", {}).get("translatedText")
                if translated:
                    return translated
    except Exception:
        pass

    return text


# Жанры сериалов (эндпоинт discover/tv) — используются и для дорам,
# только с доп. фильтром by origin_country
TV_GENRES = {
    10759: "Боевик и приключения",
    16: "Мультфильм",
    35: "Комедия",
    80: "Криминал",
    99: "Документальный",
    18: "Драма",
    10751: "Семейный",
    9648: "Детектив",
    10765: "Фантастика и фэнтези",
    10766: "Мелодрама",
}


# /start
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(f"Привет, {message.from_user.first_name}! Рад тебя видеть!")


# /weather
@dp.message(Command("weather"))
async def weather(message: Message):
    waiting_weather[message.chat.id] = True
    await message.answer("Напиши название города.")


# /help
@dp.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "Команды:\n"
        "/start - запуск\n"
        "/weather - погода\n"
        "/help - помощь\n"
        "/movie - фильмы, сериалы, дорамы"
    )


def type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Фильм",
                    callback_data="type_movie")
            ],
            [
                InlineKeyboardButton(
                    text="Сериал",
                    callback_data="type_tv")
            ],
            [
                InlineKeyboardButton(
                    text="🇰🇷 Дорама",
                    callback_data="type_kdrama")
            ]
        ]
    )


@dp.message(Command("movie"))
async def movie(message: Message):
    await message.answer(
        "Что хотите посмотреть?",
        reply_markup=type_keyboard()
    )


def genres_keyboard(content_type: str) -> InlineKeyboardMarkup:
    genres = MOVIE_GENRES if content_type == "movie" else TV_GENRES

    buttons = []
    row = []
    for genre_id, name in genres.items():
        row.append(
            InlineKeyboardButton(
                text=name,
                callback_data=f"genre_{content_type}_{genre_id}"
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton(text="🏠 В начало", callback_data="restart")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Выбор типа (фильм/сериал/дорама) -> показываем жанры
@dp.callback_query(F.data.startswith("type_"))
async def choose_type(callback: CallbackQuery):
    content_type = callback.data.split("_", 1)[1]  # movie / tv / kdrama

    await callback.message.edit_text(
        "Выберите жанр:",
        reply_markup=genres_keyboard(content_type)
    )
    await callback.answer()


# Выбор жанра -> случайный тайтл с TMDB
@dp.callback_query(F.data.startswith("genre_"))
async def choose_genre(callback: CallbackQuery):
    _, content_type, genre_id = callback.data.split("_", 2)

    # У дорам нет своего типа в TMDB — это сериалы (tv) с origin_country
    tmdb_type = "movie" if content_type == "movie" else "tv"

    params = {
        "api_key": TMDB_API,
        "with_genres": genre_id,
        "sort_by": "popularity.desc",
        "language": "en-US",  # у TMDB описание почти всегда заполнено на английском,
        # в отличие от ru-RU — иначе фильтр по overview всё вырезает
        "page": random.randint(1, 5),
        "include_adult": "false",
    }
    if content_type == "kdrama":
        params["with_origin_country"] = random.choice(DRAMA_COUNTRIES)

    await callback.answer("Ищу...")

    timeout = aiohttp.ClientTimeout(total=10)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(
                f"https://api.themoviedb.org/3/discover/{tmdb_type}",
                params=params
        ) as res:
            if res.status != 200:
                await callback.message.answer("❌ Не удалось получить данные от TMDB")
                return
            data = await res.json()

        results = [r for r in data.get("results", []) if r.get("overview")]

        # если на случайной странице ничего подходящего не нашлось — пробуем 1-ю страницу
        if not results and params["page"] != 1:
            params["page"] = 1
            async with session.get(
                    f"https://api.themoviedb.org/3/discover/{tmdb_type}",
                    params=params
            ) as res:
                if res.status == 200:
                    data = await res.json()
                    results = [r for r in data.get("results", []) if r.get("overview")]

        if not results:
            await callback.message.answer("Ничего не нашлось 😔 Попробуйте другой жанр.")
            return

        item = random.choice(results)
        title = item.get("title") or item.get("name") or "Без названия"
        rating = item.get("vote_average", 0)
        poster_path = item.get("poster_path")

        rating_label = "TMDB"
        overview_source = item.get("overview")[:500]

        # Для дорам пробуем подтянуть более точный синопсис и рейтинг с MyDramaList
        if content_type == "kdrama":
            mdl_info = await get_mdl_info(session, title)
            if mdl_info:
                overview_source = mdl_info["synopsis"][:500]
                if mdl_info.get("rating"):
                    rating = mdl_info["rating"]
                    rating_label = "MDL"

        overview = await translate_to_ru(session, overview_source)

    caption = f"🎬 {title}\n⭐ {rating}/10 ({rating_label})\n\n{overview}"

    again_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔁 Выбрать другой",
                    callback_data=callback.data  # тот же genre_{type}_{id}
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ К жанрам",
                    callback_data=f"back_{content_type}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 В начало",
                    callback_data="restart"
                )
            ]
        ]
    )

    if poster_path:
        await callback.message.answer_photo(
            photo=f"https://image.tmdb.org/t/p/w500{poster_path}",
            caption=caption,
            reply_markup=again_keyboard
        )
    else:
        await callback.message.answer(caption, reply_markup=again_keyboard)


# Возврат к выбору типа контента (кнопка "🏠 В начало")
@dp.callback_query(F.data == "restart")
async def restart_selection(callback: CallbackQuery):
    await callback.message.answer(
        "Что хотите посмотреть?",
        reply_markup=type_keyboard()
    )
    await callback.answer()


# Возврат к выбору жанра из-под результата (кнопка "⬅️ К жанрам")
@dp.callback_query(F.data.startswith("back_"))
async def back_to_genres(callback: CallbackQuery):
    content_type = callback.data.split("_", 1)[1]

    await callback.message.answer(
        "Выберите жанр:",
        reply_markup=genres_keyboard(content_type)
    )
    await callback.answer()


# Единственный обработчик текстовых сообщений
@dp.message(F.text)
async def text_messages(message: Message):
    text = message.text.lower().strip()

    # Проверка погоды — идёт первой, т.к. это "режим ожидания"
    if waiting_weather.get(message.chat.id):

        city = text
        waiting_weather[message.chat.id] = False

        async with aiohttp.ClientSession() as session:
            async with session.get(
                    "https://api.weatherapi.com/v1/current.json",
                    params={"key": API, "q": city, "lang": "ru"}
            ) as res:

                if res.status == 200:
                    data = await res.json()

                    temp = data["current"]["temp_c"]
                    condition = data["current"]["condition"]["text"]

                    await message.answer(
                        f"🌡 Температура: {temp}°C\n"
                        f"☁️ {condition}"
                    )
                else:
                    await message.answer("❌Город не найден. Напиши еще раз /weather")

        return

    # Обычные ключевые слова
    if text == "привет":
        await message.answer(f"Привет, {message.from_user.first_name}!")

    elif text == "id":
        await message.answer(f"ID: {message.from_user.id}")

    elif text in ["ты кто", "ты кто?"]:
        await message.answer("Я цифровой житель Telegram. Работаю без выходных.")

    elif text == "бомгю":
        await message.answer("Бомгю? Из TXT? Хороший выбор! ;)")

    elif text == "тхт":
        await message.answer("Tomorrow X Together (TXT) — южнокорейская группа из пяти участников.")

    elif text in ["как дела", "как дела?"]:
        await message.answer("У меня всё хорошо!")

    elif text in ["что ты умеешь", "что ты умеешь?"]:
        await message.answer("Я умею показывать погоду /weather и отвечать на сообщения.")

    elif text == "погода":
        await message.answer("Напиши /weather")

    elif text == "таллинн":
        await message.answer("Напиши с одной н, метеослужбы не хотят работать")

    elif text == "помощь":
        await message.answer(
            "Команды:\n"
            "/start - запуск\n"
            "/weather - погода\n"
            "/help - помощь\n"
            "/movie - фильмы, сериалы, дорамы"
        )

    elif text in ["фильм", "посоветуй фильм", "посоветуй дораму", "посоветуй сериал", "я не знаю что посмотреть", "я не знаю, что посмотреть"]:
        await message.answer("Напиши /movie и найди себе подходящее😉")

    elif text in ["спасибо", "ура", "благодарю", "спасибо тебе", "молодец"]:
        await message.answer("Рад помочь😊")

    else:
        await message.answer("Не понимаю🤔. Скорее всего мой код еще не позволяет распознать твое сообщение.")


# Фото
@dp.message(F.photo)
async def photo(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Удалить фото",
                    callback_data="delete"
                )
            ]
        ]
    )

    await message.answer(
        "Имба!",
        reply_markup=keyboard
    )


# Удаление фото
@dp.callback_query(F.data == "delete")
async def delete_photo(callback: CallbackQuery):
    await bot.delete_message(
        callback.message.chat.id,
        callback.message.message_id - 1
    )

    await callback.answer()


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

