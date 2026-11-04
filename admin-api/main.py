"""知遇运营后台 API（本机开发版）。

后台直接读取预会面服务的 SQLite 账户、档案与会员权益；后台管理员、登录会话
和审计日志独立存放在同一数据库，避免用户登录与运营权限混用。
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
USER_DATABASE = ROOT.parent / "premeet-backend" / "sessions.sqlite3"
SESSION_COOKIE = "zhiyu_admin_session"
SESSION_TTL = 8 * 60 * 60
Role = Literal["super_admin", "operations", "safety_reviewer", "matchmaker"]
UserStatus = Literal["正常", "已冻结"]


def load_local_env() -> None:
    """Load the local bootstrap configuration without adding another package."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()

ROLE_PERMISSIONS: dict[Role, set[str]] = {
    "super_admin": {"*"},
    "operations": {"dashboard.read", "user.read", "verification.read", "verification.review", "recommendation.read", "membership.manage"},
    "safety_reviewer": {"dashboard.read", "user.read", "safety.read", "safety.handle", "account.freeze", "room.close", "audit.read"},
    "matchmaker": {"dashboard.read", "user.read.assigned", "match.read", "room.read.assigned"},
}

class LoginPayload(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)

class AdminIdentity(BaseModel):
    id: str
    username: str
    role: Role
    permissions: list[str]

class AccountStatePayload(BaseModel):
    verification_status: Literal["未核验", "核验中", "已核验", "核验异常"]
    account_status: UserStatus
    note: str = Field(default="", max_length=300)

class MembershipPayload(BaseModel):
    status: Literal["inactive", "active", "expired", "revoked"]
    plan: str = Field(default="体验会员", max_length=40)
    expires_at: float | None = None
    note: str = Field(default="", max_length=300)

class VerificationReviewPayload(BaseModel):
    verification_status: Literal["未核验", "核验中", "已核验", "核验异常"]
    note: str = Field(default="", max_length=300)

class SafetyReportReviewPayload(BaseModel):
    status: Literal["received", "under_review", "resolved", "dismissed"]
    note: str = Field(default="", max_length=500)

class CloseRoomPayload(BaseModel):
    note: str = Field(min_length=2, max_length=300)

class PremeetReviewPayload(BaseModel):
    status: Literal["pending", "follow_up", "completed", "no_action"]
    note: str = Field(default="", max_length=500)

def connect() -> sqlite3.Connection:
    # FastAPI may run dependency setup and endpoint handlers on different
    # worker threads. Each request still receives its own connection.
    db = sqlite3.connect(USER_DATABASE, check_same_thread=False, timeout=8)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=8000")
    return db

def ensure_schema(db: sqlite3.Connection) -> None:
    # Product tables are normally initialized by premeet-backend. IF NOT EXISTS
    # lets the independent admin service recover cleanly after local restarts.
    db.execute("CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, nickname TEXT NOT NULL, role TEXT NOT NULL, created_at REAL NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS profiles (user_id TEXT PRIMARY KEY, public_data TEXT NOT NULL, private_data TEXT NOT NULL, visibility_data TEXT NOT NULL, version INTEGER NOT NULL, updated_at REAL NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS membership_entitlements (user_id TEXT PRIMARY KEY, status TEXT NOT NULL, plan TEXT NOT NULL, starts_at REAL, expires_at REAL, source TEXT NOT NULL, updated_at REAL NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS admin_account_state (user_id TEXT PRIMARY KEY, verification_status TEXT NOT NULL, account_status TEXT NOT NULL, note TEXT NOT NULL, updated_at REAL NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS rooms (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS premeet_links (candidate_id TEXT NOT NULL REFERENCES accounts(id), member_id TEXT NOT NULL REFERENCES accounts(id), room_id TEXT NOT NULL UNIQUE REFERENCES rooms(id), status TEXT NOT NULL, created_at REAL NOT NULL, PRIMARY KEY(candidate_id,member_id))")
    db.execute("CREATE TABLE IF NOT EXISTS service_groups (id TEXT PRIMARY KEY, room_id TEXT NOT NULL UNIQUE REFERENCES rooms(id), data TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS match_preferences (user_id TEXT PRIMARY KEY REFERENCES accounts(id), data TEXT NOT NULL, updated_at REAL NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS twin_profiles (user_id TEXT PRIMARY KEY, data TEXT NOT NULL, version INTEGER NOT NULL, updated_at REAL NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS admin_events (id TEXT PRIMARY KEY, operator_id TEXT NOT NULL, action TEXT NOT NULL, subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, note TEXT NOT NULL, created_at REAL NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS admin_users (id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL, enabled INTEGER NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS admin_sessions (id TEXT PRIMARY KEY, admin_id TEXT NOT NULL REFERENCES admin_users(id), expires_at REAL NOT NULL, created_at REAL NOT NULL, last_seen_at REAL NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS admin_audit_logs (id TEXT PRIMARY KEY, admin_id TEXT NOT NULL REFERENCES admin_users(id), action TEXT NOT NULL, subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, metadata_json TEXT NOT NULL, created_at REAL NOT NULL)")

