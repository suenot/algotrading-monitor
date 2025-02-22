Для описания сервисов проекта и их взаимодействия я использую диаграмму последовательности в Mermaid. Эта диаграмма показывает, как сервисы обмениваются данными и в каком порядке выполняются действия. Вот список сервисов и их взаимодействие:

### Сервисы проекта:
1. **Project Discovery Service** — автоматически ищет алготрейдинговые проекты и отправляет их на анализ.
2. **Git Cloning Service** — клонирует репозиторий по заданию из Kafka.
3. **File Selection Service** — отбирает ключевые файлы из склонированного репозитория.
4. **RAG Loading Service** — загружает файлы в RAG.
5. **Project Analysis Service** — анализирует данные и формирует результаты.
6. **Database Service** — хранит статусы и результаты анализа.
7. **Kafka Task Management Service** — принимает запросы от пользователя и управляет задачами через Kafka.

### Диаграмма Mermaid:
```mermaid
sequenceDiagram
    participant ProjectDiscoveryService
    participant User
    participant KafkaTaskManagementService
    participant Kafka
    participant GitCloningService
    participant DatabaseService
    participant FileSelectionService
    participant RAGLoadingService
    participant ProjectAnalysisService

    ProjectDiscoveryService->>DatabaseService: Проверяет список обработанных репозиториев
    ProjectDiscoveryService->>ProjectDiscoveryService: Ищет новые алготрейдинговые проекты
    ProjectDiscoveryService->>KafkaTaskManagementService: Отправляет URL нового репозитория
    User->>KafkaTaskManagementService: Отправляет URL репозитория
    KafkaTaskManagementService->>Kafka: Ставит задачу в очередь
    Kafka-->>GitCloningService: Задача на клонирование
    GitCloningService->>DatabaseService: Обновляет статус "Cloning"
    GitCloningService->>GitCloningService: Клонирует репозиторий
    GitCloningService->>DatabaseService: Обновляет статус "Cloned"
    GitCloningService->>FileSelectionService: Передает путь к репозиторию
    FileSelectionService->>FileSelectionService: Отбирает ключевые файлы
    FileSelectionService->>RAGLoadingService: Передает список файлов
    RAGLoadingService->>RAGLoadingService: Загружает файлы в RAG
    RAGLoadingService->>ProjectAnalysisService: Уведомляет о готовности
    ProjectAnalysisService->>ProjectAnalysisService: Проводит анализ
    ProjectAnalysisService->>DatabaseService: Сохраняет результаты анализа
    DatabaseService-->>User: Выводит результаты
```

### Объяснение работы сервисов:
- **Project Discovery Service** автоматически ищет новые алготрейдинговые проекты, проверяет их наличие в базе данных через **Database Service**, и если проект еще не анализировался, отправляет его URL в **Kafka Task Management Service**.
- **Пользователь (User)** отправляет URL репозитория в **Kafka Task Management Service**.
- **Kafka Task Management Service** добавляет задачу в очередь через **Kafka**.
- **Git Cloning Service** забирает задачу из **Kafka**, обновляет статус в **Database Service** на "Cloning", клонирует репозиторий, затем обновляет статус на "Cloned" и передает путь к репозиторию в **File Selection Service**.
- **File Selection Service** анализирует репозиторий, отбирает ключевые файлы и отправляет их в **RAG Loading Service**.
- **RAG Loading Service** загружает файлы в RAG и уведомляет **Project Analysis Service** о готовности.
- **Project Analysis Service** выполняет анализ данных и сохраняет результаты в **Database Service**.
- **Database Service** хранит результаты и возвращает их пользователю.

Эта диаграмма наглядно демонстрирует поток данных и последовательность действий между сервисами в проекте.