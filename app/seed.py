"""Realistic demo data for a small payments team. Dates are relative to today so the demo never goes stale.
Seeds only when the database is empty (safe to call on every startup)."""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from . import models
from .logger import get_logger

log = get_logger("seed")
D = lambda n: date.today() + timedelta(days=n)  # noqa: E731


def _item(db, meeting, title, owner, due, status="open", outcome="", orig=None, parent=None, hist_note="Created in meeting"):
    it = models.ActionItem(meeting_id=meeting.id, original_meeting_id=(orig or meeting).id, parent_item_id=parent.id if parent else None,
                           title=title, owner=owner, due_date=due, status=status, outcome=outcome)
    db.add(it)
    db.flush()
    db.add(models.ActionItemHistory(item_id=it.id, event="created", new_value=f"owner={owner or '-'}, due={due or '-'}", note=hist_note))
    if status in ("done", "dropped"):
        db.add(models.ActionItemHistory(item_id=it.id, event="status_changed", old_value="open", new_value=status, note=outcome))
    if status == "in_progress":
        db.add(models.ActionItemHistory(item_id=it.id, event="status_changed", old_value="open", new_value="in_progress"))
    return it


def _people(db, m, rows):
    for name, rsvp, attended in rows:
        db.add(models.Participant(meeting_id=m.id, name=name, email=f"{name.lower()}@northwind.example", rsvp=rsvp, attended=attended))


