"""Run from a private terminal; defaults to fake providers, never live by accident.

This owns exactly one disposable container with loopback-only published PostgreSQL.
It reuses the tracked migration validator. No backup, .env or user profile is read.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import getpass
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import warnings
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from acceptance.trial_budget import MODEL, TrialBudget, TrialStopped  # noqa: E402

IMAGE = "supabase/postgres:17.6.1.136@sha256:f371b5f3f2ac0a05703f33d6e6134515fb2498cab708fb948a0aeb7481467c00"
CONTAINER = "li-os-kr011-provider-pr104-20260909"
DATABASE = "li_os_kr011_provider_pr104"
PORT = "55443"
PASSWORD = "ci-synthetic-postgres-password"
JOURNAL = ROOT / "output" / "acceptance" / "kr011-provider-20260907.jsonl"
PR104_JOURNAL = JOURNAL.with_name("kr011-provider-pr104-20260909.jsonl")
PREDECESSOR_SHA256 = "3e38ce407dcce3a7d8353749a719e63437bc6907e4edd3e1c1c9231e23fef917"
KEY_ENTRY_JOURNAL = JOURNAL.with_name("kr011-provider-pr104-key-entry-20260909.jsonl")
PRE_DISPATCH_SHA256 = "4fc45bbbd060ba4f2934cab352013381d18f8ed89eec5a675f515832470b4e13"
DOCKER_ENDPOINT = ("npipe:////./pipe/dockerDesktopLinuxEngine" if sys.platform == "win32"
                   else "unix:///var/run/docker.sock")


def command(args, *, env=None):
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=240)
    if result.returncode:
        raise TrialStopped("local_trial_setup_or_cleanup_failed")
    return result.stdout.strip()


def isolated_environment() -> dict:
    # Allow-list process basics: no inherited DB, provider, proxy or cloud config.
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC",
               "PATHEXT", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "PROGRAMFILES"}
    return {key: value for key, value in os.environ.items() if key.upper() in allowed} | {
        "PGHOST": "127.0.0.1", "PGPORT": PORT, "PGDATABASE": DATABASE,
        "PGUSER": "supabase_admin", "PGPASSWORD": PASSWORD, "PGSSLMODE": "disable",
    }


def docker_command(*arguments):
    # Do not inherit a remote Docker context/host and accidentally create cloud resources.
    return command(["docker", "--host", DOCKER_ENDPOINT, *arguments], env=isolated_environment())


def fake_messages():
    """Exercise the live runner and real app/DB locally without any network provider."""
    def create(**request):
        system = request.get("system", "")
        content = request["messages"][0]["content"]
        if "You are Nora" in system:
            answer = {"recommendation": "Compare the imaginary reversible options.",
                      "confidence": 0.8, "sources_needed": False}
        elif "output_config" in request:
            answer = {"final_response": "A short synthetic comparison.",
                      "used_specialist_keys": ["nora"] if "Ask Nora" in content or "Be Nora" in content else [],
                      "action_intents": []}
        else:
            old = re.search(r"synthetic-old-(?:en|sv)-[a-f0-9]+", content)
            new = re.search(r"synthetic-new-(?:en|sv)-[a-f0-9]+", content)
            candidate = {"action": "correct_explicit",
                         "memory_class": "explicit_preference", "domain": "notebooks",
                         "value": (("Föredrar anteckningsböcker märkta " if "synthetic-new-sv-" in content
                                    else "Prefers notebooks labelled ") + new[0]) if new else "unused",
                         "sensitivity": "low"}
            if old:
                candidate["target_query"] = old[0]
            answer = {"candidates": [candidate] if old else []}
        return SimpleNamespace(stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=json.dumps(answer))],
            usage=SimpleNamespace(model_dump=lambda: {"input_tokens": 100, "output_tokens": 100}))
    return SimpleNamespace(create=create)


def configure_application():
    # Clear only this child process's environment. Never modify user/system secrets.
    clean = isolated_environment()
    os.environ.clear()
    os.environ.update(clean)
    from app.config import Settings, get_settings
    from unittest.mock import patch
    settings = Settings(_env_file=None, environment="development", log_level="CRITICAL",
        api_token="ci-synthetic-api-token", theo_api_token="ci-synthetic-theo-token",
        owner_api_token="ci-synthetic-owner-token", anthropic_api_key="ci-synthetic-placeholder",
        claude_model=MODEL, db_host="127.0.0.1", db_port=int(PORT), db_name=DATABASE,
        db_user="li_backend_runtime", db_password="ci-synthetic-backend-password",
        theo_db_user="li_theo_runtime", theo_db_password="ci-synthetic-theo-password",
        owner_db_user="li_owner_runtime", owner_db_password="ci-synthetic-owner-password",
        db_sslmode="disable")
    get_settings.cache_clear()
    return patch("app.config.get_settings", lambda: settings)


def memory_fingerprint():
    """Read only this runner's synthetic canonical schema; emit a digest, never rows."""
    import psycopg
    from psycopg import sql
    digest = hashlib.sha256()
    with psycopg.connect(host="127.0.0.1", port=int(PORT), dbname=DATABASE,
                         user="supabase_admin", password=PASSWORD, sslmode="disable") as connection:
        tables = connection.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'li_memory' ORDER BY tablename").fetchall()
        for (table,) in tables:
            digest.update(table.encode())
            # Include proposals, versions, audits and every canonical row, not only
            # the one record returned by a search. Owner-service DSNs are impossible here.
            rows = connection.execute(sql.SQL(
                "SELECT row_to_json(t)::text FROM {}.{} t ORDER BY row_to_json(t)::text"
            ).format(sql.Identifier("li_memory"), sql.Identifier(table))).fetchall()
            for (row,) in rows:
                digest.update(row.encode())
    return digest.hexdigest()


