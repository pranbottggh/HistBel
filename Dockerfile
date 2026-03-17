# Используем легкий образ Python 3.11
FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Убираем BOM и лишние символы в requirements
RUN sed -i 's/^\xEF\xBB\xBF//' requirements.txt 2>/dev/null || true && \
    sed -i 's/^\xFF\xFE//' requirements.txt 2>/dev/null || true && \
    sed -i 's/^\xFE\xFF//' requirements.txt 2>/dev/null || true && \
    tr -d '\r\0' < requirements.txt > requirements.txt.tmp && mv requirements.txt.tmp requirements.txt 2>/dev/null || true

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код бота
COPY . .

# Создаем папку для данных
RUN mkdir -p /app/data && chmod 777 /app/data

# Команда запуска бота
CMD ["python", "bot.py"]
