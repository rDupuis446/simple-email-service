"""Deterministic tests for email_message_id_generator.core.

We inject a fake clock so output timestamps are fully predictable. We never
assert on wall-clock time, never sleep, and never compare floats with ==.
"""

import os
import re
import unittest

from email_message_id_generator.core import (
    MessageIDGenerator,
    DEFAULT_DOMAIN_POLICY,
    DEFAULT_CLOCK,
)


# A fake clock that advances by a fixed number of seconds each call. Returns
# Unix epoch seconds as a float, matching the contract of time.time.
class _FakeClock:
    def __init__(self, start: float = 1_000_000.0, step: float = 0.0) -> None:
        self._current = start
        self._step = step
        self.calls = 0

    def __call__(self) -> float:
        result = self._current
        self._current += self._step
        self.calls += 1
        return result


# Matches the exact format we generate: <ms-counter-32hex@domain>
_MSGID_RE = re.compile(
    r'^<\d+-\d{8}-[0-9a-f]{32}@[A-Za-z0-9.-]+>$'
)


class TestMessageIDFormat(unittest.TestCase):
    def test_basic_shape_includes_brackets(self) -> None:
        clock = _FakeClock()
        gen = MessageIDGenerator(domain="example.org", clock=clock)
        mid = gen.generate()
        self.assertTrue(mid.startswith("<"))
        self.assertTrue(mid.endswith(">"))

    def test_matches_expected_regex(self) -> None:
        clock = _FakeClock()
        gen = MessageIDGenerator(domain="example.org", clock=clock)
        self.assertRegex(gen.generate(), _MSGID_RE)

    def test_default_domain_is_localhost(self) -> None:
        clock = _FakeClock()
        gen = MessageIDGenerator(clock=clock)
        mid = gen.generate()
        self.assertTrue(mid.endswith("@localhost>"))
        self.assertEqual(gen.domain, DEFAULT_DOMAIN_POLICY)
        self.assertEqual(DEFAULT_DOMAIN_POLICY, "localhost")

    def test_domain_is_stripped_of_surrounding_whitespace(self) -> None:
        clock = _FakeClock()
        gen = MessageIDGenerator(domain="  example.org  ", clock=clock)
        self.assertEqual(gen.domain, "example.org")
        self.assertTrue(gen.generate().endswith("@example.org>"))

    def test_timestamp_is_milliseconds_of_clock(self) -> None:
        # 1_500_000.0 seconds -> 1_500_000_000 ms
        clock = _FakeClock(start=1_500_000.0)
        gen = MessageIDGenerator(domain="example.org", clock=clock)
        mid = gen.generate()
        # Extract the ms segment (the first numeric run after '<').
        ms_segment = mid[1:mid.index("-")]
        self.assertEqual(ms_segment, "1500000000")


class TestUniquenessAndOrdering(unittest.TestCase):
    def test_two_calls_in_same_ms_differ_by_counter(self) -> None:
        clock = _FakeClock(start=2_000_000.0, step=0.0)  # never advances
        gen = MessageIDGenerator(domain="example.org", clock=clock)
        first = gen.generate()
        second = gen.generate()
        self.assertNotEqual(first, second)
        # Counters should be 00000001 and 00000002.
        self.assertIn("-00000001-", first)
        self.assertIn("-00000002-", second)

    def test_counter_padded_to_eight_digits(self) -> None:
        clock = _FakeClock()
        gen = MessageIDGenerator(domain="example.org", clock=clock)
        mid = gen.generate()
        # The counter segment is exactly 8 digits.
        parts = mid[1:-1].split("-")
        # parts: [ms, counter, secret@domain]
        self.assertEqual(len(parts), 3)
        counter = parts[1]
        self.assertEqual(len(counter), 8)
        self.assertTrue(counter.isdigit())

    def test_many_calls_are_all_distinct(self) -> None:
        clock = _FakeClock(step=0.0)
        gen = MessageIDGenerator(domain="example.org", clock=clock)
        ids = {gen.generate() for _ in range(500)}
        self.assertEqual(len(ids), 500)

    def test_ordering_within_same_ms_matches_creation(self) -> None:
        clock = _FakeClock(step=0.0)
        gen = MessageIDGenerator(domain="example.org", clock=clock)
        ids = [gen.generate() for _ in range(10)]
        self.assertEqual(ids, sorted(ids))


class TestDomainValidation(unittest.TestCase):
    def _expect_value_error(self, domain) -> None:
        with self.assertRaises(ValueError):
            MessageIDGenerator(domain=domain, clock=_FakeClock())

    def test_empty_string_rejected(self) -> None:
        self._expect_value_error("")

    def test_whitespace_only_rejected(self) -> None:
        self._expect_value_error("   \t  ")

    def test_at_sign_rejected(self) -> None:
        self._expect_value_error("foo@example.org")

    def test_angle_brackets_rejected(self) -> None:
        self._expect_value_error("<example.org>")

    def test_control_character_rejected(self) -> None:
        self._expect_value_error("example\n.org")

    def test_label_too_long_rejected(self) -> None:
        # A single label of 64 chars exceeds the 63-char limit.
        long_label = "a" * 64
        self._expect_value_error(long_label)

    def test_total_length_over_253_rejected(self) -> None:
        # 254 chars total in a dotted form.
        # Each label 63 chars -> 4 labels + 3 dots = 255 chars.
        labels = ["a" * 63 for _ in range(4)]
        domain = ".".join(labels)
        self.assertEqual(len(domain), 255)
        self._expect_value_error(domain)

    def test_valid_subdomain_accepted(self) -> None:
        clock = _FakeClock()
        gen = MessageIDGenerator(domain="mail.sub.example.org", clock=clock)
        self.assertEqual(gen.domain, "mail.sub.example.org")

    def test_fqdn_with_trailing_dot_accepted(self) -> None:
        clock = _FakeClock()
        gen = MessageIDGenerator(domain="example.org.", clock=clock)
        self.assertEqual(gen.domain, "example.org.")

    def test_single_label_localhost_accepted(self) -> None:
        clock = _FakeClock()
        gen = MessageIDGenerator(domain="localhost", clock=clock)
        self.assertEqual(gen.domain, "localhost")

    def test_underscore_rejected(self) -> None:
        # Underscore is not valid in hostnames; we reject it.
        self._expect_value_error("bad_domain.example.org")

    def test_leading_hyphen_rejected(self) -> None:
        self._expect_value_error("-bad.example.org")


class TestDefaults(unittest.TestCase):
    def test_default_clock_is_time_time(self) -> None:
        # We only check identity, never behaviour.
        import time
        self.assertIs(DEFAULT_CLOCK, time.time)

    def test_default_domain_constant_value(self) -> None:
        self.assertEqual(DEFAULT_DOMAIN_POLICY, "localhost")


if __name__ == "__main__":
    unittest.main()
