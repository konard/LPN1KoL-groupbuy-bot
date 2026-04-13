"""
Management command to seed the database with initial category data.

Run with:
    python manage.py seed_categories

The command is idempotent — it will not create duplicate categories.
Use --clear to remove all existing categories first.
"""

from django.core.management.base import BaseCommand

from procurements.models import Category


CATEGORIES = [
    # Top-level categories
    {
        "name": "Продукты питания",
        "description": "Еда, напитки, бакалея",
        "icon": "🍎",
        "children": [
            {"name": "Мёд и пчеловодство", "description": "Натуральный мёд, соты, прополис", "icon": "🍯"},
            {"name": "Молочная продукция", "description": "Молоко, сыр, масло, йогурт", "icon": "🥛"},
            {"name": "Мясо и птица", "description": "Говядина, свинина, курица, индейка", "icon": "🥩"},
            {"name": "Рыба и морепродукты", "description": "Рыба, креветки, кальмары", "icon": "🐟"},
            {"name": "Овощи и фрукты", "description": "Свежие овощи, фрукты, зелень", "icon": "🥦"},
            {"name": "Крупы и зерновые", "description": "Рис, гречка, пшеница, кукуруза", "icon": "🌾"},
            {"name": "Чай и кофе", "description": "Листовой чай, кофе в зёрнах", "icon": "☕"},
            {"name": "Снеки и сладости", "description": "Орехи, сухофрукты, конфеты", "icon": "🍫"},
        ],
    },
    {
        "name": "Товары для дома",
        "description": "Бытовая химия, хозяйственные товары",
        "icon": "🏠",
        "children": [
            {"name": "Бытовая химия", "description": "Моющие средства, стиральные порошки", "icon": "🧴"},
            {"name": "Текстиль", "description": "Постельное бельё, полотенца, шторы", "icon": "🛏️"},
            {"name": "Посуда и кухня", "description": "Кастрюли, сковороды, столовые приборы", "icon": "🍳"},
            {"name": "Инструменты", "description": "Ручной и электрический инструмент", "icon": "🔧"},
        ],
    },
    {
        "name": "Одежда и обувь",
        "description": "Одежда, обувь, аксессуары",
        "icon": "👗",
        "children": [
            {"name": "Женская одежда", "description": "Платья, блузки, юбки, джинсы", "icon": "👚"},
            {"name": "Мужская одежда", "description": "Рубашки, брюки, куртки", "icon": "👔"},
            {"name": "Детская одежда", "description": "Одежда для детей всех возрастов", "icon": "👶"},
            {"name": "Обувь", "description": "Туфли, кроссовки, сапоги, ботинки", "icon": "👟"},
            {"name": "Аксессуары", "description": "Сумки, ремни, шарфы, перчатки", "icon": "👜"},
        ],
    },
    {
        "name": "Электроника",
        "description": "Гаджеты, техника, комплектующие",
        "icon": "📱",
        "children": [
            {"name": "Смартфоны и планшеты", "description": "Телефоны, планшеты, аксессуары", "icon": "📱"},
            {"name": "Компьютеры", "description": "Ноутбуки, комплектующие, периферия", "icon": "💻"},
            {"name": "Бытовая техника", "description": "Холодильники, стиральные машины, пылесосы", "icon": "📟"},
            {"name": "Освещение", "description": "Лампы, светильники, LED-ленты", "icon": "💡"},
        ],
    },
    {
        "name": "Косметика и здоровье",
        "description": "Уходовая косметика, медикаменты, витамины",
        "icon": "💄",
        "children": [
            {"name": "Уход за лицом", "description": "Кремы, маски, сыворотки", "icon": "🧖"},
            {"name": "Уход за телом", "description": "Лосьоны, скрабы, мыло", "icon": "🧴"},
            {"name": "Витамины и добавки", "description": "БАДы, витаминные комплексы", "icon": "💊"},
            {"name": "Спорт и фитнес", "description": "Спортивное питание, инвентарь", "icon": "🏋️"},
        ],
    },
    {
        "name": "Детские товары",
        "description": "Игрушки, товары для новорождённых, школьные принадлежности",
        "icon": "🧸",
        "children": [
            {"name": "Игрушки", "description": "Развивающие игры, конструкторы, куклы", "icon": "🎮"},
            {"name": "Товары для новорождённых", "description": "Памперсы, питание, коляски", "icon": "🍼"},
            {"name": "Школьные принадлежности", "description": "Тетради, ручки, рюкзаки", "icon": "📒"},
        ],
    },
    {
        "name": "Сад и огород",
        "description": "Семена, рассада, удобрения, садовый инвентарь",
        "icon": "🌱",
        "children": [
            {"name": "Семена и рассада", "description": "Овощи, цветы, ягоды", "icon": "🌿"},
            {"name": "Удобрения", "description": "Минеральные и органические удобрения", "icon": "🌱"},
            {"name": "Садовый инвентарь", "description": "Лопаты, грабли, шланги", "icon": "⛏️"},
        ],
    },
    {
        "name": "Строительство и ремонт",
        "description": "Стройматериалы, инструменты, отделочные материалы",
        "icon": "🏗️",
        "children": [
            {"name": "Стройматериалы", "description": "Кирпич, цемент, доска, арматура", "icon": "🧱"},
            {"name": "Отделочные материалы", "description": "Обои, плитка, ламинат, краска", "icon": "🎨"},
            {"name": "Сантехника", "description": "Трубы, краны, унитазы, ванны", "icon": "🚿"},
        ],
    },
    {
        "name": "Автотовары",
        "description": "Автозапчасти, масла, аксессуары",
        "icon": "🚗",
        "children": [
            {"name": "Шины и диски", "description": "Летние и зимние шины, диски", "icon": "🔄"},
            {"name": "Автохимия", "description": "Масла, антифризы, автомойка", "icon": "🛢️"},
            {"name": "Автоаксессуары", "description": "Коврики, чехлы, ароматизаторы", "icon": "🚙"},
        ],
    },
    {
        "name": "Прочее",
        "description": "Товары, не вошедшие в другие категории",
        "icon": "📦",
        "children": [],
    },
]


class Command(BaseCommand):
    help = "Seed the database with initial procurement categories"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove all existing categories before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            count = Category.objects.count()
            Category.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f"Deleted {count} existing categories.")
            )

        created_count = 0
        skipped_count = 0

        for cat_data in CATEGORIES:
            children = cat_data.get("children", [])

            parent, created = Category.objects.get_or_create(
                name=cat_data["name"],
                parent=None,
                defaults={
                    "description": cat_data.get("description", ""),
                    "icon": cat_data.get("icon", ""),
                    "is_active": True,
                },
            )

            if created:
                created_count += 1
                self.stdout.write(f"  Created category: {parent.name}")
            else:
                skipped_count += 1
                self.stdout.write(f"  Skipped (exists): {parent.name}")

            for child_data in children:
                child, child_created = Category.objects.get_or_create(
                    name=child_data["name"],
                    parent=parent,
                    defaults={
                        "description": child_data.get("description", ""),
                        "icon": child_data.get("icon", ""),
                        "is_active": True,
                    },
                )

                if child_created:
                    created_count += 1
                    self.stdout.write(f"    Created subcategory: {child.name}")
                else:
                    skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Created {created_count} categories, "
                f"skipped {skipped_count} existing."
            )
        )
