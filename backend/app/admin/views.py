from sqladmin import Admin, ModelView

from app.models.models import CategoryModel, ChatMessageModel, ParticipantModel, PaymentModel, ProcurementModel, UserModel


class UserAdmin(ModelView, model=UserModel):
    column_list = [UserModel.id, UserModel.username, UserModel.email, UserModel.is_active, UserModel.is_admin, UserModel.balance, UserModel.created_at]
    column_searchable_list = [UserModel.username, UserModel.email]
    column_sortable_list = [UserModel.id, UserModel.username, UserModel.created_at]
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"


class CategoryAdmin(ModelView, model=CategoryModel):
    column_list = [CategoryModel.id, CategoryModel.name, CategoryModel.is_active, CategoryModel.created_at]
    column_searchable_list = [CategoryModel.name]
    name = "Category"
    name_plural = "Categories"
    icon = "fa-solid fa-tag"


class ProcurementAdmin(ModelView, model=ProcurementModel):
    column_list = [ProcurementModel.id, ProcurementModel.title, ProcurementModel.status, ProcurementModel.target_amount, ProcurementModel.current_amount, ProcurementModel.deadline, ProcurementModel.created_at]
    column_searchable_list = [ProcurementModel.title, ProcurementModel.city]
    column_sortable_list = [ProcurementModel.id, ProcurementModel.created_at, ProcurementModel.status]
    name = "Procurement"
    name_plural = "Procurements"
    icon = "fa-solid fa-box"


class PaymentAdmin(ModelView, model=PaymentModel):
    column_list = [PaymentModel.id, PaymentModel.user_id, PaymentModel.payment_type, PaymentModel.amount, PaymentModel.status, PaymentModel.created_at]
    column_sortable_list = [PaymentModel.id, PaymentModel.created_at]
    name = "Payment"
    name_plural = "Payments"
    icon = "fa-solid fa-credit-card"


class ParticipantAdmin(ModelView, model=ParticipantModel):
    column_list = [ParticipantModel.id, ParticipantModel.procurement_id, ParticipantModel.user_id, ParticipantModel.quantity, ParticipantModel.amount, ParticipantModel.status, ParticipantModel.joined_at]
    name = "Participant"
    name_plural = "Participants"
    icon = "fa-solid fa-users"


def setup_admin(app, engine):
    admin = Admin(app, engine, title="GroupBuy Admin")
    admin.add_view(UserAdmin)
    admin.add_view(CategoryAdmin)
    admin.add_view(ProcurementAdmin)
    admin.add_view(PaymentAdmin)
    admin.add_view(ParticipantAdmin)
    return admin
