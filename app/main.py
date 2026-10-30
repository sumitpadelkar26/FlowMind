import time
import os
import re
import csv
from io import StringIO
from datetime import date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.exc import IntegrityError
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from . import ai_service, auth, kb_service, models, schemas
from .config import settings
from .database import Base, SessionLocal, engine, get_db
from .logger import get_logger, new_request_id, request_id_var, setup_logging
from .migrations import upgrade_existing_database
from .note_uploads import MAX_FILES, MAX_UPLOAD_BYTES, extract_note_upload

setup_logging()
log = get_logger("app")
app = FastAPI(title="FlowMind - AI Knowledge & Task Platform", version="1.0.0")
STATIC = Path(__file__).parent / "static"
OPEN = ("open", "in_progress")
CLOSED = ("done", "dropped")


# ------------------------------------------------------------------ startup
@app.on_event("startup")
def on_startup():
    if os.getenv("VERCEL"):
        if settings.database_url.startswith("sqlite"):
            raise RuntimeError("Configure DATABASE_URL with a hosted PostgreSQL database on Vercel; local SQLite files are not durable there.")
        if not settings.auth_secret:
            raise RuntimeError("Configure AUTH_SECRET in Vercel Environment Variables so sessions work across function instances.")
    Base.metadata.create_all(bind=engine)
    upgrade_existing_database(engine)
    if settings.seed_on_start:
        from .seed import seed_if_empty
        with SessionLocal() as db:
            seed_if_empty(db)
    if not settings.auth_secret:
        log.warning("auth_secret_missing", extra={"note": "Sessions will be invalidated when the process restarts"})
    log.info("startup", extra={"ai_configured": ai_service.ai_enabled(), "model": settings.ai_model,
                               "db": settings.database_url.split(":")[0]})


# --------------------------------------------------------- middleware / errors
@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or new_request_id()
    token = request_id_var.set(rid)
    t0 = time.perf_counter()
    try:
        path = request.url.path
        public = path in {"/api/health", "/api/auth/status", "/api/auth/setup", "/api/auth/login", "/api/auth/logout"}
        if path.startswith("/api/") and not public:
            with SessionLocal() as db:
                user = _session_user(db, request)
                if user is None:
                    response = JSONResponse(status_code=401, content={
                        "error": "Sign in to continue", "request_id": rid})
                else:
                    request.state.user = {"id": user.id, "name": user.name, "email": user.email, "role": user.role}
                    response = await call_next(request)
        else:
            response = await call_next(request)
    except Exception:
        log.error("unhandled_exception", exc_info=True, extra={"method": request.method, "path": request.url.path})
        response = JSONResponse(status_code=500, content={
            "error": "Something went wrong on our side. Please try again.", "request_id": rid})
    ms = round((time.perf_counter() - t0) * 1000)
    if request.url.path.startswith("/api"):
        log.info("request", extra={"method": request.method, "path": request.url.path,
                                   "status": response.status_code, "duration_ms": ms})
    response.headers["X-Request-ID"] = rid
    request_id_var.reset(token)
    return response


def _session_user(db: Session, request: Request):
    claims = auth.read_session(request.cookies.get("flowmind_session"))
    if not claims:
        return None
    user = db.get(models.User, claims.get("uid"))
    if not user or not user.active or user.session_version != claims.get("ver"):
        return None
    return user


def _set_auth_cookie(response: Response, user: models.User):
    response.set_cookie("flowmind_session", auth.issue_session(user.id, user.session_version),
                        max_age=auth.SESSION_TTL_SECONDS, httponly=True, secure=settings.auth_cookie_secure,
                        samesite="strict", path="/")


def _user_public(user: models.User) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role,
            "active": user.active, "created_at": user.created_at.isoformat()}


@app.get("/api/auth/status")
def auth_status(request: Request, db: Session = Depends(get_db)):
    user = _session_user(db, request)
    return {"setup_required": db.query(models.User.id).first() is None,
            "authenticated": user is not None, "user": _user_public(user) if user else None}


@app.post("/api/auth/setup", status_code=201)
def auth_setup(body: schemas.FirstAdminCreate, request: Request, response: Response,
               db: Session = Depends(get_db)):
    if db.query(models.User.id).first() is not None:
        raise HTTPException(409, "Initial admin setup is already complete. Sign in instead.")
    user = models.User(name=body.name, email=body.email, password_hash=auth.hash_password(body.password), role="admin")
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account was created at the same time. Try signing in.")
    _set_auth_cookie(response, user)
    log.info("first_admin_created", extra={"user_id": user.id})
    return _user_public(user)


