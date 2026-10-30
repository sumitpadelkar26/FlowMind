"""All AI interaction lives here.

Reliability pipeline for every call:
  1. no key configured      -> skip AI, use rule-based fallback
  2. primary model, 2 tries -> timeout, retry once on transient errors
  3. fallback model, 2 tries
  4. strip ```json fences, extract the JSON object, validate with Pydantic
  5. anything still failing -> rule-based fallback; the API never returns a 500
Every attempt is logged with latency + outcome. Prompts/keys are never logged.
"""
import json
import re
import time
from datetime import date
from typing import Optional, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .config import settings
from .logger import get_logger
from .schemas import (BriefOut, NudgeOut, ReadinessAdvice, RecapItem, RecapOut)

log = get_logger("ai")
T = TypeVar("T", bound=BaseModel)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"


class AIError(Exception):
    def __init__(self, msg: str, retryable: bool = True):
        super().__init__(msg)
        self.retryable = retryable


def ai_enabled() -> bool:
    return bool(settings.ai_api_key)


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise AIError("no JSON object in model output")
    return json.loads(text[start:end + 1])


def _gemini(system: str, prompt: str, model: str) -> str:
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    try:
        r = httpx.post(GEMINI_URL.format(model=model), json=body,
                       headers={"x-goog-api-key": settings.ai_api_key, "Content-Type": "application/json"},
                       timeout=settings.ai_timeout)
    except httpx.TimeoutException:
        raise AIError("timeout")
    except httpx.HTTPError as e:
        raise AIError(f"network error: {type(e).__name__}")
    if r.status_code in (400, 401, 403, 404):
        raise AIError(f"http {r.status_code} (check AI_API_KEY / AI_MODEL)", retryable=False)
    if r.status_code == 429 or r.status_code >= 500:
        raise AIError(f"http {r.status_code}")
    if r.status_code != 200:
        raise AIError(f"http {r.status_code}", retryable=False)
    data = r.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError, TypeError):
        raise AIError("empty or blocked response")


def embed_texts(texts: list[str], task_type: str) -> list[list[float]]:
    """Embed documents or queries for semantic retrieval. Text and key are never logged."""
    if not ai_enabled():
        raise AIError("AI key not configured", retryable=False)
    if not texts:
        return []
    model = settings.ai_embedding_model
    requests = [{
        "model": f"models/{model}",
        "content": {"parts": [{"text": text[:7000]}]},
        "taskType": task_type,
        "outputDimensionality": 768,
    } for text in texts]
    body = {"requests": requests}
    for attempt in (1, 2):
        t0 = time.perf_counter()
        try:
            response = httpx.post(
                GEMINI_EMBED_URL.format(model=model), json=body,
                headers={"x-goog-api-key": settings.ai_api_key, "Content-Type": "application/json"},
                timeout=settings.ai_timeout,
            )
        except httpx.TimeoutException:
            error = "timeout"
            retryable = True
        except httpx.HTTPError as e:
            error = f"network error: {type(e).__name__}"
            retryable = True
        else:
            if response.status_code == 200:
                try:
                    vectors = [item["values"] for item in response.json()["embeddings"]]
                    if len(vectors) != len(texts):
                        raise ValueError("embedding count mismatch")
                    normalized = []
                    for vector in vectors:
                        norm = sum(float(value) ** 2 for value in vector) ** 0.5
                        if not norm:
                            raise ValueError("empty embedding")
                        normalized.append([float(value) / norm for value in vector])
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    error = "invalid embedding response"
                    retryable = False
                else:
                    ms = round((time.perf_counter() - t0) * 1000)
                    log.info("ai_call", extra={"task": "kb_embedding", "model": model, "attempt": attempt,
                                               "latency_ms": ms, "outcome": "success", "input_count": len(texts)})
                    return normalized
            else:
                error = f"http {response.status_code}"
                retryable = response.status_code == 429 or response.status_code >= 500
        ms = round((time.perf_counter() - t0) * 1000)
        log.warning("ai_call", extra={"task": "kb_embedding", "model": model, "attempt": attempt,
                                      "latency_ms": ms, "outcome": "error", "error": error,
                                      "input_count": len(texts), "will_retry": retryable and attempt == 1})
        if not retryable or attempt == 2:
            raise AIError(error, retryable=retryable)
        time.sleep(0.25 * attempt)
    raise AIError("embedding failed")