def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"{salt.hex()}${digest.hex()}"

def password_matches(password: str, stored: str) -> bool:
    try:
        salt_hex, saved = stored.split("$", 1)
        actual = hash_password(password, bytes.fromhex(salt_hex)).split("$", 1)[1]
        return secrets.compare_digest(actual, saved)
    except (ValueError, AttributeError):
        return False

def bootstrap_admin(db: sqlite3.Connection) -> None:
    if db.execute("SELECT 1 FROM admin_users LIMIT 1").fetchone():
        return
    # Local-only fallback makes the first test possible. Deployment must set env.
    username = os.getenv("ADMIN_BOOTSTRAP_USERNAME", "admin")
    password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "LocalAdmin!2026")
    now = time.time()
    db.execute("INSERT INTO admin_users VALUES (?,?,?,?,?,?,?)", (uuid.uuid4().hex, username, hash_password(password), "super_admin", 1, now, now))

@asynccontextmanager
async def lifespan(_: FastAPI):
    db = connect()
    try:
        ensure_schema(db)
        bootstrap_admin(db)
        db.commit()
    finally:
        db.close()
    yield

app = FastAPI(title="知遇运营后台 API", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5190", "http://localhost:5190"], allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])

def get_db():
    db = connect()
    try:
        # Schema is initialized once in lifespan. Re-running DDL on every
        # request creates unnecessary SQLite write locks when the dashboard
        # loads its three read endpoints concurrently.
        yield db
        db.commit()
    finally:
        db.close()

Db = Annotated[sqlite3.Connection, Depends(get_db)]

def parse_json(value: str | None) -> dict:
    try:
        return json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}

def active_membership(status_value: str | None, starts_at: float | None, expires_at: float | None) -> bool:
    now = time.time()
    return status_value == "active" and (starts_at is None or starts_at <= now) and (expires_at is None or expires_at > now)

def relative_time(value: float | None) -> str:
    if not value:
        return "—"
    delta = max(0, time.time() - value)
    if delta < 60: return "刚刚"
    if delta < 3600: return f"{int(delta // 60)} 分钟前"
    if delta < 86400: return f"{int(delta // 3600)} 小时前"
    return datetime.fromtimestamp(value, UTC).astimezone().strftime("%m-%d %H:%M")

def profile_completion(public: dict, private: dict) -> int:
    fields = ("gender", "height", "education", "city", "relationship_goal", "marital", "housing", "vehicle", "occupation", "birthday")
    return round(sum(bool(public.get(k) or private.get(k)) for k in fields) / len(fields) * 100)

