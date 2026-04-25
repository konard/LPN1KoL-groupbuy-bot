from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "mapsoft-platform"


REQUIRED_FILES = [
    "README.md",
    "composer.json",
    "package.json",
    "package-lock.json",
    "index.html",
    "vite.config.js",
    ".env.example",
    ".gitlab-ci.yml",
    "docker-compose.yml",
    "Makefile",
    "phpstan.neon",
    "phpunit.xml",
    "docker/php/Dockerfile",
    "docker/nginx/default.conf",
    "routes/api.php",
    "routes/web.php",
    "app/Contracts/Repositories/UserReaderInterface.php",
    "app/Contracts/Repositories/UserWriterInterface.php",
    "app/Contracts/Repositories/ReadingReaderInterface.php",
    "app/Contracts/Repositories/ReadingWriterInterface.php",
    "app/Contracts/Repositories/BillReaderInterface.php",
    "app/Contracts/Repositories/BillWriterInterface.php",
    "app/Contracts/Repositories/TariffReaderInterface.php",
    "app/Contracts/Repositories/NotificationLogWriterInterface.php",
    "app/Contracts/Infrastructure/CacheInterface.php",
    "app/Contracts/Infrastructure/MessageBrokerInterface.php",
    "app/Contracts/Infrastructure/HttpClientInterface.php",
    "app/Contracts/Infrastructure/TransactionManagerInterface.php",
    "app/Contracts/ReadingPipelineStageInterface.php",
    "app/Contracts/NotificationHandlerInterface.php",
    "app/Contracts/TariffCalculatorInterface.php",
    "app/Contracts/BillGeneratorInterface.php",
    "app/DTO/UserDTO.php",
    "app/DTO/CreateUserDTO.php",
    "app/DTO/ReadingDTO.php",
    "app/DTO/CreateReadingDTO.php",
    "app/DTO/ReadingFilterDTO.php",
    "app/DTO/TariffDTO.php",
    "app/DTO/BillDTO.php",
    "app/DTO/BillItemDTO.php",
    "app/DTO/BillFilterDTO.php",
    "app/DTO/CreateBillDTO.php",
    "app/DTO/MoneyDTO.php",
    "app/DTO/NotificationDTO.php",
    "app/Enums/ReadingType.php",
    "app/Enums/BillStatus.php",
    "app/Enums/NotificationChannel.php",
    "app/Enums/NotificationType.php",
    "app/Enums/Permission.php",
    "app/Enums/Currency.php",
    "app/Repositories/EloquentUserRepository.php",
    "app/Repositories/EloquentReadingRepository.php",
    "app/Repositories/EloquentBillRepository.php",
    "app/Repositories/EloquentTariffRepository.php",
    "app/Repositories/EloquentNotificationLogRepository.php",
    "app/Services/ReadingPipelineService.php",
    "app/Services/BillingService.php",
    "app/Services/BillGeneratorService.php",
    "app/Services/TariffCalculatorService.php",
    "app/Services/NotificationDispatchService.php",
    "app/Services/UserService.php",
    "app/Services/HealthCheckService.php",
    "app/Pipelines/Stages/ValidateReadingStage.php",
    "app/Pipelines/Stages/NormalizeReadingStage.php",
    "app/Pipelines/Stages/EnrichReadingStage.php",
    "app/Pipelines/Stages/PersistReadingStage.php",
    "app/Infrastructure/RedisCache.php",
    "app/Infrastructure/RabbitMQBroker.php",
    "app/Infrastructure/HttpGuzzleClient.php",
    "app/Infrastructure/DatabaseTransactionManager.php",
    "app/Providers/RepositoryServiceProvider.php",
    "app/Providers/InfrastructureServiceProvider.php",
    "app/Providers/PipelineServiceProvider.php",
    "app/Providers/NotificationServiceProvider.php",
    "app/Http/Controllers/ReadingController.php",
    "app/Http/Controllers/BillController.php",
    "app/Http/Controllers/StatsController.php",
    "app/Http/Controllers/TariffController.php",
    "app/Http/Controllers/HealthController.php",
    "app/Http/Requests/StoreReadingRequest.php",
    "app/Http/Requests/HistoryReadingRequest.php",
    "app/Http/Resources/ReadingResource.php",
    "app/Http/Resources/BillResource.php",
    "app/Http/Resources/StatsResource.php",
    "app/Http/Resources/TariffResource.php",
    "app/Jobs/CalculateMonthlyBills.php",
    "app/Jobs/SendOverdueNotification.php",
    "app/Console/Commands/ImportReadingsCommand.php",
    "app/Console/Commands/CalculateBillsCommand.php",
    "app/Exceptions/Handler.php",
    "resources/js/Components/UserDashboard.vue",
    "resources/js/app.js",
    "resources/views/app.blade.php",
    "tests/Feature/ReadingApiTest.php",
    "tests/Unit/BillingServiceTest.php",
    "tests/Unit/ReadingPipelineServiceTest.php",
]