def verify_trial_schema() -> str:
    """Match runtime health to the manifest just applied by the isolated validator."""
    from acceptance.provider_trial import require
    from app.database import database_health
    manifest = json.loads((ROOT / "memory/migrations/manifest.json").read_text(encoding="utf-8"))
    expected = manifest["migrations"][-1]["logical_version"]
    require(database_health().get("schema_version") == expected, "runtime_database_health_failed")
    return expected


def trial_journal(live: bool, authorized_pr104: bool, authorized_key_entry: bool = False):
    """One exact owner-authorized new batch, never an arbitrary retry path."""
    predecessor = None
    if authorized_pr104 and authorized_key_entry:
        raise TrialStopped("select_one_authorized_batch_only")
    if authorized_pr104 or authorized_key_entry:
        if not JOURNAL.is_file() or JOURNAL.is_symlink():
            raise TrialStopped("preserved_predecessor_required")
        predecessor = hashlib.sha256(JOURNAL.read_bytes()).hexdigest()
        if predecessor != PREDECESSOR_SHA256:
            raise TrialStopped("preserved_predecessor_changed")
    if authorized_key_entry:
        if (not PR104_JOURNAL.is_file() or PR104_JOURNAL.is_symlink()
                or hashlib.sha256(PR104_JOURNAL.read_bytes()).hexdigest() != PRE_DISPATCH_SHA256):
            raise TrialStopped("preserved_pre_dispatch_ledger_required")
    journal = (KEY_ENTRY_JOURNAL if authorized_key_entry else
               PR104_JOURNAL if authorized_pr104 else JOURNAL) if live else (
        JOURNAL.with_name("kr011-provider-dry-" + str(time.time_ns()) + ".jsonl"))
    if journal.exists() or journal.is_symlink():
        raise TrialStopped("trial_ledger_already_exists_reconcile_only")
    return journal, predecessor