def audit(db: sqlite3.Connection, operator: AdminIdentity, action: str, subject_type: str, subject_id: str, metadata: dict | None = None) -> None:
    now, payload = time.time(), json.dumps(metadata or {}, ensure_ascii=False, separators=(",", ":"))
    db.execute("INSERT INTO admin_audit_logs VALUES (?,?,?,?,?,?,?)", (uuid.uuid4().hex, operator.id, action, subject_type, subject_id, payload, now))
    db.execute("INSERT INTO admin_events VALUES (?,?,?,?,?,?,?)", (uuid.uuid4().hex, operator.id, action, subject_type, subject_id, payload[:300], now))

async def current_admin(request: Request, db: Db, cookie_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> AdminIdentity:
    bearer = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    session_id = bearer or cookie_session
    if not session_id:
        raise HTTPException(status_code=401, detail="请先登录运营后台。")
    row = db.execute("SELECT u.id,u.username,u.role,u.enabled,s.expires_at FROM admin_sessions s JOIN admin_users u ON u.id=s.admin_id WHERE s.id=?", (session_id,)).fetchone()
    if not row or not row["enabled"] or row["expires_at"] <= time.time():
        raise HTTPException(status_code=401, detail="后台登录已失效，请重新登录。")
    if row["role"] not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=403, detail="后台角色配置无效。")
    db.execute("UPDATE admin_sessions SET last_seen_at=? WHERE id=?", (time.time(), session_id))
    # Dashboard requests are issued concurrently. Commit this tiny heartbeat
    # immediately, so it cannot keep a write transaction open while another
    # request is authorizing against the same SQLite file.
    db.commit()
    return AdminIdentity(id=row["id"], username=row["username"], role=row["role"], permissions=sorted(ROLE_PERMISSIONS[row["role"]]))

def require(permission: str):
    async def check(identity: AdminIdentity = Depends(current_admin)) -> AdminIdentity:
        if "*" not in identity.permissions and permission not in identity.permissions:
            raise HTTPException(status_code=403, detail="当前角色没有此操作权限。")
        return identity
    return check

USER_QUERY = """
SELECT a.id,a.nickname,p.public_data,p.private_data,p.updated_at AS profile_updated_at,
       s.verification_status,s.account_status,s.note,s.updated_at AS state_updated_at,
       e.status AS membership_status,e.plan,e.starts_at,e.expires_at,e.source AS membership_source,e.updated_at AS membership_updated_at
FROM accounts a LEFT JOIN profiles p ON p.user_id=a.id
LEFT JOIN admin_account_state s ON s.user_id=a.id
LEFT JOIN membership_entitlements e ON e.user_id=a.id
"""

def user_view(row: sqlite3.Row) -> dict[str, object]:
    public, private = parse_json(row["public_data"]), parse_json(row["private_data"])
    source = row["membership_source"] or "自然注册"
    source = {"local_register": "自然注册", "seed": "本地演示", "admin": "运营开通"}.get(source, source)
    latest = max(row["profile_updated_at"] or 0, row["state_updated_at"] or 0, row["membership_updated_at"] or 0)
    return {"id": row["id"], "name": row["nickname"], "gender": public.get("gender", "未知"), "city": public.get("city", "未填写"), "source": source, "profile": profile_completion(public, private), "verification": row["verification_status"] or "未核验", "membership": "会员" if active_membership(row["membership_status"], row["starts_at"], row["expires_at"]) else "普通用户", "status": row["account_status"] or "正常", "updated": relative_time(latest)}

def verification_queue(db: sqlite3.Connection) -> list[dict[str, object]]:
    items=[]
    for row in db.execute(USER_QUERY + " WHERE COALESCE(s.verification_status,'未核验') != '已核验' ORDER BY s.updated_at ASC, a.created_at ASC"):
        item=user_view(row)
        item.update({"note": row["note"] or "", "reviewed_at": row["state_updated_at"], "queue_reason": "资料待核验" if (row["verification_status"] or "未核验") in ("未核验", "核验中") else "核验异常"})
        items.append(item)
    return items

