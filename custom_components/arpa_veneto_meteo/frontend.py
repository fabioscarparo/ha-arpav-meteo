"""Frontend static resource registration for the built-in Lovelace card.

Serves the bundled ES module from the integration package and registers it
with Home Assistant's frontend via `add_extra_js_url` using a content SHA-256
digest query parameter for automatic cache busting across updates.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from homeassistant.core import HomeAssistant

from .const import CARD_FILENAME, CARD_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

_FRONTEND_REGISTERED_KEY = "frontend_registered"
_CARD_FILE_PATH = Path(__file__).parent / "frontend" / CARD_FILENAME


def _compute_card_digest() -> str:
    """Return a short SHA-256 hex digest of the bundled card module."""
    return hashlib.sha256(_CARD_FILE_PATH.read_bytes()).hexdigest()[:12]


async def async_register_frontend(hass: HomeAssistant) -> bool:
    """Register the Lovelace card static path and frontend JS module once."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_FRONTEND_REGISTERED_KEY):
        return False

    http = getattr(hass, "http", None)
    components = getattr(hass.config, "components", set())
    if http is None or "frontend" not in components:
        _LOGGER.debug(
            "Skipping frontend card registration because http or frontend is unavailable"
        )
        return False

    from homeassistant.components.frontend import add_extra_js_url  # noqa: PLC0415
    from homeassistant.components.http import StaticPathConfig  # noqa: PLC0415

    digest = await hass.async_add_executor_job(_compute_card_digest)
    await http.async_register_static_paths(
        [
            StaticPathConfig(
                url_path=CARD_URL,
                path=str(_CARD_FILE_PATH),
                cache_headers=True,
            )
        ]
    )
    add_extra_js_url(hass, f"{CARD_URL}?v={digest}")
    domain_data[_FRONTEND_REGISTERED_KEY] = True
    _LOGGER.debug("Registered ARPA Veneto Meteo Lovelace card at %s?v=%s", CARD_URL, digest)
    return True