@app.post("/api/auth/login")
def auth_login(body: schemas.LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if not user or not user.active or not auth.verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect")
    _set_auth_cookie(response, user)
    log.info("user_login", extra={"user_id": user.id})
    return _user_public(user)


@app.post("/api/auth/logout")
def auth_logout(request: Request, response: Response, db: Session = Depends(get_db)):
    user = _session_user(db, request)
    if user:
        user.session_version += 1
        db.commit()
        log.info("user_logout", extra={"user_id": user.id})
    response.delete_cookie("flowmind_session", path="/", httponly=True,
                           secure=settings.auth_cookie_secure, samesite="strict")
    return {"ok": True}


@app.get("/api/auth/me")
def auth_me(request: Request):
    return request.state.user


@app.get("/api/auth/users")
def auth_users(request: Request, db: Session = Depends(get_db)):
    if request.state.user["role"] != "admin":
        raise HTTPException(403, "Admin role required")
    return [_user_public(u) for u in db.query(models.User).order_by(models.User.id).all()]


@app.post("/api/auth/users", status_code=201)
def auth_create_user(body: schemas.UserCreate, request: Request, db: Session = Depends(get_db)):
    if request.state.user["role"] != "admin":
        raise HTTPException(403, "Admin role required")
    user = models.User(name=body.name, email=body.email, password_hash=auth.hash_password(body.password), role=body.role)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists")
    log.info("user_created", extra={"user_id": user.id, "role": user.role, "created_by": request.state.user["id"]})
    return _user_public(user)


@app.patch("/api/auth/users/{user_id}")
def auth_update_user(user_id: int, body: schemas.UserUpdate, request: Request, db: Session = Depends(get_db)):
    if request.state.user["role"] != "admin":
        raise HTTPException(403, "Admin role required")
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    data = body.model_dump(exclude_unset=True)
    if user.id == request.state.user["id"] and data.get("active") is False:
        raise HTTPException(422, "You cannot deactivate your own account")
    removes_admin = user.role == "admin" and user.active and (
        data.get("role", user.role) != "admin" or data.get("active", user.active) is False)
    if removes_admin and db.query(models.User.id).filter_by(role="admin", active=True).count() <= 1:
        raise HTTPException(422, "Keep at least one active admin account")
    for key, value in data.items():
        if key == "password":
            user.password_hash = auth.hash_password(value)
            user.session_version += 1
        else:
            setattr(user, key, value)
    if "active" in data and not data["active"]:
        user.session_version += 1
    db.commit()
    return _user_public(user)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    details = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"].replace("Value error, ", "")}
               for e in exc.errors()]
    log.warning("validation_failed", extra={"path": request.url.path, "fields": [d["field"] for d in details]})
    msg = "; ".join(f"{d['field']}: {d['message']}" if d["field"] else d["message"] for d in details)
    return JSONResponse(status_code=422, content={"error": msg, "details": details, "request_id": request_id_var.get()})


@app.exception_handler(HTTPException)
async def http_handler(request: Request, exc: HTTPException):
    if exc.status_code >= 500:
        log.error("http_error", extra={"status": exc.status_code, "detail": str(exc.detail)})
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail, "request_id": request_id_var.get()})


# ------------------------------------------------------------------ helpers
def today() -> date:
    return date.today()


def is_overdue(it: models.ActionItem) -> bool:
    return bool(it.due_date and it.due_date < today() and it.status in OPEN)


def ser_item(it: models.ActionItem, full: bool = False) -> dict:
    d = {
        "id": it.id, "meeting_id": it.meeting_id, "original_meeting_id": it.original_meeting_id,
        "parent_item_id": it.parent_item_id, "title": it.title, "owner": it.owner,
        "due_date": it.due_date.isoformat() if it.due_date else None, "priority": it.priority,
        "blocker": it.blocker, "status": it.status,
        "outcome": it.outcome, "overdue": is_overdue(it),
        "meeting_title": it.meeting.title if it.meeting else None,
        "carried": it.original_meeting_id != it.meeting_id,
        "links": [{"kb_doc_id": l.kb_doc_id, "title": l.kb_doc.title, "reason": l.reason, "source": l.source}
                  for l in it.links],
    }
    if full:
        d["history"] = [{"event": h.event, "old": h.old_value, "new": h.new_value, "note": h.note,
                         "at": h.at.isoformat()} for h in it.history]
    return d