def safety_report_queue(db: sqlite3.Connection) -> list[dict[str, object]]:
    """Read user-created service-group reports without exposing them to the other participant."""
    items=[]
    names={row["id"]: row["nickname"] for row in db.execute("SELECT id,nickname FROM accounts")}
    for row in db.execute("SELECT id,room_id,data FROM service_groups"):
        group=parse_json(row["data"])
        for report in group.get("safety_reports", []):
            if not isinstance(report, dict) or not report.get("id"): continue
            actor_id=str(report.get("actor_id", ""))
            items.append({
                "id": str(report["id"]), "group_id": row["id"], "room_id": row["room_id"],
                "reporter_id": actor_id, "reporter_name": names.get(actor_id, "已注销用户"),
                "detail": str(report.get("detail", "")), "status": str(report.get("status", "received")),
                "created_at": float(report.get("created_at", 0)), "review_note": str(report.get("review_note", "")),
                "reviewed_at": report.get("reviewed_at"),
            })
    return sorted(items, key=lambda item: item["created_at"], reverse=True)

def premeet_review_queue(db: sqlite3.Connection) -> list[dict[str, object]]:
    """Build an operations view without exposing raw pre-meeting messages."""
    names = {row["id"]: row["nickname"] for row in db.execute("SELECT id,nickname FROM accounts")}
    items: list[dict[str, object]] = []
    for row in db.execute("SELECT id,data FROM rooms"):
        room = parse_json(row["data"])
        if room.get("room_type") != "bound_premeet":
            continue
        candidate_id, member_id = str(room.get("candidate_id", "")), str(room.get("member_id", ""))
        review = room.get("admin_review") if isinstance(room.get("admin_review"), dict) else {}
        items.append({
            "id": row["id"], "candidate_id": candidate_id, "candidate_name": names.get(candidate_id, "已注销用户"),
            "member_id": member_id, "member_name": names.get(member_id, "已注销用户"),
            "status": str(room.get("status", "unknown")), "reason": str(room.get("reason", "")),
            "rounds": int(room.get("rounds", 0) or 0), "started": room.get("started"),
            "deadline": room.get("deadline"), "created_at": room.get("requested_at") or room.get("started") or 0,
            "decisions": room.get("decisions", {}) if isinstance(room.get("decisions"), dict) else {},
            "analysis": str(room.get("result_analysis", "")), "analysis_mode": str(room.get("analysis_mode", "")),
            "review_status": str(review.get("status", "pending")), "review_note": str(review.get("note", "")),
            "reviewed_at": review.get("at"), "reviewed_by": str(review.get("by", "")),
        })
    return sorted(items, key=lambda item: float(item["created_at"] or 0), reverse=True)

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "zhiyu-admin-api", "database": str(USER_DATABASE)}

@app.post("/admin/auth/login", response_model=AdminIdentity)
async def login(payload: LoginPayload, response: Response, db: Db) -> AdminIdentity:
    row = db.execute("SELECT id,username,password_hash,role,enabled FROM admin_users WHERE username=?", (payload.username.strip(),)).fetchone()
    if not row or not row["enabled"] or not password_matches(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="账号或密码不正确。")
    now, session_id = time.time(), secrets.token_urlsafe(32)
    db.execute("INSERT INTO admin_sessions VALUES (?,?,?,?,?)", (session_id, row["id"], now + SESSION_TTL, now, now))
    identity = AdminIdentity(id=row["id"], username=row["username"], role=row["role"], permissions=sorted(ROLE_PERMISSIONS[row["role"]]))
    audit(db, identity, "admin_login", "admin_user", identity.id, {"username": identity.username})
    response.set_cookie(SESSION_COOKIE, session_id, max_age=SESSION_TTL, httponly=True, samesite="lax", secure=False, path="/")
    return identity

@app.post("/admin/auth/logout")
async def logout(response: Response, identity: Annotated[AdminIdentity, Depends(current_admin)], db: Db, cookie_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, bool]:
    if cookie_session: db.execute("DELETE FROM admin_sessions WHERE id=?", (cookie_session,))
    audit(db, identity, "admin_logout", "admin_user", identity.id)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}

