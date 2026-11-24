"""All ORM models. Importing this module registers every table on Base.metadata."""

from app.db.models.catalog import Cart, CartItem, Category, Product, ProductImage
from app.db.models.ops import (
    AdminAuditLog,
    Broadcast,
    BroadcastTarget,
    Job,
    Setting,
    SupportMessage,
    SupportThread,
    WalletTransaction,
)
from app.db.models.orders import Order, OrderItem, OrderStatusHistory
from app.db.models.payments import (
    BankTransaction,
    CardBinding,
    PaymentIntent,
    PaymentProof,
    ShopCard,
    SmsMessage,
)
from app.db.models.users import Address, User, UserEvent

__all__ = [
    "User",
    "UserEvent",
    "Address",
    "Category",
    "Product",
    "ProductImage",
    "Cart",
    "CartItem",
    "Order",
    "OrderItem",
    "OrderStatusHistory",
    "PaymentIntent",
    "SmsMessage",
    "BankTransaction",
    "ShopCard",
    "PaymentProof",
    "CardBinding",
    "WalletTransaction",
    "AdminAuditLog",
    "Broadcast",
    "BroadcastTarget",
    "SupportThread",
    "SupportMessage",
    "Job",
    "Setting",
]