def read(path: str) -> str:
    return (APP / path).read_text(encoding="utf-8")


def test_issue_93_mapsoft_platform_required_files_exist():
    missing = [path for path in REQUIRED_FILES if not (APP / path).is_file()]

    assert missing == []


def test_issue_93_mapsoft_platform_declares_laravel_vue_and_infrastructure_stack():
    composer = read("composer.json")
    package = read("package.json")
    compose = read("docker-compose.yml")
    gitlab = read(".gitlab-ci.yml")

    for dependency in [
        '"laravel/framework": "^9.0"',
        '"filament/filament": "^3.0"',
        '"webmozart/assert"',
        '"guzzlehttp/guzzle"',
        '"php-amqplib/php-amqplib"',
    ]:
        assert dependency in composer

    for dependency in ['"vue"', '"chart.js"', '"axios"', '"vite"']:
        assert dependency in package

    for service in ["postgres", "redis", "rabbitmq", "nginx", "app", "worker", "scheduler"]:
        assert service in compose

    for stage in ["test", "build", "deploy"]:
        assert stage in gitlab


def test_issue_93_api_routes_and_services_match_requested_contracts():
    routes = read("routes/api.php")
    billing = read("app/Services/BillingService.php")
    pipeline = read("app/Services/ReadingPipelineService.php")
    notifications = read("app/Services/NotificationDispatchService.php")
    providers = "\n".join(
        read(path)
        for path in [
            "app/Providers/RepositoryServiceProvider.php",
            "app/Providers/InfrastructureServiceProvider.php",
            "app/Providers/PipelineServiceProvider.php",
            "app/Providers/NotificationServiceProvider.php",
        ]
    )

    for endpoint in [
        "Route::post('/readings'",
        "Route::get('/readings/history'",
        "Route::get('/bills'",
        "Route::get('/bills/{uuid}'",
        "Route::get('/stats/monthly'",
        "Route::get('/tariffs'",
        "Route::get('/health'",
    ]:
        assert endpoint in routes

    assert "ReadingReaderInterface" in billing
    assert "TariffReaderInterface" in billing
    assert "TariffCalculatorInterface" in billing
    assert "BillGeneratorInterface" in billing
    assert "BillWriterInterface" in billing
    assert "TransactionManagerInterface" in billing
    assert "array_reduce" in pipeline
    assert "ReadingPipelineStageInterface" in pipeline
    assert "NotificationHandlerInterface" in notifications
    assert "NotificationLogWriterInterface" in notifications
    assert "$this->app->bind" in providers
    assert "$this->app->tag" in providers


def test_issue_93_php_application_code_uses_final_classes_and_avoids_comments():
    failures = []

    for path in (APP / "app").rglob("*.php"):
        content = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT)
        if "interface " not in content and "enum " not in content and "final class " not in content:
            failures.append(f"{relative}: missing final class")

        for line_number, line in enumerate(content.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith(("//", "/*", "*", "#")):
                failures.append(f"{relative}:{line_number}: comment")
                break

    assert failures == []