def seed_if_empty(db: Session) -> None:
    if db.query(models.Meeting).count() > 0:
        return

    # ---------------- knowledge base
    kb = [
        ("Release process", "doc", "Production releases happen every second Thursday. A release candidate is cut from main on Tuesday and must pass the regression suite and a staging smoke test. The release manager posts a go/no-go in #releases by 3pm. Rollbacks use the one-click revert in the deploy tool; any rollback needs a postmortem within five working days. Database migrations must be backwards compatible for one release."),
        ("On-call guide", "doc", "On-call rotates weekly between backend engineers. The primary responds to PagerDuty within 10 minutes; the secondary takes over after 20. Severity 1 incidents require an incident channel, a named incident commander and a status page update within 30 minutes. Escalation path: primary, secondary, engineering manager, CTO. Hand the pager over every Monday with a written summary of open alerts."),
        ("Billing service runbook", "doc", "The billing service issues invoices nightly at 02:00 UTC and retries failed card payments three times over seven days. Invoice generation depends on the tax-rates table and the Stripe webhook consumer. If the webhook queue backs up, scale the consumer to four replicas and replay from the dead-letter queue. Refund approvals above 500 USD need finance sign-off. Ask the billing owner before changing retry timing."),
        ("Payments API versioning policy", "doc", "Public API changes are versioned by date header. A breaking change needs a new version, a deprecation notice to partners 90 days ahead and a migration guide. Additive fields are not breaking. Partner sandbox keys must be rotated every 180 days. Changelog entries are mandatory for every merged API pull request."),
        ("Incident postmortem template", "doc", "Postmortems are blameless and published within five working days. Sections: impact, timeline, root cause, what went well, what went badly, action items with owners and due dates. Every action item must be tracked until closed and reviewed in the next weekly sync. Severity 1 postmortems are presented to the whole engineering team."),
        ("New engineer onboarding", "doc", "Week one: laptop setup, repository access, shadow the on-call engineer, and ship a small fix. Week two: own a ticket end to end and present it at the weekly sync. Mentors are assigned by the engineering manager. Security training and the data-handling quiz must be completed within the first 14 days."),
        ("Load testing guide", "doc", "Load tests run against the staging cluster using k6 scripts in the perf repository. Target for the payments API is 1,200 requests per second with p95 latency under 300 ms. Run a load test before any release that touches the payment path and attach the report to the release ticket. Never run load tests against production."),
    ]
    for t, ty, c in kb:
        db.add(models.KBDocument(title=t, type=ty, content=c))
    db.flush()

    # ---------------- Q3 retro (closed, 30 days ago)
    retro = models.Meeting(title="Q3 Engineering Retro", type="meeting", date=D(-30), status="closed",
                           agenda="What went well, what hurt, and what we change in Q4.",
                           summary="The team shipped Payments v1 on time but struggled with unclear on-call ownership and flaky staging tests.",
                           notes="Retro notes: on-call escalation was confusing during the August outage. Staging tests flake roughly 1 in 6 runs.")
    db.add(retro)
    db.flush()
    _people(db, retro, [("Aarav", "accepted", True), ("Priya", "accepted", True), ("Rohan", "accepted", True), ("Meera", "accepted", True), ("Sneha", "accepted", True)])
    db.add_all([models.Decision(meeting_id=retro.id, text="Adopt weekly on-call rotation with written handovers"),
                models.Decision(meeting_id=retro.id, text="Freeze new features for two days before each release")])
    retro_oncall = _item(db, retro, "Document the on-call escalation path", "Rohan", D(-14), status="carried",
                         hist_note="Created in retro")
    _item(db, retro, "Stabilise flaky staging tests", "Meera", D(-10), status="done",
          outcome="Quarantined 4 flaky suites; failure rate dropped from 1 in 6 to 1 in 40")

    # ---------------- Sprint 42 planning (held, 12 days ago)
    s42 = models.Meeting(title="Sprint 42 Planning", type="meeting", date=D(-12), status="held",
                         agenda="Review Q3 carry-overs. Scope the Payments v2 refund flow. Capacity check.",
                         summary="Sprint scoped around the Payments v2 refund flow. Team agreed to cap scope at 34 points because Kabir is out for two weeks from next Monday.",
                         notes="Rohan still owes the on-call doc. Priya to prototype partial refunds. Meera raised the load test gap for the refund path.")
    db.add(s42)
    db.flush()
    _people(db, s42, [("Aarav", "accepted", True), ("Priya", "accepted", True), ("Rohan", "accepted", True),
                      ("Meera", "accepted", True), ("Kabir", "accepted", True), ("Sneha", "declined", False)])
    db.add_all([models.Decision(meeting_id=s42.id, text="Cap Sprint 42 scope at 34 story points"),
                models.Decision(meeting_id=s42.id, text="Partial refunds ship behind a feature flag first"),
                models.Decision(meeting_id=s42.id, text="Refund approvals above 500 USD stay manual until finance signs off")])
    s42_oncall = _item(db, s42, "Document the on-call escalation path", "Rohan", D(-5), status="in_progress",
                       orig=retro, parent=retro_oncall, hist_note="Carried forward from Q3 Engineering Retro")
    db.add(models.ActionItemHistory(item_id=s42_oncall.id, event="carried_forward", old_value=f"meeting #{retro.id}",
                                    new_value=f"meeting #{s42.id}", note='Carried from "Q3 Engineering Retro"'))
    _item(db, s42, "Prototype partial refund API behind a feature flag", "Priya", D(3), status="in_progress")
    _item(db, s42, "Load test the refund path against staging", "Meera", D(-2))   # overdue
    _item(db, s42, "Confirm refund approval threshold with finance", "", D(5))     # unowned
    _item(db, s42, "Draft partner deprecation notice for v1 refund endpoint", "Aarav", D(10))
    _item(db, s42, "Evaluate switching webhook consumer to batch processing", "Sneha", None, status="dropped",
          outcome="Out of scope this quarter; revisit after v2 launch")

    # ---------------- Kabir leave handover (held, 3 days ago)
    ho = models.Meeting(title="Billing service handover: Kabir to Rohan", type="handover", date=D(-3), status="held",
                        agenda="Kabir is on leave for two weeks. Transfer ownership of the billing service, pending tickets and partner contacts.",
                        summary="Kabir walked Rohan through the nightly invoice job and the retry logic. Two tickets are still open and the tax-rate update is risky.",
                        notes="Kabir: tax-rates table update is due end of month, do not change retry timing without asking finance. Stripe webhook consumer sometimes backs up on the 1st of the month. Partner contact for invoices: finance@northwind.example.")
    db.add(ho)
    db.flush()
    _people(db, ho, [("Kabir", "accepted", True), ("Rohan", "accepted", True), ("Aarav", "accepted", True), ("Priya", "pending", False)])
    db.add_all([models.Decision(meeting_id=ho.id, text="Rohan is the interim owner of the billing service until Kabir returns"),
                models.Decision(meeting_id=ho.id, text="No changes to invoice retry timing during the handover period")])
    _item(db, ho, "Update the tax-rates table for the new quarter", "Kabir", D(4))
    _item(db, ho, "Investigate webhook queue backlog on the 1st of the month", "Kabir", D(7), status="in_progress")
    _item(db, ho, "Share partner contact list and escalation numbers", "Kabir", D(-1))  # overdue, on leave

    # ---------------- Weekly sync (planned, upcoming)
    wk = models.Meeting(title="Weekly Engineering Sync", type="meeting", date=D(2), status="planned",
                        agenda="1. Sprint 42 progress  2. Billing handover status  3. Release go/no-go  4. Open action items review",
                        summary="", notes="")
    db.add(wk)
    db.flush()
    _people(db, wk, [("Aarav", "accepted", False), ("Priya", "accepted", False), ("Rohan", "pending", False),
                     ("Meera", "declined", False), ("Sneha", "pending", False)])

    db.commit()
    log.info("seeded", extra={"meetings": 4, "kb_docs": len(kb)})
