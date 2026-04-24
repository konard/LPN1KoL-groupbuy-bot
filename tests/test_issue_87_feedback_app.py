from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "feedback-form-laravel-vue"


def read(path: str) -> str:
    return (APP / path).read_text(encoding="utf-8")


def test_issue_87_feedback_app_structure_exists():
    expected_files = [
        "README.md",
        "composer.json",
        "index.html",
        "package.json",
        "vite.config.js",
        "routes/api.php",
        "app/Http/Controllers/FeedbackController.php",
        "app/Services/Feedback/FeedbackStorageFactory.php",
        "app/Services/Feedback/FeedbackStorageInterface.php",
        "app/Services/Feedback/DatabaseFeedbackStorage.php",
        "app/Services/Feedback/EmailFeedbackStorage.php",
        "resources/js/app.js",
        "resources/js/router.js",
        "resources/js/store.js",
        "resources/js/pages/FeedbackForm.vue",
        "resources/js/pages/FeedbackList.vue",
    ]

    missing = [path for path in expected_files if not (APP / path).is_file()]

    assert missing == []


def test_issue_87_backend_uses_factory_for_feedback_save():
    routes = read("routes/api.php")
    controller = read("app/Http/Controllers/FeedbackController.php")
    factory = read("app/Services/Feedback/FeedbackStorageFactory.php")
    interface = read("app/Services/Feedback/FeedbackStorageInterface.php")

    assert "Route::post('/feedback'" in routes
    assert "FeedbackController::class" in routes
    assert "FeedbackStorageFactory" in controller
    assert "->save(" in controller
    assert "function save(array $feedback): void" in interface
    assert "switch ($driver)" in factory
    assert "database" in factory
    assert "email" in factory


def test_issue_87_frontend_uses_vuex_and_vue_router_pages():
    app_js = read("resources/js/app.js")
    router = read("resources/js/router.js")
    store = read("resources/js/store.js")
    form = read("resources/js/pages/FeedbackForm.vue")
    listing = read("resources/js/pages/FeedbackList.vue")

    assert "createApp" in app_js
    assert ".use(store)" in app_js
    assert ".use(router)" in app_js
    assert "createRouter" in router
    assert "createWebHistory" in router
    assert "FeedbackForm" in router
    assert "FeedbackList" in router
    assert "createStore" in store
    assert "addFeedback" in store
    assert "axios.post('/api/feedback'" in form
    assert "$store.commit('addFeedback'" in form
    assert "$store.state.feedbackItems" in listing