def call_json(task: str, system: str, prompt: str, schema: Type[T]) -> tuple[Optional[T], dict]:
    """Returns (validated_model_or_None, meta). Never raises."""
    meta = {"ai_used": False, "fallback": True, "model": None, "latency_ms": None, "notice": None}
    if not ai_enabled():
        log.warning("ai_call", extra={"task": task, "outcome": "skipped_no_key"})
        meta["notice"] = "AI key not configured - showing rule-based result."
        return None, meta

    models = [settings.ai_model] + ([settings.ai_fallback_model]
                                    if settings.ai_fallback_model and settings.ai_fallback_model != settings.ai_model else [])
    last_err = "unknown"
    for model in models:
        for attempt in (1, 2):
            t0 = time.perf_counter()
            try:
                raw = _gemini(system, prompt, model)
                obj = schema.model_validate(_extract_json(raw))
                ms = round((time.perf_counter() - t0) * 1000)
                log.info("ai_call", extra={"task": task, "model": model, "attempt": attempt,
                                           "latency_ms": ms, "outcome": "success", "prompt_chars": len(prompt)})
                meta.update(ai_used=True, fallback=False, model=model, latency_ms=ms)
                return obj, meta
            except (json.JSONDecodeError, ValidationError, AIError) as e:
                ms = round((time.perf_counter() - t0) * 1000)
                last_err = str(e)[:200] if not isinstance(e, ValidationError) else "schema validation failed"
                retryable = getattr(e, "retryable", True)
                log.warning("ai_call", extra={"task": task, "model": model, "attempt": attempt, "latency_ms": ms,
                                              "outcome": "error", "error": last_err, "will_retry": retryable and attempt == 1})
                if not retryable:
                    break
            except Exception as e:  # truly unexpected - still must not crash the request
                log.error("ai_call_unexpected", exc_info=True, extra={"task": task, "model": model})
                last_err = type(e).__name__
                break
    meta["notice"] = "AI is unavailable right now - showing a rule-based result you can edit."
    log.error("ai_fallback_used", extra={"task": task, "last_error": last_err})
    return None, meta


# ---------------------------------------------------------------- recap
RECAP_SYSTEM = (
    "You turn messy meeting notes, chats or transcripts into a structured recap. "
    "Return ONLY a JSON object, no markdown, with keys: "
    '"summary" (2-4 sentences), "decisions" (array of strings, only things actually decided), '
    '"action_items" (array of {"title": string, "owner": string, "due_date": "YYYY-MM-DD" or null}). '
    "Never invent facts. If no owner is stated, use an empty string. If no date is stated or it cannot be "
    "resolved, use null. Resolve relative dates (e.g. 'by Friday') against the provided today date."
)


def extract_recap(raw_text: str, known_people: list[str]) -> dict:
    raw_text = raw_text[:12000]
    prompt = (f"Today is {date.today().isoformat()}.\nKnown team members: {', '.join(known_people) or 'unknown'}.\n"
              f"Use the exact spelling of known team members for owners.\n\nRAW NOTES:\n{raw_text}")
    out, meta = call_json("extract_recap", RECAP_SYSTEM, prompt, RecapOut)
    if out is None:
        out = _rule_recap(raw_text, known_people)
    else:
        out.action_items = [i for i in out.action_items if i.title.strip()]
    return {"recap": out.model_dump(mode="json"), **meta}


_ACTION_RE = re.compile(r"^(?P<owner>[A-Z][a-z]+)\s+(?:will|to|should|needs to|is going to|has to)\s+(?P<task>.+)$")
_DEC_WORDS = ("decided", "agreed", "approved", "decision", "we will", "going with", "chosen")


def _rule_recap(text: str, people: list[str]) -> RecapOut:
    lines = [re.sub(r"^[\-\*\d\.\)\s]+", "", l).strip() for l in text.splitlines() if l.strip()]
    sentences = [s.strip() for l in lines for s in re.split(r"(?<=[.!?])\s+", l) if s.strip()]
    decisions, items = [], []
    for s in sentences:
        low = s.lower()
        m = _ACTION_RE.match(s.rstrip("."))
        if m and (not people or m.group("owner") in people or len(sentences) < 40):
            items.append(RecapItem(title=(lambda t: t[:1].upper() + t[1:])(m.group("task")[:290]), owner=m.group("owner")))
        elif any(w in low for w in _DEC_WORDS):
            decisions.append(s[:900])
    summary = " ".join(sentences[:2])[:600] or "No summary could be generated."
    return RecapOut(summary=summary, decisions=decisions[:8], action_items=items[:12])