def run(live: bool, prepaid: Decimal | None, verified_at: str | None, auto_reload_off: bool,
        authorized_pr104: bool = False, authorized_key_entry: bool = False):
    from acceptance.provider_trial import require, run_cases
    if live:
        require(prepaid is not None and prepaid.is_finite() and prepaid >= Decimal("1.00")
                and auto_reload_off, "current_prepaid_coverage_required")
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(verified_at)).total_seconds()
        except (ValueError, TypeError):
            raise TrialStopped("current_balance_timestamp_required") from None
        require(0 <= age <= 3600, "remeasure_balance_before_live_trial")
    journal, predecessor = trial_journal(live, authorized_pr104, authorized_key_entry)
    env = isolated_environment()
    # Refuse to reuse an existing resource; no ambiguous cleanup scope.
    existing = docker_command("ps", "-a", "--filter", f"name=^/{CONTAINER}$", "--format", "{{.ID}}")
    require(not existing, "named_container_already_exists")
    docker_command("image", "inspect", IMAGE, "--format", "{{.Id}}")
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    budget = TrialBudget(journal, expires_at=(
        datetime.fromisoformat(verified_at).timestamp() + 3600 if live else None),
        predecessor_sha256=predecessor,
        pre_dispatch_sha256=PRE_DISPATCH_SHA256 if authorized_key_entry else None)
    container_id = None
    sdk = None
    try:
        container_id = docker_command("run", "--detach", "--pull=never", "--name", CONTAINER,
            "--label", "li-os.synthetic-acceptance=kr011-provider-pr104-20260909",
            "--publish", f"127.0.0.1:{PORT}:5432", "--env", "POSTGRES_DB=postgres",
            "--env", f"POSTGRES_PASSWORD={PASSWORD}", IMAGE)
        require(bool(re.fullmatch(r"[a-f0-9]{64}", container_id)), "container_identity_invalid")
        for _ in range(45):
            ready = subprocess.run(["docker", "--host", DOCKER_ENDPOINT, "exec", container_id,
                                    "pg_isready", "-U", "postgres", "-h", "localhost"],
                                   env=env, capture_output=True, timeout=10)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise TrialStopped("local_database_not_ready")
        command(["psql", "-X", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-c",
                 f"CREATE DATABASE {DATABASE};"], env=env)
        command(["psql", "-X", "-v", "ON_ERROR_STOP=1", "-c",
                 f"GRANT CREATE ON DATABASE {DATABASE} TO postgres; GRANT CREATE ON SCHEMA public TO postgres;"], env=env)
        command([sys.executable, str(ROOT / "memory/tests/validate_migrations.py")], env=env)
        import psycopg
        from psycopg import sql
        with psycopg.connect(host="127.0.0.1", port=int(PORT), dbname=DATABASE,
                             user="postgres", password=PASSWORD, sslmode="disable",
                             autocommit=True) as connection:
            for role, password in (("li_backend_runtime", "ci-synthetic-backend-password"),
                                   ("li_theo_runtime", "ci-synthetic-theo-password"),
                                   ("li_owner_runtime", "ci-synthetic-owner-password")):
                connection.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)))
        with configure_application():
            schema = verify_trial_schema()
            print(f"PASS: fresh isolated schema {schema}; three distinct synthetic runtime roles.", flush=True)
            logging.disable(logging.CRITICAL)
            messages = fake_messages()
            if live:
                # No key in CLI args, environment, files, model context, evidence or logs.
                require(sys.stdin.isatty(), "private_interactive_terminal_required")
                with warnings.catch_warnings():
                    warnings.simplefilter("error", getpass.GetPassWarning)
                    key = getpass.getpass("Existing Anthropic API key (private masked entry; NOT a Li or DB token): ")
                require(key.startswith("sk-ant-"), "anthropic_key_not_entered")
                import anthropic
                import httpx
                sdk = anthropic.Anthropic(api_key=key, base_url="https://api.anthropic.com",
                    max_retries=0, timeout=60,
                    http_client=httpx.Client(trust_env=False, follow_redirects=False,
                                             transport=httpx.HTTPTransport(retries=0)))
                key = None
                messages = sdk.messages
            evidence = run_cases(budget, messages, memory_fingerprint)
            print(json.dumps({"mode": "local_provider_backed" if live else "local_fake_provider",
                              "evidence": evidence, "model_calls": len(budget.calls),
                              "cost_upper_bound_usd": budget.charged_bound / 1_000_000}, sort_keys=True))
    finally:
        try:
            if sdk is not None:
                sdk.close()
        finally:
            try:
                budget.close()
            finally:
                if container_id and re.fullmatch(r"[a-f0-9]{64}", container_id):
                    # Remove only the ID returned by this run, even if SDK close fails.
                    docker_command("rm", "--force", "--volumes", container_id)
                    print("Removed only this run's disposable synthetic container/database/volume.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--prepaid-usd", type=Decimal)
    parser.add_argument("--balance-verified-at")
    parser.add_argument("--auto-reload-off", action="store_true")
    parser.add_argument("--authorized-pr104-trial", action="store_true",
                        help="Select only the separately authorized one-use 2026-09-09 trial.")
    parser.add_argument("--authorized-key-entry-trial", action="store_true",
                        help="Select the one separately authorized attempt after the pre-dispatch stop.")
    args = parser.parse_args()
    try:
        run(args.live, args.prepaid_usd, args.balance_verified_at, args.auto_reload_off,
            args.authorized_pr104_trial, args.authorized_key_entry_trial)
    except BaseException as exc:
        # Never emit tracebacks, provider packets, Pydantic input values or SDK errors.
        code = str(exc) if isinstance(exc, TrialStopped) else "trial_failed_safe_diagnostic_only"
        print("STOP: " + code + ". Do not restart a live batch; reconcile its journal first.")
        sys.exit(1)
