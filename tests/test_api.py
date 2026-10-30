import os
import tempfile
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/t.db"
os.environ["LOG_FILE"] = f"{tempfile.mkdtemp()}/t.log"
os.environ["AI_API_KEY"] = ""  # force the fallback path

from datetime import date, timedelta  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        setup = client.post("/api/auth/setup", json={
            "name": "Test Admin", "email": "admin@example.test", "password": "correct-horse-battery"
        })
        assert setup.status_code == 201
        yield client


def future(n=5):
    return (date.today() + timedelta(days=n)).isoformat()


def test_health_and_request_id(c):
    r = c.get("/api/health")
    assert r.status_code == 200 and r.headers["X-Request-ID"]


def test_login_protects_api_and_admin_manages_accounts(c):
    with TestClient(app) as anon:
        assert anon.get("/api/auth/status").json()["setup_required"] is False
        assert anon.get("/api/dashboard").status_code == 401
        assert anon.post("/api/auth/login", json={"email": "admin@example.test", "password": "wrong"}).status_code == 401
        logged_in = anon.post("/api/auth/login", json={
            "email": "admin@example.test", "password": "correct-horse-battery"
        })
        assert logged_in.status_code == 200 and logged_in.json()["role"] == "admin"
        member = anon.post("/api/auth/users", json={
            "name": "Team Member", "email": "member@example.test", "password": "member-passphrase-123", "role": "member"
        })
        assert member.status_code == 201
        assert anon.get("/api/auth/users").status_code == 200

        with TestClient(app) as member_client:
            assert member_client.post("/api/auth/login", json={
                "email": "member@example.test", "password": "member-passphrase-123"
            }).status_code == 200
            assert member_client.get("/api/dashboard").status_code == 200
            assert member_client.get("/api/auth/users").status_code == 403
            member_client.post("/api/auth/logout")
            assert member_client.get("/api/dashboard").status_code == 401
        with TestClient(app) as signed_out:
            assert signed_out.get("/api/dashboard").status_code == 401


def test_validation_errors_are_clear(c):
    r = c.post("/api/meetings", json={"title": "x", "date": "not-a-date"})
    assert r.status_code == 422 and "request_id" in r.json() and r.json()["details"]
    assert c.get("/api/meetings/9999").status_code == 404


def test_csv_exports_are_database_backed(c):
    meetings = c.get("/api/reports/meetings.csv")
    items = c.get("/api/reports/action-items.csv")
    assert meetings.status_code == items.status_code == 200
    assert "text/csv" in items.headers["content-type"]
    assert "Priority" in items.text and "Task" in items.text
    assert "Title" in meetings.text and "Participants" in meetings.text


def test_create_meeting_and_items(c):
    m = c.post("/api/meetings", json={"title": "Test planning", "date": future(1),
                                      "participants": [{"name": "Ana"}, {"name": "Ben", "email": "ben@x.io"}]}).json()
    assert len(m["participants"]) == 2
    past = c.post(f"/api/meetings/{m['id']}/action-items", json={"title": "Old thing", "due_date": "2020-01-01"})
    assert past.status_code == 422
    it = c.post(f"/api/meetings/{m['id']}/action-items", json={"title": "Write spec", "owner": "Ana", "due_date": future()}).json()
    assert it["status"] == "open" and it["history"][0]["event"] == "created"
    # closing requires an outcome
    assert c.patch(f"/api/action-items/{it['id']}", json={"status": "done"}).status_code == 422
    r = c.patch(f"/api/action-items/{it['id']}", json={"status": "done", "outcome": "Spec approved by team"})
    assert r.status_code == 200 and r.json()["status"] == "done"
    r = c.patch(f"/api/action-items/{it['id']}", json={"owner": "Ben"}).json()
    assert [h["event"] for h in r["history"]][-1] == "reassigned"


def test_priority_blocker_are_persisted_and_history_tracked(c):
    m = c.post("/api/meetings", json={"title": "Planning sync", "date": future()}).json()
    item = c.post(f"/api/meetings/{m['id']}/action-items", json={
        "title": "Prepare deployment plan", "priority": "urgent", "blocker": "Waiting for staging access"
    }).json()
    assert item["priority"] == "urgent" and item["blocker"] == "Waiting for staging access"
    saved = c.patch(f"/api/action-items/{item['id']}", json={"priority": "high", "blocker": ""}).json()
    assert saved["priority"] == "high" and saved["blocker"] == ""
    assert {h["event"] for h in saved["history"]} >= {"priority_changed", "blocker_changed"}


