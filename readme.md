# Algotrading monitor

```mermaid
sequenceDiagram
    participant U as User
    participant S as System
    participant K as Kafka
    participant G as Git
    participant DB as Database
    participant LLM as LLM (OpenRouter)
    participant R as RAG (LangChain)
    participant A as Analysis

    U->>S: Предоставляет URL Git-репозиториев
    S->>K: Отправляет задачу в Kafka (URL)
    K-->>S: Подтверждение отправки

    loop Обработка задач
        S->>K: Запрашивает задачу из очереди
        K-->>S: URL репозитория
        S->>G: Клонирует репозиторий
        G-->>S: Локальная копия

        S->>DB: Записывает статус "Cloning" и время
        DB-->>S: Подтверждение записи

        S->>LLM: Запрос списка важных файлов
        LLM-->>S: Список ключевых файлов
        S->>DB: Обновляет статус "File Selection"

        S->>R: Добавляет файлы в RAG
        R-->>S: Подтверждение добавления
        S->>DB: Обновляет статус "RAG Loaded"

        S->>A: Запрос LLM-анализа проекта
        A->>LLM: Анализ с использованием RAG
        LLM-->>A: Результаты анализа
        A-->>S: Форматированные результаты
        S->>DB: Обновляет статус "Analyzed" и время

        S-->>U: Вывод анализа проекта
    end
```

### Обновления в архитектуре:

1. **Kafka (K):**
   - Добавлен как очередь задач.
   - Пользователь отправляет URL в систему, а она публикует задачу в Kafka.
   - Система асинхронно забирает задачи из Kafka и обрабатывает их.

2. **Database (DB):**
   - Хранит информацию о репозиториях:
     - URL репозитория
     - Статус обработки (например, "Cloning", "File Selection", "RAG Loaded", "Analyzed")
     - Время начала/окончания этапов
   - Система обновляет статус и время на каждом этапе.

3. **Поток данных:**
   - Пользователь → Kafka → Система забирает задачу.
   - Клонирование → выбор файлов → загрузка в RAG → анализ.
   - На каждом шаге обновляется база данных.
   - Результат возвращается пользователю.

### Предполагаемая структура базы данных:
```sql
CREATE TABLE repositories (
    id SERIAL PRIMARY KEY,
    url VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Используемые технологии:
- **Kafka**: Для асинхронной обработки задач.
- **Database**: Любая СУБД (PostgreSQL, MySQL и т.д.) для хранения статуса и времени.
- **LangChain**: Для RAG.
- **OpenRouter**: Для LLM.

Если нужно уточнить детали (например, структуру топиков в Kafka или схему базы данных), дайте знать!