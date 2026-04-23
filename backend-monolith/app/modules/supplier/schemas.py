import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class CompanyCardCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255, description="Полное наименование компании", example="ООО «Торговый Дом»")
    legal_address: str = Field(..., min_length=1, description="Юридический адрес компании", example="г. Москва, ул. Ленина, д. 1")
    postal_address: str = Field(..., min_length=1, description="Почтовый адрес компании", example="127000, г. Москва, а/я 10")
    actual_address: str = Field(..., min_length=1, description="Фактический адрес компании", example="г. Москва, ул. Ленина, д. 1, офис 5")
    okved: str = Field(..., min_length=1, max_length=20, description="Код ОКВЭД", example="46.90")
    ogrn: str = Field(..., min_length=13, max_length=15, description="ОГРН (13 или 15 цифр)", example="1027700132195")
    inn: str = Field(..., min_length=10, max_length=12, description="ИНН (10 или 12 цифр)", example="7700000001")
    phone: str = Field(..., min_length=7, max_length=30, description="Контактный телефон", example="+7 (495) 123-45-67")
    email: EmailStr = Field(..., description="Электронная почта компании", example="info@company.ru")

    model_config = {
        "json_schema_extra": {
            "example": {
                "company_name": "ООО «Торговый Дом»",
                "legal_address": "г. Москва, ул. Ленина, д. 1",
                "postal_address": "127000, г. Москва, а/я 10",
                "actual_address": "г. Москва, ул. Ленина, д. 1, офис 5",
                "okved": "46.90",
                "ogrn": "1027700132195",
                "inn": "7700000001",
                "phone": "+7 (495) 123-45-67",
                "email": "info@company.ru",
            }
        }
    }


class CompanyCardUpdate(BaseModel):
    company_name: str | None = Field(None, min_length=1, max_length=255, description="Полное наименование компании")
    legal_address: str | None = Field(None, min_length=1, description="Юридический адрес")
    postal_address: str | None = Field(None, min_length=1, description="Почтовый адрес")
    actual_address: str | None = Field(None, min_length=1, description="Фактический адрес")
    okved: str | None = Field(None, min_length=1, max_length=20, description="Код ОКВЭД")
    ogrn: str | None = Field(None, min_length=13, max_length=15, description="ОГРН")
    inn: str | None = Field(None, min_length=10, max_length=12, description="ИНН")
    phone: str | None = Field(None, min_length=7, max_length=30, description="Контактный телефон")
    email: EmailStr | None = Field(None, description="Электронная почта")


class CompanyCardOut(BaseModel):
    id: uuid.UUID = Field(..., description="Идентификатор карты компании")
    supplier_id: uuid.UUID = Field(..., description="Идентификатор поставщика")
    company_name: str = Field(..., description="Полное наименование компании")
    legal_address: str = Field(..., description="Юридический адрес")
    postal_address: str = Field(..., description="Почтовый адрес")
    actual_address: str = Field(..., description="Фактический адрес")
    okved: str = Field(..., description="Код ОКВЭД")
    ogrn: str = Field(..., description="ОГРН")
    inn: str = Field(..., description="ИНН")
    phone: str = Field(..., description="Контактный телефон")
    email: str = Field(..., description="Электронная почта")
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: datetime = Field(..., description="Дата обновления")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "supplier_id": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
                "company_name": "ООО «Торговый Дом»",
                "legal_address": "г. Москва, ул. Ленина, д. 1",
                "postal_address": "127000, г. Москва, а/я 10",
                "actual_address": "г. Москва, ул. Ленина, д. 1, офис 5",
                "okved": "46.90",
                "ogrn": "1027700132195",
                "inn": "7700000001",
                "phone": "+7 (495) 123-45-67",
                "email": "info@company.ru",
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-01T12:00:00Z",
            }
        },
    }


class PriceListOut(BaseModel):
    id: uuid.UUID = Field(..., description="Идентификатор прайс-листа")
    supplier_id: uuid.UUID = Field(..., description="Идентификатор поставщика")
    file_url: str = Field(..., description="Ссылка на файл прайс-листа")
    file_name: str = Field(..., description="Имя файла")
    popular_items: str | None = Field(None, description="Список популярных товаров (до 20 позиций)")
    is_active: bool = Field(..., description="Прайс-лист активен")
    created_at: datetime = Field(..., description="Дата загрузки")
    updated_at: datetime = Field(..., description="Дата обновления")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "supplier_id": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
                "file_url": "/uploads/pricelists/priceList_2024.xlsx",
                "file_name": "priceList_2024.xlsx",
                "popular_items": "Мука пшеничная — 50 руб/кг; Сахар — 45 руб/кг",
                "is_active": True,
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-01T12:00:00Z",
            }
        },
    }


class ClosingDocumentOut(BaseModel):
    id: uuid.UUID = Field(..., description="Идентификатор документа")
    supplier_id: uuid.UUID = Field(..., description="Идентификатор поставщика")
    purchase_id: uuid.UUID = Field(..., description="Идентификатор закупки")
    file_url: str = Field(..., description="Ссылка на файл документа")
    file_name: str = Field(..., description="Имя файла")
    comment: str | None = Field(None, description="Комментарий для покупателей")
    created_at: datetime = Field(..., description="Дата отправки")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "supplier_id": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
                "purchase_id": "3fa85f64-5717-4562-b3fc-2c963f66afa8",
                "file_url": "/uploads/documents/act_2024.pdf",
                "file_name": "act_2024.pdf",
                "comment": "Акт выполненных работ за январь 2024",
                "created_at": "2024-01-01T12:00:00Z",
            }
        },
    }
