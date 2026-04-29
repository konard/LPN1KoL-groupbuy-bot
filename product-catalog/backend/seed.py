from sqlalchemy.orm import Session

from logging_setup import logger
from models import ProductModel, UserRole
from repositories import CategoryRepository, ProductRepository, UserRepository


def seed_data(db: Session):
    repo_cat = CategoryRepository(db)
    repo_prod = ProductRepository(db)
    repo_user = UserRepository(db)

    if not repo_user.get_by_username("admin"):
        repo_user.create("admin", "admin123", UserRole.admin)
        logger.info("Created default admin user (username=admin, password=admin123)")

    if not repo_user.get_by_username("advanced"):
        repo_user.create("advanced", "advanced123", UserRole.advanced_user)

    if not repo_user.get_by_username("user"):
        repo_user.create("user", "user123", UserRole.simple_user)

    seed_products = [
        ("Еда", [
            ("Селедка", "Селедка соленая", 10.0, "Акция", "Пересоленая"),
            ("Тушенка", "Тушенка говяжья", 20.0, "Вкусная", "Жилы"),
        ]),
        ("Вкусности", [
            ("Сгущенка", "В банках", 30.0, "С ключом", "Вкусная"),
        ]),
        ("Вода", [
            ("Квас", "В бутылках", 15.0, "Вятский", "Теплый"),
        ]),
    ]

    for cat_name, products in seed_products:
        cat = repo_cat.get_by_name(cat_name)
        if not cat:
            cat = repo_cat.create(cat_name)
        for name, desc, price, gnote, snote in products:
            existing = db.query(ProductModel).filter(
                ProductModel.name == name, ProductModel.category_id == cat.id
            ).first()
            if not existing:
                repo_prod.create({
                    "name": name,
                    "description": desc,
                    "price_rub": price,
                    "general_note": gnote,
                    "special_note": snote,
                    "category_id": cat.id,
                })