@app.get("/admin/me", response_model=AdminIdentity)
async def me(identity: Annotated[AdminIdentity, Depends(current_admin)]) -> AdminIdentity:
    return identity

@app.get("/admin/dashboard")
async def dashboard(db: Db, _: Annotated[AdminIdentity, Depends(require("dashboard.read"))]) -> dict[str, object]:
    registered = db.execute("SELECT COUNT(*) AS n FROM accounts").fetchone()["n"]
    now = time.time()
    members = db.execute("SELECT COUNT(*) AS n FROM membership_entitlements WHERE status='active' AND (starts_at IS NULL OR starts_at<=?) AND (expires_at IS NULL OR expires_at>?)", (now, now)).fetchone()["n"]
    active_rooms = sum(parse_json(row["data"]).get("status") in ("active", "awaiting_candidate") for row in db.execute("SELECT data FROM rooms"))
    safety = db.execute("SELECT COUNT(*) AS n FROM admin_account_state WHERE account_status='已冻结' OR verification_status='核验异常'").fetchone()["n"]
    return {"metrics": [{"label":"注册用户","value":registered,"hint":"来自真实本地账户","tone":"blue"},{"label":"有效会员","value":members,"hint":f"会员转化率 {round(members / registered * 100, 1) if registered else 0}%","tone":"purple"},{"label":"进行中预会面","value":active_rooms,"hint":"读取房间状态","tone":"pink"},{"label":"待处理安全事项","value":safety,"hint":"冻结或核验异常账户","tone":"orange"}], "pending_tasks":[{"title":"资料核验待处理","count":db.execute("SELECT COUNT(*) AS n FROM admin_account_state WHERE verification_status IN ('未核验','核验中')").fetchone()["n"],"description":"实名认证、照片一致性与资料补充","action":"进入核验队列"},{"title":"异常预会面","count":safety,"description":"冻结账户与核验异常需人工查看","action":"查看安全事项"}], "generated_at": datetime.now(UTC).isoformat()}

@app.get("/admin/users")
async def list_users(db: Db, _: Annotated[AdminIdentity, Depends(require("user.read"))], keyword: str = "", account_status: str = "全部", page: int = 1, page_size: int = 20) -> dict[str, object]:
    if page < 1 or not 1 <= page_size <= 100: raise HTTPException(status_code=422, detail="分页参数不正确。")
    rows = [user_view(row) for row in db.execute(USER_QUERY + " ORDER BY a.created_at DESC")]
    needle = keyword.strip().lower()
    if needle: rows = [item for item in rows if needle in str(item["name"]).lower() or needle in str(item["id"]).lower() or needle in str(item["city"]).lower()]
    if account_status != "全部": rows = [item for item in rows if item["status"] == account_status]
    total = len(rows)
    return {"items": rows[(page - 1) * page_size:page * page_size], "total": total, "page": page, "page_size": page_size}

@app.get("/admin/users/{user_id}")
async def user_detail(user_id: str, db: Db, _: Annotated[AdminIdentity, Depends(require("user.read"))]) -> dict[str, object]:
    row = db.execute(USER_QUERY + " WHERE a.id=?", (user_id,)).fetchone()
    if not row: raise HTTPException(status_code=404, detail="未找到该用户。")
    item = user_view(row); item["public_profile"] = parse_json(row["public_data"])
    return item

@app.post("/admin/users/{user_id}/account-state")
async def update_account_state(user_id: str, payload: AccountStatePayload, db: Db, identity: Annotated[AdminIdentity, Depends(require("account.freeze"))]) -> dict[str, object]:
    if not db.execute("SELECT 1 FROM accounts WHERE id=?", (user_id,)).fetchone(): raise HTTPException(status_code=404, detail="未找到该用户。")
    db.execute("INSERT INTO admin_account_state VALUES (?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET verification_status=excluded.verification_status,account_status=excluded.account_status,note=excluded.note,updated_at=excluded.updated_at", (user_id, payload.verification_status, payload.account_status, payload.note.strip(), time.time()))
    audit(db, identity, "update_account_state", "account", user_id, payload.model_dump())
    return {"id": user_id, "verification_status": payload.verification_status, "account_status": payload.account_status}

