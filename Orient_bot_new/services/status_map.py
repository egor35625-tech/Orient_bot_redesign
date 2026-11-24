STATUS_LABELS = {
    "new": "Новый",
    "processing": "На рассмотрении",
    "awaiting_client": "Ожидает ответа клиента",
    "price_sent": "Цена отправлена",
    "confirmed": "Подтверждён",
    "in_progress": "В работе",
    "completed": "Выполнен",
    "rejected": "Отклонён",
    "active": "В работе",
}

def human_status(code: str) -> str:
    return STATUS_LABELS.get(code, code)