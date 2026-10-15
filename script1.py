import telebot
from telebot import types
from geopy.distance import geodesic
import json
import os

# =====================================================================
# НАСТРОЙКИ БОТА И ДАННЫЕ
# =====================================================================

TOKEN = os.environ.get('BOT_TOKEN', '8956979903:AAFHWgRkxUhln-V-p8O-xKNkmLVY2PkO9N0')
bot = telebot.TeleBot(TOKEN)

user_states = {}

def load_places():
    filename = 'places.json'
    if not os.path.exists(filename):
        return []
    with open(filename, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

# Функция генерации нижней стационарной клавиатуры главного меню
def get_main_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    btn1 = types.KeyboardButton("🌯 Шаурма и фастфуд")
    btn2 = types.KeyboardButton("🥞 Домашние столовые")
    btn3 = types.KeyboardButton("☕ Бюджетный кофе")
    btn4 = types.KeyboardButton("🌭 Хот-доги")
    btn5 = types.KeyboardButton("🍔 Бургеры")
    btn6 = types.KeyboardButton("🧋 Бабл-ти")
    btn7 = types.KeyboardButton("🥐 Пекарни")
    btn8 = types.KeyboardButton("🍽 Показать всё подряд")

    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)
    return markup

# Техническая карта соответствия текста кнопок и тегов категорий в places.json
CATEGORY_MAP = {
    "🌯 Шаурма и фастфуд": "sharma",
    "🥞 Домашние столовые": "canteen",
    "☕ Бюджетный кофе": "coffee",
    "🌭 Хот-доги": "hotdog",
    "🍔 Бургеры": "burgers",
    "🧋 Бабл-ти": "bubble",
    "🥐 Пекарни": "bakery",
    "🍽 Показать всё подряд": "all"
}

# Текст приветственного сообщения
INTRO_TEXT = (
    "🤖 *Приветствуем в навигационном ИТ-проекте «Студенческий Фастфуд»!*\n\n"
    "Данный чат-бот разработан специально для студентов и сотрудников учебных заведений. "
    "Его главная цель — автоматизировать и ускорить поиск мест общественного питания вокруг кампуса, "
    "оптимизируя время перерыва между учебными занятиями.\n\n"
    "💡 *Что я умею:*\n"
    "1. Классифицировать заведения по 7 категориям.\n"
    "2. Принимать вашу текущую геолокацию со смартфона.\n"
    "3. Рассчитывать точное пешеходное расстояние в метрах до ближайшего пирожка.\n"
    "4. Прокладывать готовые пешеходные маршруты прямо внутри приложений Яндекс.Карты и 2ГИС.\n\n"
    "--------------------------------------\n"
    "👇 *Давайте начнем! Выберите интересующую категорию на клавиатуре внизу:* "
)

# =====================================================================
# ЛОГИКА ТЕЛЕГРАМ-БОТА
# =====================================================================

# Обработка команды /start и кнопки сброса/возврата к началу
@bot.message_handler(commands=['start'])
def start_message(message):
    photo_path = 'logo.jpg'
    markup = get_main_menu_keyboard()

    if os.path.exists(photo_path):
        with open(photo_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=INTRO_TEXT, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, INTRO_TEXT, parse_mode="Markdown", reply_markup=markup)

# Универсальная обработка кнопки "⬅️ Назад в меню" во всех текстовых сценариях
@bot.message_handler(func=lambda message: message.text == "⬅️ Назад в меню")
def handle_back_button(message):
    markup = get_main_menu_keyboard()
    bot.send_message(
        message.chat.id,
        "Возвращаемся в главное меню. 👇 *Выберите интересующую категорию еды:*",
        parse_mode="Markdown",
        reply_markup=markup
    )

# Обработка выбора категории через нижнюю текстовую клавиатуру
@bot.message_handler(func=lambda message: message.text in CATEGORY_MAP.keys())
def handle_category_selection(message):
    chat_id = message.chat.id
    text_button = message.text

    user_states[chat_id] = CATEGORY_MAP[text_button]

    # Кнопки нижнего меню на этапе ожидания геолокации
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    btn_loc = types.KeyboardButton("📍 Отправить геолокацию", request_location=True)
    btn_back = types.KeyboardButton("⬅️ Назад в меню")
    markup.add(btn_loc, btn_back)

    bot.send_message(
        chat_id,
        f"Выбрана категория: *{text_button}*\n\n"
        "Теперь нажмите появившуюся кнопку *«📍 Отправить геолокацию»*, чтобы бот рассчитал расстояние.\n"
        "Если вы хотите изменить выбор, нажмите кнопку *«⬅️ Назад в меню»*.",
        parse_mode="Markdown",
        reply_markup=markup
    )

# Обработка полученной геолокации (Вычисление расстояний и генерация активных ссылок)
@bot.message_handler(content_types=['location'])
def handle_location(message):
    chat_id = message.chat.id
    user_lat = message.location.latitude
    user_lon = message.location.longitude
    user_coords = (user_lat, user_lon)

    selected_category = user_states.get(chat_id, 'all')
    places = load_places()

    response = "Вот что нашлось рядом с тобой:\n\n"
    found_any = False

    for place in places:
        place_cats = place['category']
        if isinstance(place_cats, str):
            place_cats = [place_cats]

        if selected_category != 'all' and selected_category not in place_cats:
            continue

        place_coords = (place["lat"], place["lon"])
        distance = round(geodesic(user_coords, place_coords).meters)

        # Радиус поиска — 1500 метров
        if distance < 1500:
            found_any = True
            response += f"📌 *{place['name']}* (в {distance} метрах от тебя)\n"
            response += f"📝 {place['desc']}\n"

            # Генерация прямых ссылок для автоматического построения маршрутов
            yandex_url = f"https://yandex.ru{user_lat},{user_lon}~{place['lat']},{place['lon']}&rtt=pd"
            twogis_url = f"https://2gis.ru{user_lon},{user_lat}/to/{place['lon']},{place['lat']}"

            response += f"🗺 *Построить пешеходный маршрут:*\n"
            response += f"➡️ [Открыть в Яндекс.Картах]({yandex_url})\n"
            response += f"➡️ [Открыть в 2ГИС]({twogis_url})\n\n"

    if not found_any:
        response = "К сожалению, в радиусе 1.5 км ничего не найдено по этой категории. Попробуйте сменить геолокацию или выберите другую категорию."

    # Клавиатура после выдачи результатов содержит кнопку возврата в нижнем меню
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("⬅️ Назад в меню"))

    # parse_mode="Markdown" делает текстовые ссылки кликабельными, а disable_web_page_preview прячет громоздкие превью карт
    bot.send_message(chat_id, response, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=markup)

# Валидация ошибочного текстового или медиа-ввода
@bot.message_handler(content_types=['text', 'photo', 'sticker', 'video', 'document'])
def handle_invalid_input(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("⬅️ Назад в меню"))
    bot.send_message(
        message.chat.id,
        "Я умею работать только со встроенными кнопками меню и геолокацией.\n\n"
        "Пожалуйста, используйте кнопки управления на нижней панели:",
        reply_markup=markup
    )

if __name__ == '__main__':
    print("Бот успешно запущен...")
    bot.infinity_polling()