@app.post("/admin/users/{user_id}/membership")
async def update_membership(user_id: str, payload: MembershipPayload, db: Db, identity: Annotated[AdminIdentity, Depends(require("membership.manage"))]) -> dict[str, object]:
    if not db.execute("SELECT 1 FROM accounts WHERE id=?", (user_id,)).fetchone(): raise HTTPException(status_code=404, detail="未找到该用户。")
    now = time.time(); starts_at = now if payload.status == "active" else None
    db.execute("INSERT INTO membership_entitlements VALUES (?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET status=excluded.status,plan=excluded.plan,starts_at=excluded.starts_at,expires_at=excluded.expires_at,source=excluded.source,updated_at=excluded.updated_at", (user_id, payload.status, payload.plan.strip(), starts_at, payload.expires_at, "admin", now))
    if payload.status == "active": db.execute("INSERT OR IGNORE INTO twin_profiles VALUES (?,?,?,?)", (user_id, json.dumps({"voice":{},"relationship_style":{},"answer_policy":{"never_answer":[]},"confirmed_answers":{},"topic_answers":{},"priority_topics":[]}, ensure_ascii=False), 1, now))
    preference_row = db.execute("SELECT data FROM match_preferences WHERE user_id=?", (user_id,)).fetchone()
    preferences = parse_json(preference_row["data"] if preference_row else None)
    preferences.setdefault("accept_distance", False)
    preferences.setdefault("preferred_cities", [])
    preferences.setdefault("relationship_priority", "认真相处")
    preferences.setdefault("max_active_premeet", 3)
    preferences["premeet_enabled"] = payload.status == "active"
    db.execute("INSERT INTO match_preferences (user_id,data,updated_at) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at", (user_id, json.dumps(preferences, ensure_ascii=False), now))
    audit(db, identity, "update_membership", "membership", user_id, payload.model_dump())
    return {"id": user_id, "status": payload.status, "plan": payload.plan, "expires_at": payload.expires_at}

@app.get("/admin/verifications")
async def list_verifications(db: Db, _: Annotated[AdminIdentity, Depends(require("verification.read"))]) -> dict[str, object]:
    items=verification_queue(db)
    return {"items": items, "total": len(items)}

@app.post("/admin/verifications/{user_id}/review")
async def review_verification(user_id: str, payload: VerificationReviewPayload, db: Db, identity: Annotated[AdminIdentity, Depends(require("verification.review"))]) -> dict[str, object]:
    previous=db.execute("SELECT verification_status,account_status FROM admin_account_state WHERE user_id=?", (user_id,)).fetchone()
    if not previous: raise HTTPException(status_code=404, detail="未找到该用户的核验记录。")
    account_status="已冻结" if previous["account_status"]=="已冻结" else "正常"
    db.execute("UPDATE admin_account_state SET verification_status=?,account_status=?,note=?,updated_at=? WHERE user_id=?", (payload.verification_status, account_status, payload.note.strip(), time.time(), user_id))
    audit(db, identity, "review_verification", "account", user_id, payload.model_dump())
    return {"id":user_id,"verification_status":payload.verification_status,"account_status":account_status}

@app.get("/admin/safety-reports")
async def list_safety_reports(db: Db, _: Annotated[AdminIdentity, Depends(require("safety.read"))]) -> dict[str, object]:
    items=safety_report_queue(db)
    return {"items": items, "total": len(items)}