# ---------------------------------------------------------------- brief
BRIEF_SYSTEM = (
    "You write a short catch-up brief for someone who missed a meeting or is taking over work. "
    "Use ONLY the facts provided. Return ONLY JSON with keys: "
    '"headline" (one sentence), "what_was_decided" (array, max 5), "still_open" (array, max 6, include owner and due), '
    '"your_actions" (array, items this person owns, or []), "watch_out" (array, max 3 risks such as overdue or unowned items). '
    "Be concise and concrete."
)


def catchup_brief(ctx: dict, for_person: str) -> dict:
    prompt = f"Reader: {for_person or 'someone new to this work'}\nToday: {date.today().isoformat()}\nFACTS:\n{json.dumps(ctx, default=str)[:12000]}"
    out, meta = call_json("catchup_brief", BRIEF_SYSTEM, prompt, BriefOut)
    if out is None:
        out = _rule_brief(ctx, for_person)
    return {"brief": out.model_dump(), **meta}


def _fmt_item(i: dict) -> str:
    return f"{i['title']} ({i['owner'] or 'unowned'}, due {i['due_date'] or 'no date'})"


def _rule_brief(ctx: dict, person: str) -> BriefOut:
    open_items = [i for i in ctx["action_items"] if i["status"] in ("open", "in_progress")]
    mine = [i for i in open_items if person and i["owner"].lower() == person.lower()]
    watch = [f"Overdue: {i['title']}" for i in open_items if i["overdue"]][:3]
    watch += [f"No owner: {i['title']}" for i in open_items if not i["owner"]][: max(0, 3 - len(watch))]
    return BriefOut(
        headline=ctx["summary"].split(". ")[0][:200] or f"Catch-up for {ctx['title']}",
        what_was_decided=ctx["decisions"][:5],
        still_open=[_fmt_item(i) for i in open_items][:6],
        your_actions=[_fmt_item(i) for i in mine],
        watch_out=watch,
    )


# ---------------------------------------------------------------- readiness (special feature)
READY_SYSTEM = (
    "You review a meeting/handover readiness check. You are given a score and a list of failed checks. "
    'Return ONLY JSON: {"verdict": one sentence, "fixes": array of max 5 short imperative fixes, most important first}. '
    "Do not change or recompute the score. Mention specific item titles or people where helpful."
)


def readiness_advice(score: int, issues: list[dict], ctx: dict) -> dict:
    if not issues:
        return {"verdict": "Ready to hand over - nothing blocking.", "fixes": [], "ai_used": False,
                "fallback": False, "model": None, "latency_ms": None, "notice": None}
    prompt = f"Score: {score}/100\nFailed checks: {json.dumps(issues)}\nContext: {json.dumps(ctx, default=str)[:6000]}"
    out, meta = call_json("readiness_advice", READY_SYSTEM, prompt, ReadinessAdvice)
    if out is None:
        out = ReadinessAdvice(
            verdict=f"Score {score}/100 - {len(issues)} thing(s) need attention before handover.",
            fixes=[i["fix"] for i in issues][:5])
    return {**out.model_dump(), **meta}


# ---------------------------------------------------------------- nudge
NUDGE_SYSTEM = (
    "You draft a short, warm, professional follow-up message (2-4 sentences) reminding someone about an open action item. "
    'Return ONLY JSON: {"message": string}. Mention the task, due date and ask for a status or blocker. No greeting emoji.'
)


def draft_nudge(item: dict) -> dict:
    prompt = f"Today: {date.today().isoformat()}\nItem: {json.dumps(item, default=str)}"
    out, meta = call_json("draft_nudge", NUDGE_SYSTEM, prompt, NudgeOut)
    if out is None:
        late = f" It was due {item['due_date']}." if item.get("overdue") else (f" It is due {item['due_date']}." if item.get("due_date") else "")
        out = NudgeOut(message=f"Hi {item['owner'] or 'there'}, a quick check-in on \"{item['title']}\".{late} "
                               f"Could you share a short status update, or let me know if anything is blocking you?")
    return {"message": out.message, **meta}
