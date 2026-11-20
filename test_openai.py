
import os

from dotenv import load_dotenv
from openai import OpenAI


# 1. Загружаем переменные из .env
load_dotenv()

# 2. Создаём OpenAI-клиент
client = OpenAI()

# 3. Получаем название модели
model = os.getenv("OPENAI_MODEL", "gpt-6-luna")

# 4. Отправляем запрос языковой модели
response = client.responses.create(
    model=model,
    instructions=(
        "Ты преподаватель программирования. "
        "Объясняй кратко, понятно и на русском языке."
    ),
    input=(
        "Объясни простыми словами, "
        "что такое MCP и зачем он нужен."
    ),
)

# 5. Выводим ответ
print("\n=== ОТВЕТ LLM ===")
print(response.output_text)