def ser_meeting(m: models.Meeting, full: bool = False) -> dict:
    open_n = sum(1 for i in m.action_items if i.status in OPEN)
    d = {
        "id": m.id, "title": m.title, "type": m.type, "date": m.date.isoformat(), "status": m.status,
        "agenda": m.agenda, "summary": m.summary, "participant_count": len(m.participants),
        "open_items": open_n, "total_items": len(m.action_items), "decision_count": len(m.decisions),
    }
    if full:
        d.update(
            notes=m.notes,
            participants=[{"id": p.id, "name": p.name, "email": p.email, "rsvp": p.rsvp, "attended": p.attended}
                          for p in m.participants],
            decisions=[{"id": x.id, "text": x.text} for x in m.decisions],
            action_items=[ser_item(i, full=True) for i in m.action_items],
        )
    return d


def get_meeting_or_404(db: Session, mid: int) -> models.Meeting:
    m = (db.query(models.Meeting)
         .options(selectinload(models.Meeting.participants), selectinload(models.Meeting.decisions),
                  selectinload(models.Meeting.action_items).selectinload(models.ActionItem.history),
                  selectinload(models.Meeting.action_items).selectinload(models.ActionItem.links)
                  .selectinload(models.Link.kb_doc))
         .filter(models.Meeting.id == mid).populate_existing().first())
    if not m:
        raise HTTPException(404, f"Meeting {mid} not found")
    return m


def get_item_or_404(db: Session, iid: int) -> models.ActionItem:
    it = db.get(models.ActionItem, iid, populate_existing=True)
    if not it:
        raise HTTPException(404, f"Action item {iid} not found")
    return it


def hist(db: Session, item: models.ActionItem, event: str, old="", new="", note=""):
    db.add(models.ActionItemHistory(item_id=item.id, event=event, old_value=str(old or ""),
                                    new_value=str(new or ""), note=note or ""))


def known_people(db: Session) -> list[str]:
    names = {n for (n,) in db.query(models.Participant.name).distinct()}
    names |= {o for (o,) in db.query(models.ActionItem.owner).distinct() if o}
    return sorted(names)


# ------------------------------------------------------------------ health / dashboard
@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "ai_configured": ai_service.ai_enabled(), "model": settings.ai_model}


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    items = db.query(models.ActionItem).options(selectinload(models.ActionItem.meeting)).all()
    live = [i for i in items if i.status in OPEN]
    by_owner: dict[str, int] = {}
    for i in live:
        by_owner[i.owner or "Unassigned"] = by_owner.get(i.owner or "Unassigned", 0) + 1
        attention = sorted([i for i in live if is_overdue(i) or not i.owner or i.priority in {"high", "urgent"}],
                       key=lambda i: (0 if i.priority == "urgent" else 1 if i.priority == "high" else 2,
                                      0 if is_overdue(i) else 1, i.due_date or date.max))[:6]
    return {
        "meetings": db.query(models.Meeting).count(),
        "open": len(live), "overdue": sum(1 for i in live if is_overdue(i)),
        "done": sum(1 for i in items if i.status == "done"),
        "unowned": sum(1 for i in live if not i.owner),
        "by_owner": [{"owner": k, "count": v} for k, v in sorted(by_owner.items(), key=lambda kv: -kv[1])],
        "attention": [ser_item(i) for i in attention],
        "ai": {"configured": ai_service.ai_enabled(), "model": settings.ai_model},
    }


@app.get("/api/people")
def people(db: Session = Depends(get_db)):
    return known_people(db)


def _csv_response(filename: str, headers: list[str], rows: list[list[object]]) -> Response:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/reports/action-items.csv")
def export_action_items(db: Session = Depends(get_db)):
    items = db.query(models.ActionItem).options(selectinload(models.ActionItem.meeting)).order_by(
        models.ActionItem.meeting_id, models.ActionItem.id).all()
    return _csv_response("flowmind-action-items.csv",
                         ["ID", "Original ID", "Meeting", "Task", "Owner", "Due date", "Priority", "Status", "Blocker", "Outcome"],
                         [[it.id, it.original_meeting_id, it.meeting.title if it.meeting else "", it.title,
                           it.owner, it.due_date.isoformat() if it.due_date else "", it.priority,
                           it.status, it.blocker, it.outcome] for it in items])


@app.get("/api/reports/meetings.csv")
def export_meetings(db: Session = Depends(get_db)):
    meetings = db.query(models.Meeting).options(selectinload(models.Meeting.participants),
        selectinload(models.Meeting.decisions)).order_by(models.Meeting.date, models.Meeting.id).all()
    return _csv_response("flowmind-meetings.csv",
        ["ID", "Title", "Type", "Date", "Status", "Participants", "Agenda", "Summary", "Decisions"],
        [[m.id, m.title, m.type, m.date.isoformat(), m.status,
          "; ".join(p.name for p in m.participants), m.agenda, m.summary,
          "; ".join(d.text for d in m.decisions)] for m in meetings])