def test_carry_forward_keeps_history(c):
    m = c.post("/api/meetings", json={"title": "Carry source", "date": future(1)}).json()
    a = c.post(f"/api/meetings/{m['id']}/action-items", json={"title": "Keep going", "owner": "Ana", "due_date": future(9)}).json()
    r = c.post(f"/api/meetings/{m['id']}/carry-forward", json={})
    assert r.status_code == 200 and r.json()["carried"] == 1
    tgt = c.get(f"/api/meetings/{r.json()['target_meeting_id']}").json()
    copy = tgt["action_items"][0]
    assert copy["original_meeting_id"] == m["id"] and copy["parent_item_id"] == a["id"] and copy["carried"]
    assert c.get(f"/api/action-items/{a['id']}").json()["status"] == "carried"
    assert c.patch(f"/api/action-items/{a['id']}", json={"owner": "Z"}).status_code == 409
    assert c.post(f"/api/meetings/{m['id']}/carry-forward", json={}).status_code == 400  # nothing left


def test_carry_forward_rejects_duplicate_ids(c):
    m = c.post("/api/meetings", json={"title": "Duplicate guard", "date": future()}).json()
    a = c.post(f"/api/meetings/{m['id']}/action-items", json={"title": "Carry one task"}).json()
    r = c.post(f"/api/meetings/{m['id']}/carry-forward", json={"item_ids": [a["id"], a["id"]]})
    assert r.status_code == 422 and "only once" in r.json()["error"]


def test_bulk_reassign(c):
    r = c.post("/api/people/reassign", json={"from_owner": "Kabir", "to_owner": "Rohan"})
    assert r.status_code == 200 and r.json()["reassigned"] >= 1
    assert c.post("/api/people/reassign", json={"from_owner": "Kabir", "to_owner": "Rohan"}).status_code == 404


def test_ai_fallbacks_never_500(c):
    mid = c.post("/api/meetings", json={"title": "Recap me", "date": future(0)}).json()["id"]
    raw = ("We decided to launch on Friday. Ana will prepare the release notes. "
           "Ben to update the runbook. Everyone agreed to freeze the code on Wednesday.")
    r = c.post(f"/api/meetings/{mid}/recap", json={"raw_text": raw})
    assert r.status_code == 200 and r.json()["fallback"] is True
    recap = r.json()["recap"]
    assert any(i["owner"] == "Ana" for i in recap["action_items"]) and recap["decisions"]
    ok = c.post(f"/api/meetings/{mid}/recap/apply", json=recap)
    assert ok.status_code == 200 and ok.json()["status"] == "held" and len(ok.json()["action_items"]) >= 2
    b = c.get("/api/meetings/2/brief?for_person=Priya")
    assert b.status_code == 200 and b.json()["brief"]["headline"]
    rd = c.get("/api/meetings/2/readiness").json()
    assert 0 <= rd["score"] <= 100 and rd["checks"]


def test_kb_linking_and_nudge(c):
    items = c.get("/api/action-items?overdue=true").json()
    assert items
    r = c.post(f"/api/action-items/{items[0]['id']}/link-kb")
    assert r.status_code == 200
    n = c.post(f"/api/action-items/{items[0]['id']}/nudge")
    assert n.status_code == 200 and n.json()["message"]
    assert c.post("/api/kb", json={"title": "Short", "content": "tiny"}).status_code == 422


def test_rag_answer_uses_knowledge_sources(c):
    r = c.post("/api/kb/ask", json={"question": "How many times are failed card payments retried?"})
    assert r.status_code == 200
    body = r.json()
    assert body["retrieval"] == "keyword" and body["fallback"] is True
    assert body["sources"] and body["sources"][0]["title"] == "Billing service runbook"
    assert "three times over seven days" in body["answer"]
    assert c.post("/api/kb/ask", json={"question": "x"}).status_code == 422


