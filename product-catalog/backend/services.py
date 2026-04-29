from models import ProductModel, UserRole
from schemas import ProductOut, ProductOutSimple


def build_product_out(p: ProductModel, include_special: bool = True):
    base = {
        "id": p.id,
        "name": p.name,
        "description": p.description or "",
        "price_rub": p.price_rub,
        "general_note": p.general_note or "",
        "category_id": p.category_id,
        "category_name": p.category.name if p.category else "",
    }
    if include_special:
        base["special_note"] = p.special_note or ""
        return ProductOut(**base)
    return ProductOutSimple(**base)


def has_special_access(role: UserRole) -> bool:
    return role in (UserRole.advanced_user, UserRole.admin)