# ------------------------------------------------------------------ meetings
@app.get("/api/meetings")
def list_meetings(status: str | None = Query(None), type: str | None = Query(None), q: str | None = Query(None),
                  db: Session = Depends(get_db)):
    qry = db.query(models.Meeting).options(selectinload(models.Meeting.participants),
                                           selectinload(models.Meeting.decisions),
                                           selectinload(models.Meeting.action_items))
    if status:
        qry = qry.filter(models.Meeting.status == status)
    if type:
        qry = qry.filter(models.Meeting.type == type)
    if q:
        qry = qry.filter(models.Meeting.title.ilike(f"%{q}%"))
    return [ser_meeting(m) for m in qry.order_by(models.Meeting.date.desc(), models.Meeting.id.desc()).all()]


@app.post("/api/meetings", status_code=201)
def create_meeting(body: schemas.MeetingCreate, db: Session = Depends(get_db)):
    m = models.Meeting(title=body.title, type=body.type, agenda=body.agenda, date=body.date, notes=body.notes)
    m.participants = [models.Participant(**p.model_dump()) for p in body.participants]
    db.add(m)
    db.commit()
    log.info("meeting_created", extra={"meeting_id": m.id, "type": m.type, "participants": len(m.participants)})
    return ser_meeting(get_meeting_or_404(db, m.id), full=True)


@app.get("/api/meetings/{mid}")
def get_meeting(mid: int, db: Session = Depends(get_db)):
    return ser_meeting(get_meeting_or_404(db, mid), full=True)


@app.post("/api/meetings/{mid}/notes/upload")
async def upload_meeting_notes(mid: int, files: list[UploadFile] = File(...),
                               notes: str | None = Form(default=None), db: Session = Depends(get_db)):
    meeting = get_meeting_or_404(db, mid)
    if len(files) > MAX_FILES:
        raise HTTPException(413, f"Upload at most {MAX_FILES} files at a time.")
    extracted, total_upload_bytes = [], 0
    for upload in files:
        data = await upload.read(MAX_UPLOAD_BYTES + 1)
        total_upload_bytes += len(data)
        if total_upload_bytes > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Combined upload size must be 5 MB or smaller.")
        try:
            extracted.extend(extract_note_upload(upload.filename or "notes.txt", data))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if len(extracted) > MAX_FILES:
            raise HTTPException(413, f"Upload at most {MAX_FILES} note files at a time, including ZIP contents.")
    base = meeting.notes if notes is None else notes
    appended = "\n\n".join(f"--- Uploaded notes: {name} ---\n{text}" for name, text in extracted)
    combined = f"{base.rstrip()}\n\n{appended}" if base.strip() else appended
    if len(combined) > 50_000:
        raise HTTPException(413, "Combined meeting notes would exceed the 50,000 character limit.")
    meeting.notes = combined
    db.commit()
    log.info("meeting_notes_uploaded", extra={"meeting_id": mid, "file_count": len(extracted),
                                               "characters_added": len(appended)})
    return {"meeting_id": mid, "files": [name for name, _ in extracted],
            "files_uploaded": len(extracted), "characters_added": len(appended)}


_ORDER = {"planned": 0, "held": 1, "closed": 2}


@app.patch("/api/meetings/{mid}")
def update_meeting(mid: int, body: schemas.MeetingUpdate, db: Session = Depends(get_db)):
    m = get_meeting_or_404(db, mid)
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        if _ORDER[data["status"]] < _ORDER[m.status]:
            raise HTTPException(409, f"Cannot move a {m.status} meeting back to {data['status']}")
    old_status = m.status
    for k, v in data.items():
        if v is not None:
            setattr(m, k, v)
    db.commit()
    if m.status != old_status:
        log.info("meeting_status_changed", extra={"meeting_id": m.id, "from": old_status, "to": m.status})
        if m.status == "closed":
            _archive_to_kb(db, m)
    return ser_meeting(get_meeting_or_404(db, mid), full=True)


def _archive_to_kb(db: Session, m: models.Meeting):
    """Closed meetings become searchable knowledge for future linking."""
    title = f"Meeting: {m.title} ({m.date.isoformat()})"
    body = f"{m.summary}\nDecisions: " + "; ".join(d.text for d in m.decisions) + f"\n{m.notes[:1500]}"
    if len(body.strip()) < 20 or db.query(models.KBDocument).filter_by(title=title).first():
        return
    db.add(models.KBDocument(title=title, type="past_meeting", content=body))
    db.commit()
    log.info("kb_archived", extra={"meeting_id": m.id})


