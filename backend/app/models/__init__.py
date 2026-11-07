"""Database models (SQLAlchemy tables) for SMART Wi-Fi AutoPay.

Importing this package registers all 16 tables on Base.metadata. Alembic
and the tests import it so they see the complete schema.

Note: the model for the "sessions" table is named Session. It is not
related to sqlalchemy.orm.Session; always import it from this package
(or app.models.session) so the two are never mixed up.
"""

from app.db.base import Base
from app.models.admin_user import AdminUser
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.device import Device
from app.models.device_enrollment_request import DeviceEnrollmentRequest
from app.models.entitlement import Entitlement
from app.models.health_event import HealthEvent
from app.models.package import Package
from app.models.payment import Payment
from app.models.pricing_rule import PricingRule
from app.models.security_event import SecurityEvent
from app.models.session import Session
from app.models.session_device import SessionDevice
from app.models.sharing_warning import SharingWarning
from app.models.site import Site
from app.models.system_setting import SystemSetting

__all__ = [
    "AdminUser",
    "AuditLog",
    "Base",
    "Customer",
    "Device",
    "DeviceEnrollmentRequest",
    "Entitlement",
    "HealthEvent",
    "Package",
    "Payment",
    "PricingRule",
    "SecurityEvent",
    "Session",
    "SessionDevice",
    "SharingWarning",
    "Site",
    "SystemSetting",
]
