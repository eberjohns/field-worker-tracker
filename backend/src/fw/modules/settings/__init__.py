"""Public interface for settings module."""

from fw.modules.settings.models import CompanySettingValue
from fw.modules.settings.service import SettingsService

__all__ = [
    "CompanySettingValue",
    "SettingsService",
]
