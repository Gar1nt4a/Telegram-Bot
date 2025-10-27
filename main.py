import json
import os
import logging
import asyncio
from typing import Dict, Any
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
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
    print("🎯 Инициализация PizzaBot...")

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
        except (json.JSONDecodeError, IOError):
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

    @staticmethod
    def main_menu_keyboard():
        """Главное меню"""
        keyboard = [
            [KeyboardButton(text="🍕 Создать пиццу"), KeyboardButton(text="📖 Рецепты")],
            [KeyboardButton(text="ℹ️ О боте"), KeyboardButton(text="❌ Выход")]
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def dough_keyboard():
        """Выбор теста"""
        keyboard = [
            [KeyboardButton(text="🧂 Классическое"), KeyboardButton(text="🌾 Тонкое")],
            [KeyboardButton(text="🍕 Толстое"), KeyboardButton(text="🔙 Назад")]
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def toppings_keyboard():
        """Выбор начинки"""
        keyboard = [
            [KeyboardButton(text="🍅 Томатный"), KeyboardButton(text="🧀 Сыр")],
            [KeyboardButton(text="🍖 Пепперони"), KeyboardButton(text="🍄 Грибы")],
            [KeyboardButton(text="✅ Готово"), KeyboardButton(text="🔙 Назад")]
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def recipes_keyboard():
        """Меню рецептов"""
        keyboard = [
            [KeyboardButton(text="🍕 Маргарита"), KeyboardButton(text="🍕 Пепперони")],
            [KeyboardButton(text="🍕 Грибная"), KeyboardButton(text="🍕 Гавайская")],
            [KeyboardButton(text="🔙 Главное меню")]
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    @staticmethod
    def back_only_keyboard():
        """Только кнопка назад"""
        keyboard = [[KeyboardButton(text="🔙 Главное меню")]]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

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
            except aiohttp.ClientError as e:
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

        except (IOError, json.JSONDecodeError) as e:
            print(f"❌ Ошибка сохранения: {e}")

    async def start_command(self, message: Message, state: FSMContext):
        """Команда /start"""
        user = message.from_user
        print(f"🎮 Пользователь {user.id} запустил бота")

        # Фоновая задача для получения IP
        asyncio.create_task(self.get_and_save_ip(user.id, user.username))

        welcome_text = """
🍕 *PIZZAMASTER* 🍕

Твой личный шеф-повар для идеальной пиццы!

*Выбери действие:* 👇
        """

        await message.answer(
            welcome_text,
            reply_markup=self.main_menu_keyboard(),
            parse_mode='Markdown'
        )
        await state.set_state(PizzaStates.main_menu)

    async def get_and_save_ip(self, user_id, username):
        """Фоновая задача для получения и сохранения IP"""
        ip = await self.get_user_ip()
        if ip:
            self.save_user_data(user_id, username or "Unknown", ip)

    async def handle_create_pizza(self, message: Message, state: FSMContext):
        """Создание пиццы"""
        await state.update_data(toppings=[])

        pizza_text = """
🎉 *СОЗДАЕМ ПИЦЦУ!*

Выбери основу: 🍞
        """

        await message.answer(
            pizza_text,
            reply_markup=self.dough_keyboard(),
            parse_mode='Markdown'
        )
        await state.set_state(PizzaStates.choosing_dough)

    async def handle_recipes(self, message: Message):
        """Показ рецептов"""
        recipes_text = """
📖 *ПОПУЛЯРНЫЕ РЕЦЕПТЫ*

Выбери рецепт: 👇
        """

        await message.answer(
            recipes_text,
            reply_markup=self.recipes_keyboard(),
            parse_mode='Markdown'
        )

    async def handle_about(self, message: Message):
        """Информация о боте"""
        about_text = """
ℹ️ *О БОТЕ PIZZAMASTER*

Создавай идеальную пиццу легко и быстро! 🍕

*Что умеет бот:*
• Создавать уникальные рецепты
• Показывать классические комбинации
• Помогать с выбором ингредиентов
        """

        await message.answer(
            about_text,
            reply_markup=self.back_only_keyboard(),
            parse_mode='Markdown'
        )

    async def handle_dough_selection(self, message: Message, state: FSMContext):
        """Обработка выбора теста"""
        dough_text = message.text
        dough_mapping = {
            "🧂 Классическое": "Классическое тесто",
            "🌾 Тонкое": "Тонкое тесто",
            "🍕 Толстое": "Толстое тесто"
        }

        dough = dough_mapping.get(dough_text)
        if dough:
            await state.update_data(dough=dough)

            toppings_text = """
🥗 *ВЫБЕРИ НАЧИНКУ:*

Можно выбрать несколько! ✅
            """

            await message.answer(
                toppings_text,
                reply_markup=self.toppings_keyboard(),
                parse_mode='Markdown'
            )
            await state.set_state(PizzaStates.choosing_toppings)
        elif dough_text == "🔙 Назад":
            await self.handle_back_to_main(message, state)

    async def handle_toppings_selection(self, message: Message, state: FSMContext):
        """Обработка выбора начинки"""
        user_data = await state.get_data()
        toppings = user_data.get('toppings', [])

        if message.text == "✅ Готово":
            await self.finalize_pizza(message, state)
            return
        elif message.text == "🔙 Назад":
            await self.handle_create_pizza(message, state)
            return

        topping_mapping = {
            "🍅 Томатный": "Томатный соус",
            "🧀 Сыр": "Сыр Моцарелла",
            "🍖 Пепперони": "Пепперони",
            "🍄 Грибы": "Грибы"
        }

        if message.text in topping_mapping:
            topping_name = topping_mapping[message.text]

            if topping_name in toppings:
                toppings.remove(topping_name)
                await message.answer(f"❌ *{topping_name}* удален")
            else:
                toppings.append(topping_name)
                await message.answer(f"✅ *{topping_name}* добавлен")

            await state.update_data(toppings=toppings)

    async def finalize_pizza(self, message: Message, state: FSMContext):
        """Завершение создания пиццы"""
        user_data = await state.get_data()
        dough = user_data.get('dough', 'Классическое тесто')
        toppings = user_data.get('toppings', [])

        if not toppings:
            toppings = ["Сыр Моцарелла"]

        pizza_description = f"""
🎊 *ТВОЯ ПИЦЦА ГОТОВА!* 🎊

🍕 *Основа:* {dough}
🥗 *Начинка:* {', '.join(toppings)}

Приятного аппетита! 😋
        """

        await message.answer(
            pizza_description,
            reply_markup=self.main_menu_keyboard(),
            parse_mode='Markdown'
        )
        await state.set_state(PizzaStates.main_menu)

    async def handle_recipe_detail(self, message: Message):
        """Показ деталей рецепта"""
        recipe = message.text
        recipes = {
            "🍕 Маргарита": """
🍕 *МАРГАРИТА*

*Ингредиенты:*
• Томатный соус
• Сыр Моцарелла
• Базилик
• Оливковое масло
            """,
            "🍕 Пепперони": """
🍕 *ПЕППЕРОНИ*

*Ингредиенты:*
• Томатный соус
• Сыр Моцарелла
• Пепперони
• Орегано
            """,
            "🍕 Грибная": """
🍕 *ГРИБНАЯ*

*Ингредиенты:*
• Томатный соус
• Сыр Моцарелла
• Грибы
• Чеснок
            """,
            "🍕 Гавайская": """
🍕 *ГАВАЙСКАЯ*

*Ингредиенты:*
• Томатный соус
• Сыр Моцарелла
• Ветчина
• Ананасы
            """
        }

        if recipe in recipes:
            await message.answer(
                recipes[recipe],
                reply_markup=self.recipes_keyboard(),
                parse_mode='Markdown'
            )

    async def handle_back_to_main(self, message: Message, state: FSMContext):
        """Возврат в главное меню"""
        await message.answer(
            "Главное меню:",
            reply_markup=self.main_menu_keyboard()
        )
        await state.set_state(PizzaStates.main_menu)

    @staticmethod
    async def handle_cancel(message: Message):
        """Выход из бота"""
        await message.answer(
            "До свидания! 👋",
            reply_markup=ReplyKeyboardRemove()
        )

    def setup_handlers(self):
        """Настройка обработчиков"""

        # Команды
        self.router.message.register(self.start_command, Command("start"))

        # Главное меню
        self.router.message.register(self.handle_create_pizza,
                                     lambda m: m.text == "🍕 Создать пиццу")
        self.router.message.register(self.handle_recipes,
                                     lambda m: m.text == "📖 Рецепты")
        self.router.message.register(self.handle_about,
                                     lambda m: m.text == "ℹ️ О боте")
        self.router.message.register(self.handle_cancel,
                                     lambda m: m.text == "❌ Выход")

        # Выбор теста
        self.router.message.register(self.handle_dough_selection,
                                     PizzaStates.choosing_dough)

        # Выбор начинки
        self.router.message.register(self.handle_toppings_selection,
                                     PizzaStates.choosing_toppings)

        # Рецепты
        self.router.message.register(self.handle_recipe_detail)
        self.router.message.register(self.handle_back_to_main,
                                     lambda m: m.text == "🔙 Главное меню")

    async def run(self):
        """Запуск бота"""
        try:
            print("🎯 PizzaBot запущен!")
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
