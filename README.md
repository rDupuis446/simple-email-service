# Email Message ID Generator

Generates RFC 5322 compliant Message-ID headers with globally-unique local parts and a caller-configured domain.

## Usage

```python
from email_message_id_generator import MessageIDGenerator

gen = MessageIDGenerator(domain="mail.example.org")
message_id = gen.generate()
# '<1716940800000-00000001-4f3a...@mail.example.org>'
```

For deterministic tests, inject a clock:

```python
from email_message_id_generator import MessageIDGenerator

class FakeClock:
    def __init__(self, t=1_000_000.0):
        self.t = t
    def __call__(self):
        return self.t

gen = MessageIDGenerator(domain="example.org", clock=FakeClock())
print(gen.generate())  # '<1000000000000-00000001-...@example.org>'
```

Exported names: `MessageIDGenerator`, `DEFAULT_DOMAIN_POLICY`, `DEFAULT_CLOCK`.

## Why this exists

Generating a Message-ID looks trivial until you need global uniqueness across
concurrent processes without a central coordinator. The scheme chosen here is
`<{ms}-{counter:08d}-{128-bit-secret}@{domain}>`. The 128-bit random secret
provides cross-process uniqueness; the per-generator counter preserves creation
order within a single millisecond on one instance. This is a deliberate
trade-off: we sacrifice the lexicographic sortability of a pure UUID scheme in
exchange for human-readable timestamps and compact representation.

The timestamp is wall-clock milliseconds from an injected clock (default
`time.time`). It is **not** monotonic, so if the system clock jumps backward,
timestamps can repeat. Uniqueness still holds because the counter and secret
are independent of the clock; only ordering within a millisecond can break.

## The awkward edge

If you do not pass a `domain`, the generator falls back to `localhost`. That is
syntactically legal per RFC 5322 but not a resolvable domain. Real mail
delivery expects a domain you control. Pass one explicitly in production.

Domain validation is conservative: labels must match `[A-Za-z0-9-]`, total
length capped at 253, underscores rejected, leading hyphens rejected. If your
use case needs internationalised or quoted-local domains, this library will not
serve it.
