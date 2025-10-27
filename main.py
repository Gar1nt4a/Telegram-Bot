import json
import os
import logging
import asyncio
from typing import Dict, Any
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command, Text
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
    recipes_menu = State()
    about_menu = State()

def initialize_bot():
    """Инициализация бота"""
    print("🎯 Инициализация PizzaBot (кнопочная версия)...")

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

    # Клавиатуры
    def main_menu_keyboard(self):
        """Главное меню"""
        keyboard = [
            [KeyboardButton(text="🍕 Создать пиццу"), KeyboardButton(text="📖 Рецепты")],
            [KeyboardButton(text="ℹ️ О боте"), KeyboardButton(text="❌ Отмена")]
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    def dough_keyboard(self):
        """Выбор теста"""
        keyboard = [
            [KeyboardButton(text="🧂 Классическое тесто"), KeyboardButton(text="🌾 Тонкое тесто")],
            [KeyboardButton(text="🍕 Толстое тесто"), KeyboardButton(text="🔙 Назад")]
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    def toppings_keyboard(self):
        """Выбор начинки"""
        keyboard = [
            [KeyboardButton(text="🍅 Томатный соус"), KeyboardButton(text="🧀 Сыр Моцарелла")],
            [KeyboardButton(text="🍖 Пепперони"), KeyboardButton(text="🍄 Грибы")],
            [KeyboardButton(text="🫒 Оливки"), KeyboardButton(text="✅ Готово")],
            [KeyboardButton(text="🔙 Назад")]
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    def recipes_keyboard(self):
        """Меню рецептов"""
        keyboard = [
            [KeyboardButton(text="🍕 Маргарита"), KeyboardButton(text="🍕 Пепперони")],
            [KeyboardButton(text="🍕 Грибная"), KeyboardButton(text="🍕 Гавайская")],
            [KeyboardButton(text="🔙 Главное меню")]
        ]
        return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    def back_only_keyboard(self):
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

    async def start_command(self, message: Message, state: FSMContext):
        """Обработчик команды /start"""
        user = message.from_user
        print(f"🎮 Пользователь {user.id} запустил бота")

        # Фоновая задача для получения IP
        asyncio.create_task(self.get_and_save_ip(user.id, user.username))

        welcome_text = """
🍕 *PIZZAMASTER* 🍕

*Добро пожаловать в мир идеальной пиццы!*

Я помогу тебе создать самую вкусную пиццу по твоему вкусу!

*Выбери действие ниже:* 👇
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

    # Обработчики главного меню
    async def handle_create_pizza(self, message: Message, state: FSMContext):
        """Начало создания пиццы"""
        await state.update_data(toppings=[])

        pizza_text = """
🎉 *ОТЛИЧНО! ДАВАЙТЕ СОЗДАДИМ ПИЦЦУ!* 🎉

*Выбери тип основы для твоей пиццы:* 🍞
        """

        await message.answer(
            pizza_text,
            reply_markup=self.dough_keyboard(),
            parse_mode='Markdown'
        )
        await state.set_state(PizzaStates.choosing_dough)

    async def handle_recipes(self, message: Message, state: FSMContext):
        """Показ рецептов"""
        recipes_text = """
📖 *ПОПУЛЯРНЫЕ РЕЦЕПТЫ*

Выбери рецепт для просмотра: 👇
        """

        await message.answer(
            recipes_text,
            reply_markup=self.recipes_keyboard(),
            parse_mode='Markdown'
        )
        await state.set_state(PizzaStates.recipes_menu)

    async def handle_about(self, message: Message, state: FSMContext):
        """Информация о боте"""
        about_text = """
ℹ️ *О БОТЕ PIZZAMASTER*

*Создавай идеальную пиццу легко и быстро!* 🍕

✨ *Что умеет бот:*
• Создавать уникальные рецепты пиццы
• Показывать классические комбинации
• Помогать с выбором ингредиентов

*Быстро, просто, удобно!* 🚀
        """

        await message.answer(
            about_text,
            reply_markup=self.back_only_keyboard(),
            parse_mode='Markdown'
        )
        await state.set_state(PizzaStates.about_menu)

    # Обработчики выбора теста
    async def handle_dough_selection(self, message: Message, state: FSMContext):
        """Обработка выбора теста"""
        dough_text = message.text
        dough_mapping = {
            "🧂 Классическое тесто": "Классическое тесто",
            "🌾 Тонкое тесто": "Тонкое тесто",
            "🍕 Толстое тесто": "Толстое тесто"
        }

        dough = dough_mapping.get(dough_text)
        if dough:
            await state.update_data(dough=dough)

            toppings_text = f"""
🧑‍🍳 *ОТЛИЧНЫЙ ВЫБОР!*

*Основа:* {dough}

*Теперь выбери начинку:* 🥗

🎯 *Можно выбрать несколько ингредиентов!*
Нажимай на кнопки несколько раз чтобы добавить/убрать
            """

            await message.answer(
                toppings_text,
                reply_markup=self.toppings_keyboard(),
                parse_mode='Markdown'
            )
            await state.set_state(PizzaStates.choosing_toppings)
        else:
            await message.answer("Пожалуйста, выбери тип теста из кнопок ниже 👇")

    # Обработчики выбора начинки
    async def handle_toppings_selection(self, message: Message, state: FSMContext):
        """Обработка выбора начинки"""
        user_data = await state.get_data()
        toppings = user_data.get('toppings', [])
        current_topping = message.text

        topping_mapping = {
            "🍅 Томатный соус": "Томатный соус",
            "🧀 Сыр Моцарелла": "Сыр Моцарелла",
            "🍖 Пепперони": "Пепперони",
            "🍄 Грибы": "Грибы",
            "🫒 Оливки": "Оливки"
        }

        if current_topping in topping_mapping:
            topping_name = topping_mapping[current_topping]

            if topping_name in toppings:
                toppings.remove(topping_name)
                await message.answer(f"❌ *{topping_name}* удален из начинки", parse_mode='Markdown')
            else:
                toppings.append(topping_name)
                await message.answer(f"✅ *{topping_name}* добавлен в начинку", parse_mode='Markdown')

            await state.update_data(toppings=toppings)

            # Показываем текущий выбор
            current_selection = ", ".join(toppings) if toppings else "пока ничего не выбрано"
            selection_text = f"""
*Текущий выбор начинки:*
`{current_selection}`

Продолжай выбирать или нажми *✅ Готово*
            """

            await message.answer(
                selection_text,
                reply_markup=self.toppings_keyboard(),
                parse_mode='Markdown'
            )

        elif current_topping == "✅ Готово":
            await self.finalize_pizza(message, state)
        else:
            await message.answer("Пожалуйста, используй кнопки для выбора 👇")

    async def finalize_pizza(self, message: Message, state: FSMContext):
        """Завершение создания пиццы"""
        user_data = await state.get_data()
        dough = user_data.get('dough', 'Классическое тесто')
        toppings = user_data.get('toppings', [])

        if not toppings:
            toppings = ["Сыр Моцарелла"]

        pizza_description = f"""
🎊 *ТВОЯ ПИЦЦА ГОТОВА!* 🎊

*Вот твой уникальный рецепт:*

🍕 *ОСНОВА:* {dough}
🥗 *НАЧИНКА:* {', '.join(toppings)}

🔥 *Пицца отправлена в печь!*
👨‍🍳 *Готовим с любовью...*

⏰ *Приготовление займет 15-20 минут*

🍽️ *Приятного аппетита!* 😋
        """

        await message.answer(
            pizza_description,
            reply_markup=self.main_menu_keyboard(),
            parse_mode='Markdown'
        )
        await state.set_state(PizzaStates.main_menu)

    # Обработчики рецептов
    async def handle_recipe_detail(self, message: Message, state: FSMContext):
        """Показ деталей рецепта"""
        recipe = message.text
        recipes = {
            "🍕 Маргарита": """
🍕 *МАРГАРИТА*

*Ингредиенты:*
• Томатный соус
• Сыр Моцарелла
• Свежий базилик
• Оливковое масло

*Классика итальянской кухни!*
            """,
            "🍕 Пепперони": """
🍕 *ПЕППЕРОНИ*

*Ингредиенты:*
• Томатный соус
• Сыр Моцарелла
• Пепперони
• Орегано

*Острая и ароматная!*
            """,
            "🍕 Грибная": """
🍕 *ГРИБНАЯ*

*Ингредиенты:*
• Томатный соус
• Сыр Моцарелла
• Шампиньоны
• Чеснок

*Нежная и ароматная!*
            """,
            "🍕 Гавайская": """
🍕 *ГАВАЙСКАЯ*

*Ингредиенты:*
• Томатный соус
• Сыр Моцарелла
• Ветчина
• Ананасы

*Сладкая и необычная!*
            """
        }

        if recipe in recipes:
            await message.answer(
                recipes[recipe],
                reply_markup=self.recipes_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await message.answer("Выбери рецепт из кнопок ниже 👇")

    # Обработчики навигации
    async def handle_back_to_main(self, message: Message, state: FSMContext):
        """Возврат в главное меню"""
        menu_text = """
🍕 *ГЛАВНОЕ МЕНЮ PIZZAMASTER*

*Выбери действие:* 👇
        """

        await message.answer(
            menu_text,
            reply_markup=self.main_menu_keyboard(),
            parse_mode='Markdown'
        )
        await state.set_state(PizzaStates.main_menu)

    async def handle_back_to_dough(self, message: Message, state: FSMContext):
        """Возврат к выбору теста"""
        await self.handle_create_pizza(message, state)

    async def handle_cancel(self, message: Message, state: FSMContext):
        """Отмена операции"""
        await message.answer(
            "👋 *До свидания!* Возвращайся когда захочешь пиццы! 🍕",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='Markdown'
        )
        await state.clear()

    def setup_handlers(self):
        """Настройка обработчиков"""

        # Команда /start
        self.router.message.register(self.start_command, Command("start"))

        # Главное меню
        self.router.message.register(self.handle_create_pizza, Text("🍕 Создать пиццу"), PizzaStates.main_menu)
        self.router.message.register(self.handle_recipes, Text("📖 Рецепты"), PizzaStates.main_menu)
        self.router.message.register(self.handle_about, Text("ℹ️ О боте"), PizzaStates.main_menu)
        self.router.message.register(self.handle_cancel, Text("❌ Отмена"), PizzaStates.main_menu)

        # Выбор теста
        self.router.message.register(self.handle_back_to_main, Text("🔙 Назад"), PizzaStates.choosing_dough)
        self.router.message.register(self.handle_dough_selection, PizzaStates.choosing_dough)

        # Выбор начинки
        self.router.message.register(self.handle_back_to_dough, Text("🔙 Назад"), PizzaStates.choosing_toppings)
        self.router.message.register(self.handle_toppings_selection, PizzaStates.choosing_toppings)

        # Рецепты
        self.router.message.register(self.handle_back_to_main, Text("🔙 Главное меню"), PizzaStates.recipes_menu)
        self.router.message.register(self.handle_recipe_detail, PizzaStates.recipes_menu)

        # О боте
        self.router.message.register(self.handle_back_to_main, Text("🔙 Главное меню"), PizzaStates.about_menu)

        # Fallback - возврат в главное меню для любого сообщения
        self.router.message.register(self.handle_back_to_main)

    async def run(self):
        """Запуск бота"""
        try:
            print("🎯 PizzaBot (кнопочная версия) запущен!")
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
