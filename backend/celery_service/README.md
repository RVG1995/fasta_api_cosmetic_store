# Централизованный Celery-сервис для микросервисной архитектуры

Этот сервис предоставляет централизованное решение для асинхронной обработки задач всех микросервисов проекта с использованием Celery.

## Особенности

- Единый монолитный сервис Celery для всех микросервисов
- Поддержка различных очередей для разных микросервисов 
- Централизованное управление периодическими задачами
- Общая инфраструктура (Redis) для брокера сообщений и хранения результатов

## Структура

```
celery_service/
├── tasks/
│   ├── __init__.py
│   ├── auth_tasks.py      # Задачи для auth_service
│   ├── cart_tasks.py      # Задачи для cart_service
│   ├── order_tasks.py     # Задачи для order_service 
│   └── product_tasks.py   # Задачи для product_service
├── celery_app.py          # Централизованная настройка Celery
├── schedule.py            # Настройка периодических задач (celerybeat)
├── requirements.txt       # Зависимости
├── Dockerfile             # Для создания Docker-образа
├── .env.example           # Пример переменных окружения 
├── INTEGRATION.md         # Инструкция по интеграции с микросервисами
└── README.md              # Документация
```

## Запуск

### В режиме разработки:

```bash
# Используйте скрипт для запуска различных компонентов
./run_dev.sh worker  # Запуск worker
./run_dev.sh beat    # Запуск beat для периодических задач
./run_dev.sh flower  # Запуск Flower для мониторинга
```

### С Docker Compose:

```bash
docker-compose up -d
```

## Подход к использованию

В отличие от распределенного подхода, данный сервис работает как монолитный Celery-сервис:

1. Все задачи определяются и выполняются **только** в этом централизованном сервисе
2. Микросервисы не импортируют задачи, а только отправляют сообщения в очередь Redis
3. Каждая задача имеет доступ к API соответствующих микросервисов для обратного взаимодействия

## Добавление новых задач

Для добавления новых задач:

1. Создайте/обновите файл в директории `tasks/` для соответствующего микросервиса
2. Зарегистрируйте задачу с помощью декоратора `@app.task`
3. Убедитесь, что задача указывает правильную очередь через параметр `queue`
4. При необходимости добавьте периодические задачи в `schedule.py`

Пример:

```python
# В файле tasks/product_tasks.py
from celery_app import app
import requests

@app.task(
    name='product.process_images',
    queue='product',
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3}
)
def process_product_images(product_id, image_urls):
    """Обрабатывает изображения продукта"""
    try:
        # Логика обработки
        # ...
        
        # Взаимодействие с API микросервиса
        requests.post(
            f"http://product-service/api/products/{product_id}/images/processed",
            json={"status": "completed"}
        )
    except Exception as e:
        logger.error(f"Error processing images for product {product_id}: {e}")
        raise
```

## Интеграция с микросервисами

Для интеграции с микросервисами необходимо добавить утилиту отправки сообщений в очередь Redis. Детальная инструкция по интеграции с микросервисами доступна в файле [INTEGRATION.md](INTEGRATION.md).

## Настройка очередей

Каждый микросервис использует свою очередь:
- `auth` - для задач аутентификации
- `cart` - для задач корзины
- `order` - для задач заказов
- `product` - для задач товаров

## Мониторинг

Для мониторинга задач используйте Flower:
- В режиме разработки: `./run_dev.sh flower`
- В Docker Compose: доступен по адресу `http://localhost:5555` 