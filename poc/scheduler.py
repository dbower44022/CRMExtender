"""Per-account background sync scheduler (Mail Client MAIL-13; TDD D-07).

One scheduler thread lives inside the web server process. Every tick it
looks at each active provider account: an account is due when its
interval has elapsed since its last run finished, or when a run was
requested ("Sync now"). A due account is synced on its own worker
thread; the same account never has two runs at once, and a global
pause stops timed runs without blocking manual ones. When every account
run has finished and at least one ran since the last cross-account
pass, the pass (summaries, enrichment, identity resolution) runs once.

A manual "Sync now" for all accounts is tracked as one aggregate run so
the Dashboard's existing status contract (running / started_at /
completed_at / result / error) keeps working.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from . import config, events
from .database import get_connection

log = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 120
MIN_INTERVAL_SECONDS = 60
TICK_SECONDS = 5.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _event_result(result: dict | None) -> dict | None:
    """The counts worth sending to browsers (never the full result)."""
    if not result:
        return None
    keys = ("emails_fetched", "emails_added", "emails_deleted", "labels_changed", "flags_changed",
            "actions_pushed", "actions_failed", "summarized", "contacts")
    return {k: result[k] for k in keys if k in result}


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


class SyncScheduler:
    """See module docstring. One instance per process; see :func:`get_scheduler`."""

    def __init__(self, *, tick_seconds: float = TICK_SECONDS) -> None:
        self._tick_seconds = tick_seconds
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.paused = False
        self.started_at: datetime | None = None
        #: account_id -> state dict
        self._accounts: dict[str, dict] = {}
        self._workers: dict[str, threading.Thread] = {}
        self._requested: set[str] = set()
        self._post_pass_due = False
        self._post_pass_running = False
        self._post_pass_since: datetime | None = None
        self._post_pass_state: dict = {"running": False, "started_at": None,
                                       "completed_at": None, "result": None, "error": None}
        #: aggregate manual run (Dashboard "Sync Now")
        self._manual: dict = {"running": False, "started_at": None, "completed_at": None,
                              "result": None, "error": None, "pending_accounts": set()}
        from .rate_limiter import RateLimiter
        self._gmail_limiter = RateLimiter(rate=config.GMAIL_RATE_LIMIT)
        self._claude_limiter = RateLimiter(rate=config.CLAUDE_RATE_LIMIT)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self.started_at = _now()
            self._thread = threading.Thread(target=self._loop, name="crm-scheduler", daemon=True)
            self._thread.start()
        log.info("Sync scheduler started")

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout)
        log.info("Sync scheduler stopped")

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def pause(self) -> None:
        with self._lock:
            self.paused = True

    def resume(self) -> None:
        with self._lock:
            self.paused = False

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                log.exception("Scheduler tick failed")
            self._stop.wait(self._tick_seconds)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def interval_seconds(self, customer_id: str | None) -> int:
        from .settings import get_setting
        try:
            raw = get_setting(customer_id, "mail_sync_interval_seconds") if customer_id else None
            val = int(raw) if raw else DEFAULT_INTERVAL_SECONDS
        except (ValueError, TypeError):
            val = DEFAULT_INTERVAL_SECONDS
        return max(MIN_INTERVAL_SECONDS, val)

    def timed_runs_enabled(self, customer_id: str | None) -> bool:
        from .settings import get_setting
        if not customer_id:
            return True
        return (get_setting(customer_id, "sync_enabled") or "true").lower() != "false"

    # ------------------------------------------------------------------
    # Requests
    # ------------------------------------------------------------------

    def request_run(self, account_id: str | None = None) -> bool:
        """Ask for an immediate run of one account, or of all (a manual run).

        Returns False when a manual all-accounts run is already in
        progress (the Dashboard's 409 contract).
        """
        with self._lock:
            if account_id:
                self._requested.add(account_id)
                return True
            if self._manual["running"]:
                return False
            accounts = self._load_accounts()
            self._manual.update(running=True, started_at=_iso(_now()), completed_at=None,
                                result=None, error=None,
                                pending_accounts={a["id"] for a in accounts})
            self._manual["_merged"] = {"accounts": len(accounts), "errors": []}
            for a in accounts:
                self._requested.add(a["id"])
            if not accounts:
                self._manual["_merged"]["errors"].append("No accounts registered.")
                self._finish_manual_if_done(force=True)
            return True

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------

    def _load_accounts(self) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM provider_accounts WHERE is_active = 1 "
                "AND COALESCE(auth_status, 'ok') NOT IN ('needs_reauth', 'disconnected') ORDER BY created_at"
            ).fetchall()
            return [dict(r) for r in rows]

    def _owner_for(self, account_id: str, customer_id: str) -> str | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT user_id FROM user_provider_accounts WHERE account_id = ? "
                "ORDER BY CASE role WHEN 'owner' THEN 0 ELSE 1 END, created_at LIMIT 1",
                (account_id,),
            ).fetchone()
            if row:
                return row["user_id"]
            row = conn.execute(
                "SELECT id FROM users WHERE customer_id = ? AND is_active = 1 "
                "ORDER BY CASE role WHEN 'admin' THEN 0 ELSE 1 END, created_at LIMIT 1",
                (customer_id,),
            ).fetchone()
            return row["id"] if row else None

    def tick(self, now: datetime | None = None) -> list[str]:
        """One scheduling pass. Returns the account ids started. Thread-safe."""
        now = now or _now()
        started: list[str] = []
        with self._lock:
            accounts = self._load_accounts()
            known = {a["id"] for a in accounts}
            for a in accounts:
                st = self._accounts.setdefault(a["id"], {
                    "email": a["email_address"], "customer_id": a["customer_id"],
                    "running": False, "last_started": None, "last_finished": None,
                    "last_result": None, "last_error": None, "runs": 0,
                })
                st["email"] = a["email_address"]
                if st["running"]:
                    continue
                interval = self.interval_seconds(a["customer_id"])
                requested = a["id"] in self._requested
                timed_ok = not self.paused and self.timed_runs_enabled(a["customer_id"])
                due_at = (st["last_finished"] + timedelta(seconds=interval)) if st["last_finished"] else now
                st["next_due_at"] = due_at
                if requested or (timed_ok and now >= due_at):
                    self._requested.discard(a["id"])
                    self._start_account(a, st)
                    started.append(a["id"])
            # forget removed/deactivated accounts' requests
            self._requested &= known

            if (self._post_pass_due and not self._post_pass_running
                    and not any(s["running"] for s in self._accounts.values())):
                self._start_post_pass()
        # Queued outbound mail whose undo window or scheduled time has passed (MAIL-35)
        try:
            from .outbound import send_due
            with get_connection() as conn:
                sent = send_due(conn, now_iso=now.isoformat())
            if sent:
                log.info("Queued send: %d message(s) processed", len(sent))
                for r in sent:
                    events.publish("outbound.sent", queue_id=r.get("queue_id"), status=r.get("status"),
                                   communication_id=r.get("communication_id"), error=r.get("failure_reason"))
        except Exception:
            log.exception("Queued send failed")
        return started

    def _start_account(self, account: dict, st: dict) -> None:
        st.update(running=True, last_started=_now(), last_error=None)
        customer_id = account["customer_id"]
        user_id = self._owner_for(account["id"], customer_id)
        events.publish("sync.started", account_id=account["id"], email=account["email_address"])

        def work() -> None:
            from .sync_service import sync_account
            result: dict | None = None
            error: str | None = None
            try:
                result = sync_account(account, customer_id=customer_id, user_id=user_id,
                                      gmail_limiter=self._gmail_limiter)
            except Exception as exc:
                log.exception("Scheduled sync failed for %s", account["email_address"])
                error = str(exc)
            events.publish("sync.finished", account_id=account["id"], email=account["email_address"],
                           error=error, result=_event_result(result))
            try:
                from .account_health import record_sync_outcome
                from .mail_notify import new_inbox_messages
                with get_connection() as conn:
                    record_sync_outcome(conn, account["id"], ([error] if error else None) or (result or {}).get("errors"))
                    # New inbox mail from this run (MAIL-39); a first sync is history, not news.
                    if account.get("initial_sync_done"):
                        fresh = new_inbox_messages(conn, account["id"], st["last_started"].isoformat())
                        if fresh["count"]:
                            events.publish("mail.new", account_id=account["id"], email=account["email_address"], **fresh)
            except Exception:
                log.exception("Could not record sync outcome for %s", account["email_address"])
            with self._lock:
                st.update(running=False, last_finished=_now(), last_result=result,
                          last_error=error, runs=st["runs"] + 1)
                if self._post_pass_since is None:
                    self._post_pass_since = st["last_started"]
                self._post_pass_due = True
                self._post_pass_customer = customer_id
                if account["id"] in self._manual["pending_accounts"]:
                    self._manual["pending_accounts"].discard(account["id"])
                    merged = self._manual["_merged"]
                    if result:
                        from .sync_service import merge_results
                        merge_results(merged, result)
                    if error:
                        merged.setdefault("errors", []).append(f"{account['email_address']}: {error}")
                self._workers.pop(account["id"], None)

        t = threading.Thread(target=work, name=f"crm-sync-{account['email_address']}", daemon=True)
        self._workers[account["id"]] = t
        t.start()

    def _start_post_pass(self) -> None:
        self._post_pass_due = False
        self._post_pass_running = True
        since = self._post_pass_since or _now()
        self._post_pass_since = None
        customer_id = getattr(self, "_post_pass_customer", None)
        self._post_pass_state.update(running=True, started_at=_iso(_now()), completed_at=None,
                                     result=None, error=None)

        def work() -> None:
            from .sync_service import post_sync_pass
            result: dict | None = None
            error: str | None = None
            try:
                if customer_id:
                    result = post_sync_pass(customer_id=customer_id, since_iso=since.isoformat(),
                                            gmail_limiter=self._gmail_limiter,
                                            claude_limiter=self._claude_limiter)
            except Exception as exc:
                log.exception("Post-sync pass failed")
                error = str(exc)
            events.publish("post_pass.finished", error=error, result=_event_result(result))
            with self._lock:
                self._post_pass_running = False
                self._post_pass_state.update(running=False, completed_at=_iso(_now()),
                                             result=result, error=error)
                if self._manual["running"] and not self._manual["pending_accounts"]:
                    merged = self._manual["_merged"]
                    if result:
                        from .sync_service import merge_results
                        merge_results(merged, result)
                    if error:
                        merged.setdefault("errors", []).append(f"post-sync pass: {error}")
                    self._finish_manual_if_done(force=True)

        threading.Thread(target=work, name="crm-post-sync", daemon=True).start()

    def _finish_manual_if_done(self, *, force: bool = False) -> None:
        m = self._manual
        if not m["running"]:
            return
        if m["pending_accounts"] and not force:
            return
        merged = m.pop("_merged", {"errors": []})
        for key in ("contacts", "emails_fetched", "actions_pushed", "actions_failed",
                    "triaged", "summarized", "enriched", "duplicate_candidates"):
            merged.setdefault(key, 0)
        m.update(running=False, completed_at=_iso(_now()), result=merged, error=None)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def wait_idle(self, timeout: float = 10.0) -> bool:
        """Test helper: block until no account run or post pass is active."""
        deadline = _now() + timedelta(seconds=timeout)
        while _now() < deadline:
            with self._lock:
                busy = self._post_pass_running or any(s["running"] for s in self._accounts.values())
            if not busy:
                return True
            threading.Event().wait(0.02)
        return False

    def legacy_status(self) -> dict:
        """The Dashboard's /sync/status shape, describing the manual run."""
        with self._lock:
            m = self._manual
            return {"running": m["running"], "started_at": m["started_at"],
                    "completed_at": m["completed_at"], "result": m["result"], "error": m["error"]}

    def status(self) -> dict:
        with self._lock:
            accounts = {}
            for aid, st in self._accounts.items():
                accounts[aid] = {
                    "email": st["email"], "running": st["running"],
                    "last_started": _iso(st["last_started"]), "last_finished": _iso(st["last_finished"]),
                    "next_due_at": _iso(st.get("next_due_at")),
                    "last_error": st["last_error"], "runs": st["runs"],
                    "last_result": st["last_result"],
                }
            return {
                "enabled": self.running, "paused": self.paused,
                "started_at": _iso(self.started_at),
                "accounts": accounts,
                "post_pass": dict(self._post_pass_state),
                "manual_run": self.legacy_status(),
            }


# ---------------------------------------------------------------------------
# Process-wide instance
# ---------------------------------------------------------------------------

_scheduler: SyncScheduler | None = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> SyncScheduler | None:
    return _scheduler


def start_scheduler() -> SyncScheduler:
    global _scheduler
    with _scheduler_lock:
        if _scheduler is None:
            _scheduler = SyncScheduler()
        _scheduler.start()
        return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    with _scheduler_lock:
        if _scheduler is not None:
            _scheduler.stop()
            _scheduler = None
