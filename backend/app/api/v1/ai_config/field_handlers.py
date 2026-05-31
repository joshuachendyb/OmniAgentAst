from typing import Dict, Any
from ._update_provider import _update_provider
from ._update_model import _update_model
from ._update_api_keys import _update_api_keys
from ._update_theme import _update_theme
from ._update_language import _update_language
from ._update_max_steps import _update_max_steps
from ._update_security import _update_security


FIELD_HANDLERS: Dict[str, Any] = {
    "ai_provider": _update_provider,
    "ai_model": _update_model,
    "provider_api_keys": _update_api_keys,
    "theme": _update_theme,
    "language": _update_language,
    "max_steps": _update_max_steps,
    "security": _update_security,
}
