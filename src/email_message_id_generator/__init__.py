"""Email Message ID Generator.

A focused library for producing RFC 5322 compliant Message-ID headers.
"""

from email_message_id_generator.core import (
    MessageIDGenerator,
    DEFAULT_DOMAIN_POLICY,
    DEFAULT_CLOCK,
)

__all__ = [
    "MessageIDGenerator",
    "DEFAULT_DOMAIN_POLICY",
    "DEFAULT_CLOCK",
]

__version__ = "1.0.0"
