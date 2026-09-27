"""Core implementation of RFC 5322 compliant Message-ID generation.

Design decisions, stated plainly:

- We pick ONE scheme: every Message-ID is of the form
      <{timestamp_in_ms}-{counter}-{secret}@{domain}>
  The counter is a per-generator monotonically increasing integer padded to a
  fixed width so that lexicographic ordering of IDs from the same generator
  matches creation order within the same millisecond. The secret is 128 bits
  of os.urandom hex-encoded. The timestamp is the clock's milliseconds since
  the Unix epoch.

- We do NOT attempt to satisfy multiple competing formats. No UUID, no
  hostname-encoding, no left-at-sign schemes. One scheme, tested.

- The clock is injected (default: time.monotonic is NOT used; we need real
  wall-clock ms for the timestamp segment, so the default is time.time). Tests
  pass a fake clock and get deterministic output.

- Domain validation: we accept a domain string only after stripping whitespace
  and confirming it contains exactly one '@'-free non-empty label, with a dot
  in the middle or a single-label form. We reject domains containing '(', ')',
  '<', '>', ',', ';', ':', '\\', '"', '@', or any control byte. The complete
  list is in _FORBIDDEN_DOMAIN_CHARS. We deliberately keep this conservative;
  a stricter validator is the caller's job.
"""

from __future__ import annotations

import os
import re
import time
from typing import Callable, Optional

# Default clock: returns Unix epoch seconds as a float, matching time.time.
DEFAULT_CLOCK: Callable[[], float] = time.time

# Default domain policy: if the caller does not supply a domain, we fall back
# to 'localhost'. This is not a resolvable domain, but it is syntactically
# legal per RFC 5322 \"domain\" production and makes the generator usable in
# contexts without configuration. The README documents this explicitly.
DEFAULT_DOMAIN_POLICY: str = "localhost"

# Characters forbidden in the domain literal per RFC 5322. We keep this list
# conservative so that a caller-supplied domain cannot break the Message-ID
# format by embedding specials.
_FORBIDDEN_DOMAIN_CHARS = frozenset(
    '()<>@,;:\\\"[]'
)

# Domain sanity regex: labels of 1-63 chars of [A-Za-z0-9-], separated by dots,
# total length 1-253. A single trailing dot is tolerated (FQDN form). We also
# accept 'localhost' (a single label). This is deliberately simple.
_DOMAIN_RE = re.compile(
    r'^(?=.{1,253}$)'
    r'(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*\.?$'
)


class MessageIDGenerator:
    """Generate RFC 5322 compliant, globally-unique Message-ID headers.

    Each call to :meth:`generate` returns a string of the form::

        <{ms}-{counter:08d}-{secret}@{domain}>

    where ``ms`` is the wall-clock millisecond timestamp from the injected
    clock, ``counter`` is a per-generator 8-digit zero-padded incrementing
    integer, and ``secret`` is 32 hex characters (128 bits) from os.urandom.

    Parameters
    ----------
    domain:
        Domain to place after the '@'. If None, falls back to
        :data:`DEFAULT_DOMAIN_POLICY` ("localhost").
    clock:
        Callable returning Unix epoch seconds as a float. Default is
        :data:`DEFAULT_CLOCK` (``time.time``). Inject a fake for deterministic
        tests.

    Raises
    ------
    ValueError
        If ``domain`` is supplied but not a syntactically valid domain.
    """

    def __init__(
        self,
        domain: Optional[str] = None,
        clock: Callable[[], float] = DEFAULT_CLOCK,
    ) -> None:
        self._clock = clock
        if domain is None:
            self._domain = DEFAULT_DOMAIN_POLICY
        else:
            self._domain = self._validate_domain(domain)
        # 64-bit counter is plenty; we never expect to wrap in any realistic
        # session. Wrapping would still produce unique IDs because the secret
        # changes per call, but ordering within a millisecond would break.
        self._counter: int = 0

    @staticmethod
    def _validate_domain(domain: str) -> str:
        if not isinstance(domain, str):  # type: ignore[unreachable]
            raise ValueError(f"domain must be a string, got {type(domain).__name__}")
        stripped = domain.strip()
        if not stripped:
            raise ValueError("domain must not be empty or whitespace-only")
        if any(c in _FORBIDDEN_DOMAIN_CHARS for c in stripped):
            raise ValueError(
                "domain contains characters forbidden by RFC 5322"
            )
        if any(ord(c) < 32 or ord(c) == 127 for c in stripped):
            raise ValueError("domain contains control characters")
        if not _DOMAIN_RE.match(stripped):
            raise ValueError(f"invalid domain syntax: {domain!r}")
        return stripped

    @staticmethod
    def _make_secret() -> str:
        # 16 bytes = 128 bits of entropy, hex-encoded to 32 chars. RFC 5322
        # local-part is allowed to contain these characters unquoted under
        # dot-atom rules. We use lowercase hex for compactness.
        return os.urandom(16).hex()

    def generate(self) -> str:
        """Return a new, globally-unique Message-ID string.

        The returned value includes the surrounding angle brackets, e.g.::

            <1716940800000-00000001-a1b2...@example.org>

        Uniqueness across processes is provided by the random secret; ordering
        within a single generator instance within the same millisecond is
        provided by the counter.
        """
        seconds = self._clock()
        # We floor to milliseconds so that two calls in the same millisecond
        # produce the same timestamp segment; the counter then disambiguates
        # them. Using int() truncates toward zero, which is fine for positive
        # epoch values.
        ms = int(seconds * 1000)
        self._counter += 1
        secret = self._make_secret()
        return f"<{ms}-{self._counter:08d}-{secret}@{self._domain}>"

    @property
    def domain(self) -> str:
        """Return the configured domain string (post-validation)."""
        return self._domain