@app.post("/api/meetings/{mid}/participants", status_code=201)
def add_participant(mid: int, body: schemas.ParticipantIn, db: Session = Depends(get_db)):
    m = get_meeting_or_404(db, mid)
    if any(p.name.lower() == body.name.lower() for p in m.participants):
        raise HTTPException(409, f"{body.name} is already a participant")
    db.add(models.Participant(meeting_id=mid, **body.model_dump()))
    db.commit()
    log.info("participant_added", extra={"meeting_id": mid, "name": body.name})
    return ser_meeting(get_meeting_or_404(db, mid), full=True)


@app.patch("/api/participants/{pid}")
def update_participant(pid: int, body: schemas.ParticipantUpdate, db: Session = Depends(get_db)):
    p = db.get(models.Participant, pid)
    if not p:
        raise HTTPException(404, f"Participant {pid} not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(p, k, v)
    db.commit()
    log.info("participant_updated", extra={"participant_id": pid, "rsvp": p.rsvp, "attended": p.attended})
    return ser_meeting(get_meeting_or_404(db, p.meeting_id), full=True)


@app.post("/api/meetings/{mid}/decisions", status_code=201)
def add_decision(mid: int, body: schemas.DecisionCreate, db: Session = Depends(get_db)):
    get_meeting_or_404(db, mid)
    db.add(models.Decision(meeting_id=mid, text=body.text.strip()))
    db.commit()
    log.info("decision_added", extra={"meeting_id": mid})
    return ser_meeting(get_meeting_or_404(db, mid), full=True)


@app.delete("/api/decisions/{did}")
def delete_decision(did: int, db: Session = Depends(get_db)):
    d = db.get(models.Decision, did)
    if not d:
        raise HTTPException(404, f"Decision {did} not found")
    mid = d.meeting_id
    db.delete(d)
    db.commit()
    return ser_meeting(get_meeting_or_404(db, mid), full=True)


# ------------------------------------------------------------------ action items
@app.get("/api/action-items")
def list_items(status: str | None = None, owner: str | None = None, priority: str | None = None, overdue: bool = False,
               db: Session = Depends(get_db)):
    qry = db.query(models.ActionItem).options(selectinload(models.ActionItem.meeting),
                                              selectinload(models.ActionItem.links).selectinload(models.Link.kb_doc))
    if status:
        qry = qry.filter(models.ActionItem.status == status)
    if owner:
        qry = qry.filter(models.ActionItem.owner == owner)
    if priority:
        if priority not in {"low", "medium", "high", "urgent"}:
            raise HTTPException(422, "priority must be low, medium, high, or urgent")
        qry = qry.filter(models.ActionItem.priority == priority)
    items = qry.order_by(models.ActionItem.due_date.is_(None), models.ActionItem.due_date).all()
    if overdue:
        items = [i for i in items if is_overdue(i)]
    return [ser_item(i) for i in items]


@app.post("/api/meetings/{mid}/action-items", status_code=201)
def create_item(mid: int, body: schemas.ActionItemCreate, db: Session = Depends(get_db)):
    get_meeting_or_404(db, mid)
    it = models.ActionItem(meeting_id=mid, original_meeting_id=mid, title=body.title, owner=body.owner,
                           due_date=body.due_date, priority=body.priority, blocker=body.blocker)
    db.add(it)
    db.flush()
    hist(db, it, "created", new=f"owner={it.owner or '-'}, due={it.due_date or '-'}")
    db.commit()
    log.info("action_item_created", extra={"item_id": it.id, "meeting_id": mid, "owner": it.owner})
    return ser_item(get_item_or_404(db, it.id), full=True)


@app.get("/api/action-items/{iid}")
def get_item(iid: int, db: Session = Depends(get_db)):
    return ser_item(get_item_or_404(db, iid), full=True)


@app.patch("/api/action-items/{iid}")
def update_item(iid: int, body: schemas.ActionItemUpdate, db: Session = Depends(get_db)):
    it = get_item_or_404(db, iid)
    if it.status == "carried":
        raise HTTPException(409, "This item was carried forward - update the copy in the newer meeting instead")
    data = body.model_dump(exclude_unset=True)
    note = data.pop("note", "") or ""

    new_status = data.get("status", it.status) or it.status
    new_outcome = data.get("outcome") if data.get("outcome") is not None else it.outcome
    if new_status in CLOSED and len(new_outcome.strip()) < 3:
        raise HTTPException(422, "Record the outcome before closing this item (what happened, in a few words)")
    if "due_date" in data and data["due_date"] and data["due_date"] < today() and new_status in OPEN \
            and data["due_date"] != it.due_date:
        raise HTTPException(422, "due_date: cannot be set in the past")

    if "owner" in data and data["owner"] is not None and data["owner"].strip() != it.owner:
        old, new = it.owner, " ".join(data["owner"].split())
        hist(db, it, "reassigned", old or "unassigned", new or "unassigned", note)
        it.owner = new
        log.info("action_item_reassigned", extra={"item_id": it.id, "from": old, "to": new})
    if "due_date" in data and data["due_date"] != it.due_date:
        hist(db, it, "due_changed", it.due_date or "", data["due_date"] or "", note)
        it.due_date = data["due_date"]
    if "priority" in data and data["priority"] and data["priority"] != it.priority:
        hist(db, it, "priority_changed", it.priority, data["priority"], note)
        it.priority = data["priority"]
    if "blocker" in data and data["blocker"] is not None:
        blocker = data["blocker"].strip()
        if blocker != it.blocker:
            hist(db, it, "blocker_changed", it.blocker or "", blocker, note)
            it.blocker = blocker
    if "title" in data and data["title"] and data["title"] != it.title:
        hist(db, it, "edited", it.title, data["title"], note)
        it.title = " ".join(data["title"].split())
    if "outcome" in data and data["outcome"] is not None and data["outcome"] != it.outcome:
        hist(db, it, "outcome", it.outcome, data["outcome"], note)
        it.outcome = data["outcome"].strip()
    if "status" in data and data["status"] and data["status"] != it.status:
        old = it.status
        hist(db, it, "status_changed", old, data["status"], note)
        it.status = data["status"]
        if it.status in CLOSED:
            log.info("action_item_closed", extra={"item_id": it.id, "status": it.status, "meeting_id": it.meeting_id})
        else:
            log.info("action_item_status_changed", extra={"item_id": it.id, "from": old, "to": it.status})
    db.commit()
    return ser_item(get_item_or_404(db, iid), full=True)


@app.post("/api/people/reassign")
def reassign_all(body: schemas.ReassignAll, db: Session = Depends(get_db)):
    """Leave / handover: move every live item from one person to another in one step."""
    if body.from_owner.strip().lower() == body.to_owner.strip().lower():
        raise HTTPException(422, "Choose two different people")
    items = db.query(models.ActionItem).filter(models.ActionItem.owner == body.from_owner,
                                               models.ActionItem.status.in_(OPEN)).all()
    if not items:
        raise HTTPException(404, f"{body.from_owner} has no open items to reassign")
    for it in items:
        hist(db, it, "reassigned", body.from_owner, body.to_owner, body.note)
        it.owner = body.to_owner.strip()
    db.commit()
    log.info("bulk_reassigned", extra={"from": body.from_owner, "to": body.to_owner, "count": len(items)})
    return {"reassigned": len(items), "ids": [i.id for i in items]}


@app.post("/api/meetings/{mid}/carry-forward")
def carry_forward(mid: int, body: schemas.CarryForward, db: Session = Depends(get_db)):
    src = get_meeting_or_404(db, mid)
    if body.item_ids:
        by_id = {i.id: i for i in src.action_items}
        bad = [i for i in body.item_ids if i not in by_id or by_id[i].status not in OPEN]
        if bad:
            raise HTTPException(422, f"Items {bad} are not open items of this meeting")
        items = [by_id[i] for i in body.item_ids]
    else:
        items = [i for i in src.action_items if i.status in OPEN]
    if not items:
        raise HTTPException(400, "There are no open items to carry forward")

    if body.target_meeting_id:
        if body.target_meeting_id == mid:
            raise HTTPException(422, "Target must be a different meeting")
        target = get_meeting_or_404(db, body.target_meeting_id)
    else:
        target = models.Meeting(title=body.new_title or f"Follow-up: {src.title}",
                                date=body.new_date or max(today(), src.date) + timedelta(days=7),
                                type=body.new_type, agenda="Review carried-forward items from "
                                                           f"\"{src.title}\".")
        db.add(target)
        db.flush()
    already_carried = [it.id for it in items if db.query(models.ActionItem.id).filter(
        models.ActionItem.meeting_id == target.id, models.ActionItem.parent_item_id == it.id).first()]
    if already_carried:
        raise HTTPException(409, f"Items {already_carried} already have a copy in the target meeting")
    try:  # one transaction: all items move or none do
        for it in items:
            copy = models.ActionItem(meeting_id=target.id, original_meeting_id=it.original_meeting_id,
                                     parent_item_id=it.id, title=it.title, owner=it.owner,
                                     due_date=it.due_date, priority=it.priority, blocker=it.blocker, status=it.status)
            db.add(copy)
            db.flush()
            hist(db, copy, "carried_forward", f"meeting #{src.id}", f"meeting #{target.id}",
                 f"Carried from \"{src.title}\"")
            hist(db, it, "status_changed", it.status, "carried", f"Carried to \"{target.title}\"")
            it.status = "carried"
        db.commit()
    except Exception:
        db.rollback()
        raise
    log.info("items_carried_forward", extra={"from_meeting": src.id, "to_meeting": target.id, "count": len(items)})
    return {"target_meeting_id": target.id, "carried": len(items)}


# ------------------------------------------------------------------ AI endpoints
@app.post("/api/meetings/{mid}/recap")
def make_recap(mid: int, body: schemas.RecapRequest, db: Session = Depends(get_db)):
    """Preview only - nothing from the AI is written to action items/decisions until the user applies it."""
    m = get_meeting_or_404(db, mid)
    people = sorted({p.name for p in m.participants} | set(known_people(db)))
    m.notes = body.raw_text  # keep the raw source so it is never lost
    db.commit()
    return ai_service.extract_recap(body.raw_text, people)


@app.post("/api/meetings/{mid}/recap/apply")
def apply_recap(mid: int, body: schemas.RecapApply, db: Session = Depends(get_db)):
    m = get_meeting_or_404(db, mid)
    if body.summary.strip():
        m.summary = body.summary.strip()
    existing = {d.text.lower() for d in m.decisions}
    new_dec = [d.strip() for d in body.decisions if d.strip() and d.strip().lower() not in existing]
    for d in new_dec:
        db.add(models.Decision(meeting_id=mid, text=d))
    added = 0
    for ai in body.action_items:
        it = models.ActionItem(meeting_id=mid, original_meeting_id=mid, title=ai.title.strip(),
                               owner=ai.owner, due_date=ai.due_date)
        db.add(it)
        db.flush()
        hist(db, it, "created", new=f"owner={it.owner or '-'}, due={it.due_date or '-'}", note="From AI recap")
        added += 1
    if m.status == "planned":
        m.status = "held"
    db.commit()
    log.info("recap_applied", extra={"meeting_id": mid, "decisions": len(new_dec), "items": added})
    return ser_meeting(get_meeting_or_404(db, mid), full=True)


def _brief_context(m: models.Meeting, person: str) -> dict:
    me = next((p for p in m.participants if p.name.lower() == person.lower()), None) if person else None
    return {
        "title": m.title, "type": m.type, "date": m.date.isoformat(), "agenda": m.agenda,
        "summary": m.summary, "notes_excerpt": m.notes[:2500],
        "participants": [{"name": p.name, "attended": p.attended, "rsvp": p.rsvp} for p in m.participants],
        "reader_missed_meeting": bool(me and not me.attended),
        "decisions": [d.text for d in m.decisions],
        "action_items": [{"title": i.title, "owner": i.owner, "due_date": i.due_date.isoformat() if i.due_date else None,
                          "status": i.status, "overdue": is_overdue(i), "outcome": i.outcome}
                         for i in m.action_items if i.status != "carried"],
    }


@app.get("/api/meetings/{mid}/brief")
def brief(mid: int, for_person: str = "", db: Session = Depends(get_db)):
    m = get_meeting_or_404(db, mid)
    result = ai_service.catchup_brief(_brief_context(m, for_person.strip()), for_person.strip())
    log.info("brief_generated", extra={"meeting_id": mid, "for": for_person or "-", "ai_used": result["ai_used"]})
    return result


@app.post("/api/action-items/{iid}/link-kb")
def link_kb(iid: int, db: Session = Depends(get_db)):
    return kb_service.link_item(db, get_item_or_404(db, iid))


@app.post("/api/action-items/{iid}/nudge")
def nudge(iid: int, db: Session = Depends(get_db)):
    it = get_item_or_404(db, iid)
    if it.status not in OPEN:
        raise HTTPException(409, "Only open items can be nudged")
    res = ai_service.draft_nudge(ser_item(it))
    log.info("nudge_drafted", extra={"item_id": iid, "ai_used": res["ai_used"]})
    return res


# ------------------------------------------------------------------ special feature: Handover Readiness
def _readiness(m: models.Meeting, db: Session) -> tuple[int, list[dict], list[dict]]:
    live = [i for i in m.action_items if i.status in OPEN]
    n = len(live)

    def frac(ok: int, total: int) -> float:
        return 1.0 if total == 0 else ok / total

    checks = [
        ("owners", "Every open item has an owner", 20, frac(sum(1 for i in live if i.owner), n),
         [i.title for i in live if not i.owner], "Assign an owner to: {x}"),
        ("dates", "Every open item has a due date", 10, frac(sum(1 for i in live if i.due_date), n),
         [i.title for i in live if not i.due_date], "Add a due date to: {x}"),
        ("overdue", "Nothing is overdue", 10, frac(sum(1 for i in live if not is_overdue(i)), n),
         [i.title for i in live if is_overdue(i)], "Re-plan or close overdue item: {x}"),
        ("decisions", "Decisions are written down", 10, 1.0 if m.decisions else 0.0,
         [] if m.decisions else ["no decisions"], "Record the decisions made so the next owner knows what is settled"),
        ("summary", "A summary exists", 10, 1.0 if m.summary.strip() else 0.0,
         [] if m.summary.strip() else ["no summary"], "Generate or write a summary"),
        ("kb", "Open items link to knowledge", 5, frac(sum(1 for i in live if i.links), n),
         [i.title for i in live if not i.links], "Link supporting docs to: {x}"),
        ("agenda", "Agenda / scope is defined", 5, 1.0 if m.agenda.strip() else 0.0,
         [] if m.agenda.strip() else ["no agenda"], "Add an agenda so the next person knows the scope"),
        ("blockers", "Open items have no unresolved blocker", 10, frac(sum(1 for i in live if not i.blocker.strip()), n),
         [i.title for i in live if i.blocker.strip()], "Resolve or document the blocker for: {x}"),
        ("repeat_carry", "No item has been carried forward repeatedly", 10,
         frac(sum(1 for i in live if carry_depth(i, db) < 2), n),
         [i.title for i in live if carry_depth(i, db) >= 2], "Review repeatedly carried item and reset its scope or owner: {x}"),
        ("decision_actions", "Decisions have related follow-up actions", 10,
         decision_action_fraction(m.decisions, m.action_items),
         [d.text for d in m.decisions if not decision_has_action(d.text, m.action_items)],
         "Add a follow-up action for decision: {x}"),
    ]
    score = round(sum(w * f for _, _, w, f, _, _ in checks))
    out, issues = [], []
    for key, label, w, f, bad, fix in checks:
        ok = f >= 0.999
        out.append({"key": key, "label": label, "weight": w, "earned": round(w * f, 1), "ok": ok,
                    "detail": ", ".join(bad[:3]) + (f" (+{len(bad) - 3} more)" if len(bad) > 3 else "")})
        if not ok:
            issues.append({"key": key, "label": label, "items": bad[:5], "fix": fix.format(x=", ".join(bad[:2]))})
    return score, out, issues


def carry_depth(item: models.ActionItem, db: Session) -> int:
    """Count predecessor links; a depth of two means the item was carried twice."""
    depth, parent_id, seen = 0, item.parent_item_id, {item.id}
    while parent_id and parent_id not in seen:
        seen.add(parent_id)
        parent = db.get(models.ActionItem, parent_id)
        if parent is None:
            break
        depth += 1
        parent_id = parent.parent_item_id
    return depth


def decision_has_action(text: str, items: list[models.ActionItem]) -> bool:
    words = {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 4}
    return any(words & {w for w in re.findall(r"[a-z0-9]+", i.title.lower()) if len(w) >= 4}
               for i in items)


def decision_action_fraction(decisions, items) -> float:
    return 1.0 if not decisions else sum(decision_has_action(d.text, items) for d in decisions) / len(decisions)


@app.get("/api/meetings/{mid}/readiness")
def readiness(mid: int, db: Session = Depends(get_db)):
    m = get_meeting_or_404(db, mid)
    # The decision/action match is a transparent title-keyword heuristic; it is an indicator, not proof.
    score, checks, issues = _readiness(m, db)
    advice = ai_service.readiness_advice(score, issues, _brief_context(m, ""))
    log.info("readiness_scored", extra={"meeting_id": mid, "score": score, "issues": len(issues)})
    return {"score": score, "checks": checks, "advice": advice}


# ------------------------------------------------------------------ knowledge base
@app.get("/api/kb")
def kb_list(q: str | None = None, db: Session = Depends(get_db)):
    qry = db.query(models.KBDocument)
    if q:
        qry = qry.filter(models.KBDocument.title.ilike(f"%{q}%") | models.KBDocument.content.ilike(f"%{q}%"))
    return [{"id": d.id, "title": d.title, "type": d.type, "content": d.content,
             "linked_items": db.query(models.Link).filter_by(kb_doc_id=d.id).count()}
            for d in qry.order_by(models.KBDocument.id.desc()).all()]


@app.post("/api/kb", status_code=201)
def kb_create(body: schemas.KBCreate, db: Session = Depends(get_db)):
    d = models.KBDocument(**body.model_dump())
    db.add(d)
    db.commit()
    log.info("kb_document_created", extra={"kb_id": d.id, "type": d.type})
    return {"id": d.id, "title": d.title, "type": d.type, "content": d.content, "linked_items": 0}


@app.post("/api/kb/ask")
def kb_ask(body: schemas.KBAsk, db: Session = Depends(get_db)):
    return kb_service.ask_knowledge(db, body.question)


# ------------------------------------------------------------------ frontend
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})
