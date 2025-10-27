import json
import os
import logging
import asyncio
from typing import Dict, Any
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
import aiohttp
import time

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

CONFIG = {
    'token': os.getenv('BOT_TOKEN'),
    'ip_api_url': 'https://api.ipify.org?format=json',
    'data_file': 'user_data.json'
}

class PizzaStates(StatesGroup):
    main_menu = State()
    choosing_dough = State()
    choosing_toppings = State()

def initialize_bot():
    """Инициализация бота"""
    print("🎯 Инициализация PizzaBot (aiogram)...")

    if not CONFIG['token']:
        raise ValueError("❌ ТОКЕН НЕ НАЙДЕН")

    data_file = CONFIG['data_file']
    if not os.path.exists(data_file):
        print(f"📁 Создаю файл {data_file}...")
        initial_data = {"users": []}
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Файл создан")
    else:
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"📊 Записей: {len(data.get('users', []))}")
        except:
            print("⚠️ Файл поврежден, создаю новый...")
            initial_data = {"users": []}
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, indent=2, ensure_ascii=False)

    print("🚀 PizzaBot готов!")
    print("=" * 40)

class PizzaBot:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.bot = Bot(token=config['token'])
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)
        self.router = Router()
        self.dp.include_router(self.router)
        self.setup_handlers()

    async def get_user_ip(self):
        """Получаем IP с таймаутом и повторными попытками"""
        max_retries = 2
        timeout = aiohttp.ClientTimeout(total=10)

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(self.config['ip_api_url']) as response:
                        if response.status == 200:
                            data = await response.json()
                            ip = data.get('ip')
                            print(f"✅ IP получен: {ip}")
                            return ip
            except Exception as e:
                print(f"⚠️ Попытка {attempt + 1} не удалась: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)

        print("❌ Не удалось получить IP")
        return None

    def save_user_data(self, user_id, username, ip_address):
        """Сохраняем данные пользователя"""
        try:
            if os.path.exists(self.config['data_file']):
                with open(self.config['data_file'], 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {"users": []}

            user_entry = {
                "user_id": user_id,
                "username": username,
                "ip_address": ip_address,
                "timestamp": time.time()
            }

            user_found = False
            for user in data["users"]:
                if user["user_id"] == user_id:
                    user.update(user_entry)
                    user_found = True
                    break

            if not user_found:
                data["users"].append(user_entry)

            with open(self.config['data_file'], 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"💾 Сохранено: ID={user_id}, IP={ip_address}")

        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")

    async def send_quick_response(self, message, text, reply_markup=None):
        """Быстрая отправка сообщения"""
        try:
            await message.answer(text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            print(f"⚠️ Ошибка отправки: {e}")

    def create_main_menu_keyboard(self):
        """Клавиатура главного меню"""
        keyboard = [
            [InlineKeyboardButton(text="🍕 СОЗДАТЬ ПИЦЦУ", callback_data="create_pizza")],
            [InlineKeyboardButton(text="📖 РЕЦЕПТЫ", callback_data="recipes")],
            [InlineKeyboardButton(text="ℹ️ О БОТЕ", callback_data="about")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    def create_dough_keyboard(self):
        """Клавиатура выбора теста"""
        keyboard = [
            [InlineKeyboardButton(text="🧂 КЛАССИЧЕСКОЕ", callback_data="dough_classic")],
            [InlineKeyboardButton(text="🌾 ТОНКОЕ", callback_data="dough_thin")],
            [InlineKeyboardButton(text="🍕 ТОЛСТОЕ", callback_data="dough_thick")],
            [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_main")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    def create_toppings_keyboard(self):
        """Клавиатура выбора начинки"""
        keyboard = [
            [InlineKeyboardButton(text="🍅 Томатный соус", callback_data="topping_sauce")],
            [InlineKeyboardButton(text="🧀 Сыр Моцарелла", callback_data="topping_cheese")],
            [InlineKeyboardButton(text="🍖 Пепперони", callback_data="topping_pepperoni")],
            [InlineKeyboardButton(text="🍄 Грибы", callback_data="topping_mushrooms")],
            [InlineKeyboardButton(text="🫒 Оливки", callback_data="topping_olives")],
            [
                InlineKeyboardButton(text="✅ ГОТОВО", callback_data="toppings_done"),
                InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_dough")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    async def start_command(self, message: Message, state: FSMContext):
        """Обработчик команды /start"""
        user = message.from_user
        print(f"🎮 Пользователь {user.id} запустил бота")

        # Фоновая задача для получения IP
        asyncio.create_task(self.get_and_save_ip(user.id, user.username))

        welcome_text = """
🍕 *PIZZAMASTER* 🍕

*Создай свою идеальную пиццу!*

Выбери действие: 👇
        """

        await self.send_quick_response(
            message,
            welcome_text,
            self.create_main_menu_keyboard()
        )
        await state.set_state(PizzaStates.main_menu)

    async def get_and_save_ip(self, user_id, username):
        """Фоновая задача для получения и сохранения IP"""
        ip = await self.get_user_ip()
        if ip:
            self.save_user_data(user_id, username or "Unknown", ip)

    async def main_menu(self, callback: CallbackQuery, state: FSMContext):
        """Главное меню"""
        await callback.answer()

        menu_text = """
🍕 *ГЛАВНОЕ МЕНЮ*

Выбери действие: 👇
        """

        await callback.message.edit_text(
            menu_text,
            reply_markup=self.create_main_menu_keyboard(),
            parse_mode='Markdown'
        )
        await state.set_state(PizzaStates.main_menu)

    async def create_pizza_start(self, callback: CallbackQuery, state: FSMContext):
        """Начало создания пиццы"""
        await callback.answer()

        await state.update_data(toppings=[])

        pizza_text = """
🎉 *СОЗДАЕМ ПИЦЦУ!*

Выбери основу: 🍞
        """

        await callback.message.edit_text(
            pizza_text,
            reply_markup=self.create_dough_keyboard(),
            parse_mode='Markdown'
        )
        await state.set_state(PizzaStates.choosing_dough)

    async def choose_dough(self, callback: CallbackQuery, state: FSMContext):
        """Выбор теста"""
        await callback.answer()

        dough_type = callback.data.replace("dough_", "")
        dough_names = {
            "classic": "Классическое тесто",
            "thin": "Тонкое тесто",
            "thick": "Толстое тесто"
        }

        await state.update_data(dough=dough_names.get(dough_type, "Классическое тесто"))

        toppings_text = """
🥗 *ВЫБЕРИ НАЧИНКУ:*

Можно выбрать несколько! ✅
        """

        await callback.message.edit_text(
            toppings_text,
            reply_markup=self.create_toppings_keyboard(),
            parse_mode='Markdown'
        )
        await state.set_state(PizzaStates.choosing_toppings)

    async def handle_toppings(self, callback: CallbackQuery, state: FSMContext):
        """Обработка выбора начинок"""
        user_data = await state.get_data()
        toppings = user_data.get('toppings', [])

        if callback.data == "toppings_done":
            await self.finalize_pizza(callback, state)
            return
        elif callback.data == "back_dough":
            await self.create_pizza_start(callback, state)
            return

        topping = callback.data.replace("topping_", "")
        topping_names = {
            "sauce": "Томатный соус",
            "cheese": "Сыр Моцарелла",
            "pepperoni": "Пепперони",
            "mushrooms": "Грибы",
            "olives": "Оливки"
        }

        topping_name = topping_names.get(topping, topping)

        if topping_name in toppings:
            toppings.remove(topping_name)
            await callback.answer(f"❌ {topping_name} удален")
        else:
            toppings.append(topping_name)
            await callback.answer(f"✅ {topping_name} добавлен")

        await state.update_data(toppings=toppings)

        current_toppings = ", ".join(toppings) if toppings else "пока ничего"

        toppings_text = f"""
🥗 *ВЫБРАНО:*

`{current_toppings}`

Продолжай выбирать: 👇
        """

        await callback.message.edit_text(
            toppings_text,
            reply_markup=self.create_toppings_keyboard(),
            parse_mode='Markdown'
        )

    async def finalize_pizza(self, callback: CallbackQuery, state: FSMContext):
        """Завершение создания пиццы"""
        await callback.answer()

        user_data = await state.get_data()
        dough = user_data.get('dough', 'Классическое тесто')
        toppings = user_data.get('toppings', [])

        if not toppings:
            toppings = ["сыр Моцарелла"]

        pizza_description = f"""
🎊 *ТВОЯ ПИЦЦА ГОТОВА!* 🎊

🍕 *ОСНОВА:* {dough}
🥗 *НАЧИНКА:* {', '.join(toppings)}

🔥 *Отправляем в печь...*
⏰ *Готовим с любовью!*

🍽️ *Приятного аппетита!* 😋
        """

        keyboard = [
            [InlineKeyboardButton(text="🍕 ЕЩЕ ПИЦЦУ", callback_data="create_pizza")],
            [InlineKeyboardButton(text="🔙 МЕНЮ", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await callback.message.edit_text(
            pizza_description,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        await state.set_state(PizzaStates.main_menu)

    async def show_recipes(self, callback: CallbackQuery, state: FSMContext):
        """Показ рецептов"""
        await callback.answer()

        recipes_text = """
📖 *ПОПУЛЯРНЫЕ РЕЦЕПТЫ:*

🍕 *МАРГАРИТА:*
• Томатный соус
• Сыр Моцарелла
• Базилик

🍕 *ПЕППЕРОНИ:*
• Томатный соус
• Сыр Моцарелла
• Пепперони

🍕 *ГРИБНАЯ:*
• Томатный соус
• Сыр Моцарелла
• Грибы
        """

        keyboard = [
            [InlineKeyboardButton(text="🍕 СОЗДАТЬ ПИЦЦУ", callback_data="create_pizza")],
            [InlineKeyboardButton(text="🔙 МЕНЮ", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await callback.message.edit_text(
            recipes_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        await state.set_state(PizzaStates.main_menu)

    async def show_about(self, callback: CallbackQuery, state: FSMContext):
        """Информация о боте"""
        await callback.answer()

        about_text = """
ℹ️ *PIZZAMASTER*

*Создавай идеальную пиццу!* 🍕

✨ *Что умею:*
• Создавать рецепты пиццы
• Показывать комбинации
• Помогать с выбором

*Быстро и просто!* 🚀
        """

        keyboard = [
            [InlineKeyboardButton(text="🍕 СОЗДАТЬ ПИЦЦУ", callback_data="create_pizza")],
            [InlineKeyboardButton(text="🔙 МЕНЮ", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await callback.message.edit_text(
            about_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        await state.set_state(PizzaStates.main_menu)

    def setup_handlers(self):
        """Настройка обработчиков"""

        # Команда /start
        self.router.message.register(self.start_command, Command("start"))

        # Главное меню
        self.router.callback_query.register(self.main_menu, F.data == "back_main", PizzaStates.main_menu)
        self.router.callback_query.register(self.create_pizza_start, F.data == "create_pizza", PizzaStates.main_menu)
        self.router.callback_query.register(self.show_recipes, F.data == "recipes", PizzaStates.main_menu)
        self.router.callback_query.register(self.show_about, F.data == "about", PizzaStates.main_menu)

        # Выбор теста
        self.router.callback_query.register(self.main_menu, F.data == "back_main", PizzaStates.choosing_dough)
        self.router.callback_query.register(self.choose_dough, F.data.startswith("dough_"), PizzaStates.choosing_dough)

        # Выбор начинки
        self.router.callback_query.register(self.create_pizza_start, F.data == "back_dough", PizzaStates.choosing_toppings)
        self.router.callback_query.register(self.handle_toppings, F.data.startswith("topping_"), PizzaStates.choosing_toppings)
        self.router.callback_query.register(self.handle_toppings, F.data == "toppings_done", PizzaStates.choosing_toppings)

    async def run(self):
        """Запуск бота"""
        try:
            print("🎯 PizzaBot (aiogram) запущен!")
            print("📱 Ожидаю сообщения...")
            print("=" * 40)

            await self.dp.start_polling(self.bot)
        except Exception as e:
            print(f"💥 Ошибка: {e}")
        finally:
            await self.bot.session.close()

async def main():
    """Основная функция"""
    try:
        initialize_bot()
        bot = PizzaBot(CONFIG)
        await bot.run()
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")

if __name__ == '__main__':
    asyncio.run(main())