def test_semantic_retrieval_indexes_and_ranks_chunks(monkeypatch):
    from app import kb_service
    from app.database import SessionLocal

    def fake_embed(texts, task_type):
        if task_type == "RETRIEVAL_QUERY":
            return [[1.0, 0.0] for _ in texts]
        return [[1.0, 0.0] if "billing service runbook" in text.lower() else [0.0, 1.0] for text in texts]

    monkeypatch.setattr(kb_service, "embed_texts", fake_embed)
    with SessionLocal() as db:
        hits = kb_service.semantic_candidates(db, "What is the card payment retry policy?", top_k=2)
    assert hits and hits[0]["doc"].title == "Billing service runbook"
    assert hits[0]["score"] == 1.0


def test_meeting_notes_upload_text_and_zip(c):
    meeting = c.post("/api/meetings", json={"title": "Upload notes", "date": future(1)}).json()
    plain = c.post(f"/api/meetings/{meeting['id']}/notes/upload", data={"notes": "Typed note kept"},
                   files=[("files", ("rough-notes.txt", b"People discussed the launch timeline.", "text/plain"))])
    assert plain.status_code == 200 and plain.json()["files"] == ["rough-notes.txt"]
    notes = c.get(f"/api/meetings/{meeting['id']}").json()["notes"]
    assert "Typed note kept" in notes and "launch timeline" in notes

    archive = BytesIO()
    with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
        bundle.writestr("meeting/rough-notes.md", "Rohan was absent. Priya owns the beta follow-up.")
        bundle.writestr("decisions.txt", "We agreed to keep the rollout behind a feature flag.")
    zipped = c.post(f"/api/meetings/{meeting['id']}/notes/upload", data={"notes": notes},
                    files=[("files", ("absent-teammate-notes.zip", archive.getvalue(), "application/zip"))])
    assert zipped.status_code == 200 and zipped.json()["files_uploaded"] == 2
    final_notes = c.get(f"/api/meetings/{meeting['id']}").json()["notes"]
    assert "Rohan was absent" in final_notes and "feature flag" in final_notes

    unsupported = c.post(f"/api/meetings/{meeting['id']}/notes/upload", data={"notes": final_notes},
                         files=[("files", ("audio.mp3", b"audio", "audio/mpeg"))])
    assert unsupported.status_code == 422


def test_json_fence_stripping():
    from app.ai_service import _extract_json
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json('Sure! {"a": 2} thanks') == {"a": 2}


def test_ai_success_retry_and_failure(c, monkeypatch):
    from app import ai_service
    monkeypatch.setattr(ai_service.settings, "ai_api_key", "fake-key-123")
    calls = {"n": 0}
    good = '```json\n{"summary":"S","decisions":["D1"],"action_items":[{"title":"Do thing","owner":"Ana","due_date":null}]}\n```'

    def flaky(system, prompt, model):  # 1st call garbage, 2nd good -> retry works, fences stripped
        calls["n"] += 1
        return "not json at all" if calls["n"] == 1 else good

    monkeypatch.setattr(ai_service, "_gemini", flaky)
    r = ai_service.extract_recap("Ana will do thing. We decided D1 for sure.", ["Ana"])
    assert r["ai_used"] is True and r["fallback"] is False and calls["n"] == 2
    assert r["recap"]["action_items"][0]["owner"] == "Ana"

    def schema_bad(system, prompt, model):  # valid JSON, wrong shape -> falls back, no crash
        return '{"summary": "", "action_items": "nope"}'

    monkeypatch.setattr(ai_service, "_gemini", schema_bad)
    r = ai_service.extract_recap("Ana will do thing. We decided D1 for sure.", ["Ana"])
    assert r["fallback"] is True and r["notice"]

    def bad_key(system, prompt, model):
        raise ai_service.AIError("http 403 (check AI_API_KEY / AI_MODEL)", retryable=False)

    monkeypatch.setattr(ai_service, "_gemini", bad_key)
    mid = c.post("/api/meetings", json={"title": "Bad key meeting", "date": future(0)}).json()["id"]
    r = c.post(f"/api/meetings/{mid}/recap", json={"raw_text": "Ana will ship the beta build tomorrow morning."})
    assert r.status_code == 200 and r.json()["fallback"] is True


def test_no_secret_in_logs():
    from app.logger import redact
    assert "AIzaSyABCDEFGHIJKLMNOPQRSTUV" not in redact("url?key=AIzaSyABCDEFGHIJKLMNOPQRSTUV&x=1")
    assert "secret123" not in redact('{"api_key": "secret123"}')
