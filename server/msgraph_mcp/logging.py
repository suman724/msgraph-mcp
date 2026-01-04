import logging
import sys
from typing import Any, Dict

import structlog


def _add_app_context(_: Any, __: Any, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    event_dict.setdefault("service", "msgraph-mcp")
    return event_dict


def configure_logging() -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            timestamper,
            _add_app_context,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
