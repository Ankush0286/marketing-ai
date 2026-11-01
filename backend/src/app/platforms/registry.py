import logging
from typing import ClassVar

from app.common.enums import PlatformType
from app.modules.accounts.models import ConnectedAccount
from app.platforms.base import BasePlatformAdapter
from app.platforms.instagram.adapter import InstagramAdapter
from app.platforms.twitter.adapter import TwitterAdapter

logger = logging.getLogger(__name__)


class UnsupportedPlatformError(Exception):
    """Raised when an adapter is requested for an unregistered platform."""


class PlatformRegistry:
    """
    Central factory resolving ConnectedAccount records into their matching
    platform automation adapters.
    """

    _registry: ClassVar[dict[PlatformType, type[BasePlatformAdapter]]] = {}

    @classmethod
    def register(
        cls,
        platform: PlatformType,
        adapter_cls: type[BasePlatformAdapter],
    ) -> None:
        """Registers an adapter implementation class for a specific platform."""
        cls._registry[platform] = adapter_cls
        logger.debug("Registered platform adapter '%s' -> %s", platform.value, adapter_cls.__name__)

    @classmethod
    def get_adapter(cls, account: ConnectedAccount, **kwargs: object) -> BasePlatformAdapter:
        """Instantiates and returns the appropriate adapter for a ConnectedAccount."""
        adapter_cls = cls._registry.get(account.platform)
        if not adapter_cls:
            raise UnsupportedPlatformError(
                f"No automation adapter registered for platform '{account.platform.value}'."
            )
        return adapter_cls(account, **kwargs)

    @classmethod
    def is_supported(cls, platform: PlatformType) -> bool:
        """Checks if a platform adapter is registered."""
        return platform in cls._registry


# ---------- Built-in Platform Registrations ----------

PlatformRegistry.register(PlatformType.INSTAGRAM, InstagramAdapter)
PlatformRegistry.register(PlatformType.TWITTER, TwitterAdapter)
