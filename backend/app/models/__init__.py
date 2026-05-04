"""
Регистрирует все SQLAlchemy-модели в Base.metadata.
Импортировать этот пакет перед вызовом Base.metadata.create_all().
"""
# Старые модели (существующая структура)
from app.models.models import (  # noqa: F401
    UserModel, CategoryModel, ProcurementModel,
    ParticipantModel, PaymentModel, ChatMessageModel,
)

# Новые модели (из микросервисов)
from app.models.purchase import PurchaseModel, VotingSessionModel, CandidateModel, VoteModel  # noqa: F401
from app.models.payment import WalletModel, TransactionModel, EscrowAccountModel, CommissionModel  # noqa: F401
from app.models.chat import RoomModel, RoomMemberModel, MessageModel  # noqa: F401
from app.models.reputation import ReviewModel, ComplaintModel, ReputationScoreModel  # noqa: F401
