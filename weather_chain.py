'''
1 Получить название города от пользователя
2 Вызвать geocode_location
3 Извлечь JSON из result.content
4 Выбрать город с нужным кодом страны
5 Получить latitude, longitude и timezone
6 Вызвать get_weather_forecast
7 Вывести результат прогноза
'''

import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

def describe_weather(code):
    """Переводит WMO-код погоды в описание."""

    descriptions = {
        0: "Ясно",
        1: "Преимущественно ясно",
        2: "Переменная облачность",
        3: "Пасмурно",
        45: "Туман",
        48: "Изморозевый туман",
        51: "Слабая морось",
        53: "Умеренная морось",
        55: "Сильная морось",
        61: "Небольшой дождь",
        63: "Умеренный дождь",
        65: "Сильный дождь",
        71: "Небольшой снег",
        73: "Умеренный снег",
        75: "Сильный снег",
        80: "Небольшие ливни",
        81: "Умеренные ливни",
        82: "Сильные ливни",
        95: "Гроза",
        96: "Гроза с небольшим градом",
        99: "Гроза с сильным градом",
    }

    return descriptions.get(
        code,
        f"Неизвестный код погоды: {code}"
    )


MCP_URL = "https://weather.chukai.io/mcp"


def parse_tool_result(result):
    """Преобразует ответ MCP-инструмента в словарь."""

    if result.is_error:
        errors = [
            block.text
            for block in result.content
            if block.type == "text"
        ]
        raise RuntimeError(
            "Ошибка MCP: " + "; ".join(errors)
        )

    # Сначала пробуем структурированный ответ
    if result.structured_content is not None:
        return result.structured_content

    # Иначе извлекаем JSON из текстового блока
    for block in result.content:
        if block.type == "text":
            try:
                return json.loads(block.text)
            except json.JSONDecodeError:
                continue

    raise ValueError("Не удалось получить JSON из MCP")


async def main():
    city_name = "Moscow"
    country_code = "RU"

    async with streamable_http_client(MCP_URL) as (
        read_stream,
        write_stream,
    ):
        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:

            await session.initialize()
            print("MCP подключён")

            # Шаг 1. Поиск города
            geo_result = await session.call_tool(
                "geocode_location",
                arguments={"name": city_name}
            )

            geo_data = parse_tool_result(geo_result)

            # Шаг 2. Выбор города в нужной стране
            locations = geo_data.get("results") or []

            location = next(
                (
                    item for item in locations
                    if item.get("country_code") == country_code
                ),
                None
            )

            if location is None:
                print("Город не найден")
                return

            latitude = location["latitude"]
            longitude = location["longitude"]
            timezone = location["timezone"]

            print(
                f"Найден город: {location['name']}, "
                f"{location['country']}"
            )
            print(f"Координаты: {latitude}, {longitude}")

            # Шаг 3. Получение погоды
            weather_result = await session.call_tool(
                "get_weather_forecast",
                arguments={
                    "latitude": latitude,
                    "longitude": longitude,
                    "timezone": timezone,
                    "current_weather": True,
                    "forecast_days": 1,
                }
            )

            weather_data = parse_tool_result(
                weather_result
            )

            print("\n=== КЛЮЧИ ОТВЕТА ===")
            print(list(weather_data.keys()))

            print("\n=== CURRENT WEATHER ===")
            print(json.dumps(
                weather_data.get("current_weather"),
                indent=2,
                ensure_ascii=False
            ))
            # ---> ['latitude', 'longitude', 'elevation', 'timezone', 'timezone_abbreviation', 'current_weather', 'hourly', 'daily']
            #       == = CURRENT WEATHER == =
            #         {
            #             "temperature": 3.3,
            #             "windspeed": 6.8,
            #             "winddirection": 108.0,
            #             "weathercode": 61,
            #             "time": "2026-11-19T16:00"
            #         }


            # Шаг 4. Вывод данных
            print("\n=== ПОГОДА ===")
            print(format_weather(
                weather_data,
                location["name"]
            ))



def format_weather(weather_data, city_name):
    """Формирует понятный прогноз из JSON."""

    current = weather_data.get("current_weather")

    if not isinstance(current, dict):
        return "Текущая погода отсутствует в ответе"

    temperature = current.get("temperature")
    wind_speed = current.get("windspeed")
    wind_direction = current.get("winddirection")
    weather_code = current.get("weathercode")

    lines = [f"Погода в городе {city_name}"]

    # вместо if temperature, потому что температура 0 °C — корректное значение, а Python считает число 0 ложным.
    if temperature is not None:
        lines.append(
            f"Температура: {temperature} °C"
        )

    if weather_code is not None:
        lines.append(
            f"Состояние: {describe_weather(weather_code)}"
        )

    if wind_speed is not None:
        lines.append(
            f"Скорость ветра: {wind_speed} км/ч"
        )

    if wind_direction is not None:
        lines.append(
            f"Направление ветра: {wind_direction}°"
        )

    return "\n".join(lines)



if __name__ == "__main__":
    asyncio.run(main())

















