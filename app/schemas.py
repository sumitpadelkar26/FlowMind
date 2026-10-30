"""Pydantic models: request validation AND the contracts we demand from the AI."""
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

MeetingType = Literal["meeting", "handover"]
MeetingStatus = Literal["planned", "held", "closed"]
ItemStatus = Literal["open", "in_progress", "done", "dropped"]
ItemPriority = Literal["low", "medium", "high", "urgent"]
Rsvp = Literal["pending", "accepted", "declined"]


def _clean(v: str) -> str:
    return " ".join(v.split())


class ParticipantIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(default="", max_length=200)
    rsvp: Rsvp = "pending"
    attended: bool = False

    @field_validator("name")
    @classmethod
    def _n(cls, v):
        return _clean(v)

    @field_validator("email")
    @classmethod
    def _e(cls, v):
        v = v.strip()
        if v and ("@" not in v or "." not in v.split("@")[-1]):
            raise ValueError("email looks invalid")
        return v


class ParticipantUpdate(BaseModel):
    rsvp: Optional[Rsvp] = None
    attended: Optional[bool] = None


class MeetingCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    type: MeetingType = "meeting"
    agenda: str = Field(default="", max_length=5000)
    date: date
    notes: str = Field(default="", max_length=50000)
    participants: list[ParticipantIn] = []

    @field_validator("title")
    @classmethod
    def _t(cls, v):
        return _clean(v)


class MeetingUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    agenda: Optional[str] = Field(default=None, max_length=5000)
    date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=50000)
    summary: Optional[str] = Field(default=None, max_length=5000)
    status: Optional[MeetingStatus] = None


class DecisionCreate(BaseModel):
    text: str = Field(min_length=3, max_length=1000)


class ActionItemCreate(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    owner: str = Field(default="", max_length=100)
    due_date: Optional[date] = None
    priority: ItemPriority = "medium"
    blocker: str = Field(default="", max_length=1000)

    @field_validator("due_date")
    @classmethod
    def _future(cls, v):
        if v is not None and v < date.today():
            raise ValueError("due_date cannot be in the past")
        return v

    @field_validator("title", "owner", "blocker")
    @classmethod
    def _c(cls, v):
        return _clean(v)


class ActionItemUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=300)
    owner: Optional[str] = Field(default=None, max_length=100)
    due_date: Optional[date] = None
    priority: Optional[ItemPriority] = None
    blocker: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[ItemStatus] = None
    outcome: Optional[str] = Field(default=None, max_length=2000)
    note: Optional[str] = Field(default=None, max_length=500)


class CarryForward(BaseModel):
    target_meeting_id: Optional[int] = None
    new_title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    new_date: Optional[date] = None
    new_type: MeetingType = "meeting"
    item_ids: Optional[list[int]] = None  # default: all open / in-progress items

    @field_validator("item_ids")
    @classmethod
    def _unique_items(cls, v):
        if v is not None and len(v) != len(set(v)):
            raise ValueError("Select each action item only once")
        return v


class ReassignAll(BaseModel):
    from_owner: str = Field(min_length=1, max_length=100)
    to_owner: str = Field(min_length=1, max_length=100)
    note: str = Field(default="Owner on leave", max_length=300)


class FirstAdminCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        return _clean(v)

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        v = v.strip().lower()
        if "@" not in v or "." not in v.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address")
        return v


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        return v.strip().lower()


class UserCreate(FirstAdminCreate):
    role: Literal["admin", "member"] = "member"


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    role: Optional[Literal["admin", "member"]] = None
    active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=12, max_length=128)

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        return _clean(v) if v is not None else v


class KBCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    type: Literal["doc", "past_meeting"] = "doc"
    content: str = Field(min_length=20, max_length=30000)


class KBAsk(BaseModel):
    question: str = Field(min_length=3, max_length=1200)

    @field_validator("question")
    @classmethod
    def _question(cls, v):
        return _clean(v)


class RecapRequest(BaseModel):
    raw_text: str = Field(min_length=20, max_length=30000)


# ---------- AI contracts (what we require the model to return) ----------
class RecapItem(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    owner: str = ""
    due_date: Optional[date] = None

    @field_validator("owner", mode="before")
    @classmethod
    def _o(cls, v):
        return "" if v is None else str(v).strip()


class RecapOut(BaseModel):
    summary: str = Field(min_length=1, max_length=3000)
    decisions: list[str] = []
    action_items: list[RecapItem] = []


class RecapApply(BaseModel):
    summary: str = Field(default="", max_length=5000)
    decisions: list[str] = []
    action_items: list[RecapItem] = []


class BriefOut(BaseModel):
    headline: str
    what_was_decided: list[str] = []
    still_open: list[str] = []
    your_actions: list[str] = []
    watch_out: list[str] = []


class KBPick(BaseModel):
    doc_id: int
    relevant: bool
    reason: str = ""


class KBRerankOut(BaseModel):
    picks: list[KBPick] = []


class KBAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=5000)
    cited_document_ids: list[int] = []


class ReadinessAdvice(BaseModel):
    verdict: str
    fixes: list[str] = []


class NudgeOut(BaseModel):
    message: str = Field(min_length=5)
