"""Fail-closed, write-ahead budget for one synthetic Anthropic trial.

This is not a general pricing engine or a production billing control. The only
allowed wire request is a bounded text Messages request to first-party Anthropic.
No tools, caching, thinking, streaming, geo premiums or SDK retries are enabled.
Reservations use UTF-8 bytes plus a generous provider-envelope allowance, not the
application's chars/4 estimate. Successful usage can reduce a reservation; failed
or ambiguous calls retain it. Reopening a journal never starts another trial.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from threading import RLock
import time

MODEL = "claude-sonnet-5"
MAX_CALLS = 16
MAX_TURNS = 4
MAX_MICRO_USD = 500_000
MAX_OUTPUT = 2048
MAX_INPUT_BYTES = 100_000
# More conservative than the verified 2026-09-07 $2/$10 per MTok prices.
INPUT_MICRO_USD = 3
OUTPUT_MICRO_USD = 15
ENVELOPE_TOKENS = 16_384


class TrialStopped(RuntimeError):
    """Safe fixed diagnostic; never includes request, credential or response text."""


def reservation(request: dict) -> tuple[int, int]:
    allowed = {"model", "max_tokens", "messages", "system", "output_config"}
    if set(request) - allowed or request.get("model") != MODEL:
        raise TrialStopped("trial_request_not_allowed")
    output = request.get("max_tokens")
    if type(output) is not int or not 1 <= output <= MAX_OUTPUT:
        raise TrialStopped("trial_output_limit")
    messages = request.get("messages")
    if (not isinstance(messages, list) or len(messages) != 1
            or set(messages[0]) != {"role", "content"}
            or messages[0]["role"] != "user"
            or not isinstance(messages[0]["content"], str)
            or not isinstance(request.get("system", ""), str)):
        raise TrialStopped("trial_text_only")
    if "output_config" in request:
        config = request["output_config"]
        if (not isinstance(config, dict) or set(config) != {"format"}
                or not isinstance(config["format"], dict)
                or set(config["format"]) != {"type", "schema"}
                or config["format"]["type"] != "json_schema"
                or not isinstance(config["format"]["schema"], dict)):
            raise TrialStopped("trial_output_config_not_allowed")
    wire = json.dumps(request, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(wire) > MAX_INPUT_BYTES:
        raise TrialStopped("trial_input_limit")
    input_bound = len(wire) + ENVELOPE_TOKENS
    return input_bound, input_bound * INPUT_MICRO_USD + output * OUTPUT_MICRO_USD


class TrialBudget:
    def __init__(self, journal: Path, *, expires_at: float | None = None):
        self._lock = RLock()
        # Exclusive creation is intentional. After interruption, reconcile this
        # batch; do not delete its journal or mint a new identity to rerun it.
        self._file = journal.open("x", encoding="utf-8")
        self.calls: list[dict] = []
        self.turns: set[str] = set()
        self.stopped = False
        self.replaying = False
        self.expires_at = expires_at
        self._append({"event": "created", "max_calls": MAX_CALLS,
                      "max_turns": MAX_TURNS, "max_micro_usd": MAX_MICRO_USD})

    def _append(self, event: dict) -> None:
        try:
            self._file.write(json.dumps(event, sort_keys=True) + "\n")
            self._file.flush()
            os.fsync(self._file.fileno())
        except Exception:
            self.stopped = True
            raise TrialStopped("trial_journal_failed") from None

    @property
    def charged_bound(self) -> int:
        return sum(call["bound_micro_usd"] for call in self.calls)

    def turn(self, identity: str, *, replay: bool = False) -> None:
        with self._lock:
            if replay:
                if identity not in self.turns:
                    raise TrialStopped("trial_unknown_replay")
                self.replaying = True
                return
            if self.stopped or identity in self.turns or len(self.turns) >= MAX_TURNS:
                raise TrialStopped("trial_turn_limit")
            self._append({"event": "turn", "identity_hash": hashlib.sha256(
                identity.encode()).hexdigest()})
            self.turns.add(identity)
            self.replaying = False

    def reserve(self, request: dict) -> int:
        with self._lock:
            if self.expires_at is not None and time.time() >= self.expires_at:
                self.stopped = True
                raise TrialStopped("trial_coverage_expired")
            if self.stopped or self.replaying or not self.turns or len(self.calls) >= MAX_CALLS:
                raise TrialStopped("trial_call_limit")
            input_bound, amount = reservation(request)
            if self.charged_bound + amount > MAX_MICRO_USD:
                self.stopped = True
                raise TrialStopped("trial_cost_limit")
            ticket = len(self.calls)
            entry = {"event": "reserved", "call": ticket,
                     "input_bound": input_bound, "output_bound": request["max_tokens"],
                     "bound_micro_usd": amount, "settled": False}
            self._append(entry)
            self.calls.append(entry)
            return ticket

    def settle(self, ticket: int, usage: dict) -> None:
        with self._lock:
            entry = self.calls[ticket]
            counts = [usage.get("input_tokens"), usage.get("output_tokens")]
            if (entry["settled"] or any(type(n) is not int or n < 0 for n in counts)
                    or counts[0] > entry["input_bound"] or counts[1] > entry["output_bound"]
                    or usage.get("cache_creation_input_tokens", 0) not in (0, None)
                    or usage.get("cache_read_input_tokens", 0) not in (0, None)
                    or usage.get("server_tool_use") not in (None, {})):
                self.stopped = True
                raise TrialStopped("trial_usage_requires_reconciliation")
            amount = counts[0] * INPUT_MICRO_USD + counts[1] * OUTPUT_MICRO_USD
            self._append({"event": "usage", "call": ticket,
                          "input_tokens": counts[0], "output_tokens": counts[1],
                          "bound_micro_usd": amount})
            entry.update(bound_micro_usd=amount, settled=True)

    def fail(self) -> None:
        with self._lock:
            self.stopped = True
            self._append({"event": "stopped"})

    def checkpoint(self, language: str, case: str, flags: dict[str, bool]) -> None:
        """Persist only fixed-schema observations, never arbitrary diagnostic text."""
        allowed = {
            "specialist_packet_private_marker_absent", "li_packet_private_marker_present",
            "specialist_provider_responded", "derived_history_private",
            "exact_replay_no_provider_call", "write_before_model",
            "real_response_before_injected_failure", "outcome_uncertain",
            "canonical_memory_fingerprint_unchanged_on_replay",
            "same_correction_record_after_replay", "exact_value_unique",
            "marker_present", "current_turn_source_present",
        }
        if (language not in {"en", "sv"} or case not in {"privacy", "recovery", "recovery_precondition"}
                or not flags or set(flags) - allowed
                or any(type(value) is not bool for value in flags.values())):
            raise TrialStopped("trial_checkpoint_not_allowed")
        with self._lock:
            self._append({"event": "checkpoint", "language": language, "case": case,
                          "flags": flags})

    def close(self) -> None:
        self._file.close()