@app.post("/admin/safety-reports/{group_id}/{report_id}/review")
async def review_safety_report(group_id: str, report_id: str, payload: SafetyReportReviewPayload, db: Db, identity: Annotated[AdminIdentity, Depends(require("safety.handle"))]) -> dict[str, object]:
    row=db.execute("SELECT data FROM service_groups WHERE id=?", (group_id,)).fetchone()
    if not row: raise HTTPException(status_code=404, detail="未找到对应服务群。")
    group=parse_json(row["data"])
    report=next((item for item in group.get("safety_reports", []) if item.get("id")==report_id), None)
    if not report: raise HTTPException(status_code=404, detail="未找到该安全投诉。")
    report.update({"status":payload.status,"review_note":payload.note.strip(),"reviewed_at":time.time(),"reviewed_by":identity.username})
    group.setdefault("events", []).append({"type":"safety_report_reviewed","report_id":report_id,"at":time.time()})
    db.execute("UPDATE service_groups SET data=? WHERE id=?", (json.dumps(group,ensure_ascii=False), group_id))
    audit(db, identity, "review_safety_report", "safety_report", report_id, {"group_id":group_id,**payload.model_dump()})
    return {"id":report_id,"status":payload.status}

@app.post("/admin/rooms/{room_id}/close")
async def close_room(room_id: str, payload: CloseRoomPayload, db: Db, identity: Annotated[AdminIdentity, Depends(require("room.close"))]) -> dict[str, object]:
    row=db.execute("SELECT data FROM rooms WHERE id=?", (room_id,)).fetchone()
    if not row: raise HTTPException(status_code=404, detail="未找到预会面房间。")
    room=parse_json(row["data"])
    room.update({"status":"ended","reason":f"运营已关闭：{payload.note.strip()}","closed_by_admin":identity.username,"closed_at":time.time()})
    db.execute("UPDATE rooms SET data=? WHERE id=?", (json.dumps(room,ensure_ascii=False), room_id))
    db.execute("UPDATE premeet_links SET status='ended' WHERE room_id=?", (room_id,))
    audit(db, identity, "close_room", "room", room_id, payload.model_dump())
    return {"id":room_id,"status":"ended"}

@app.get("/admin/premeet-reviews")
async def list_premeet_reviews(db: Db, _: Annotated[AdminIdentity, Depends(require("recommendation.read"))]) -> dict[str, object]:
    items = premeet_review_queue(db)
    return {"items": items, "total": len(items)}

@app.post("/admin/premeet-reviews/{room_id}")
async def review_premeet(room_id: str, payload: PremeetReviewPayload, db: Db, identity: Annotated[AdminIdentity, Depends(require("recommendation.read"))]) -> dict[str, object]:
    row = db.execute("SELECT data FROM rooms WHERE id=?", (room_id,)).fetchone()
    if not row: raise HTTPException(status_code=404, detail="未找到预会面房间。")
    room = parse_json(row["data"])
    if room.get("room_type") != "bound_premeet": raise HTTPException(status_code=422, detail="该房间不是可人工复盘的预会面。")
    review = {"status": payload.status, "note": payload.note.strip(), "at": time.time(), "by": identity.username}
    room["admin_review"] = review
    db.execute("UPDATE rooms SET data=? WHERE id=?", (json.dumps(room, ensure_ascii=False), room_id))
    audit(db, identity, "review_premeet", "premeet_room", room_id, payload.model_dump())
    return {"id": room_id, **review}

@app.get("/admin/audit-logs")
async def audit_logs(db: Db, _: Annotated[AdminIdentity, Depends(require("audit.read"))], page: int = 1, page_size: int = 30) -> dict[str, object]:
    page, page_size = max(1, page), min(100, max(1, page_size))
    total = db.execute("SELECT COUNT(*) AS n FROM admin_audit_logs").fetchone()["n"]
    rows = db.execute("SELECT l.id,l.action,l.subject_type,l.subject_id,l.metadata_json,l.created_at,u.username,u.role FROM admin_audit_logs l JOIN admin_users u ON u.id=l.admin_id ORDER BY l.created_at DESC LIMIT ? OFFSET ?", (page_size, (page - 1) * page_size)).fetchall()
    return {"items":[{**dict(row),"metadata":parse_json(row["metadata_json"]),"created_at":datetime.fromtimestamp(row["created_at"], UTC).isoformat()} for row in rows],"total":total,"page":page,"page_size":page_size}
