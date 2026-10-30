import os, hashlib, secrets, asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError, PasswordHashInvalidError, FloodWaitError
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID
import asyncpg
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field

DATABASE_URL=os.getenv("DATABASE_URL","")
JWT_SECRET=os.getenv("JWT_SECRET","")
TOKEN_MINUTES=int(os.getenv("TOKEN_MINUTES","720"))
TELEGRAM_API_ID=os.getenv("TELEGRAM_API_ID","")
TELEGRAM_API_HASH=os.getenv("TELEGRAM_API_HASH","")
telegram_challenges={}
telegram_rate_limits={}
pool=None
pwd=CryptContext(schemes=["bcrypt"],deprecated="auto")
oauth=OAuth2PasswordBearer(tokenUrl="/auth/token")

@asynccontextmanager
async def lifespan(app):
    global pool
    if DATABASE_URL:
        pool=await asyncpg.create_pool(DATABASE_URL,min_size=1,max_size=5,command_timeout=15)
    yield
    if pool: await pool.close()

app=FastAPI(title="SKYGRID API",version="0.2.0",lifespan=lifespan)
origins=[x.strip() for x in os.getenv("CORS_ORIGINS","http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=["GET","POST","DELETE","OPTIONS"],allow_headers=["Authorization","Content-Type"])

def database():
    if pool is None: raise HTTPException(503,"Database not configured; set DATABASE_URL")
    return pool
def secret():
    if len(JWT_SECRET)<32: raise HTTPException(503,"Set JWT_SECRET to a random value of at least 32 characters")
    return JWT_SECRET

class Register(BaseModel):
    email: EmailStr
    display_name: str=Field(min_length=1,max_length=80)
    password: str=Field(min_length=10,max_length=128)
class GroupCreate(BaseModel):
    name: str=Field(min_length=1,max_length=80)
class JoinGroup(BaseModel):
    invite_code: str=Field(min_length=20,max_length=200)
class FileMeta(BaseModel):
    original_name: str=Field(min_length=1,max_length=255)
    mime_type: str=Field(min_length=1,max_length=120)
    size_bytes: int=Field(ge=0,le=5_000_000_000)
    group_id: UUID|None=None

async def authenticated(token: Annotated[str,Depends(oauth)]):
    try:
        payload=jwt.decode(token,secret(),algorithms=["HS256"])
        uid=UUID(payload["sub"])
    except (JWTError,ValueError,KeyError):
        raise HTTPException(401,"Invalid or expired token",headers={"WWW-Authenticate":"Bearer"})
    async with database().acquire() as c:
        row=await c.fetchrow("SELECT id,email,display_name,created_at FROM skygrid.users WHERE id=$1",uid)
    if not row: raise HTTPException(401,"User not found")
    return dict(row)
User=Annotated[dict,Depends(authenticated)]

@app.get("/")
async def root(): return {"name":"SKYGRID","message":"Your Files. Your Space.","docs":"/docs"}
@app.get("/health")
async def health(): return {"status":"ok","service":"skygrid-api"}
@app.get("/ready")
async def ready(): return {"ready":pool is not None,"database":"connected" if pool else "not_configured","storage":"not_configured"}

@app.post("/auth/register",status_code=201)
async def register(body:Register):
    p=database(); secret()
    try:
        async with p.acquire() as c:
            row=await c.fetchrow("INSERT INTO skygrid.users(email,display_name,password_hash) VALUES($1,$2,$3) RETURNING id,email,display_name,created_at",body.email.lower().strip(),body.display_name.strip(),pwd.hash(body.password))
    except asyncpg.UniqueViolationError: raise HTTPException(409,"An account with this email already exists")
    return dict(row)
@app.post("/auth/token")
async def login(form:Annotated[OAuth2PasswordRequestForm,Depends()]):
    p=database(); s=secret()
    async with p.acquire() as c: row=await c.fetchrow("SELECT id,email,display_name,password_hash FROM skygrid.users WHERE email=$1",form.username.lower().strip())
    if not row or not pwd.verify(form.password,row["password_hash"]): raise HTTPException(401,"Incorrect email or password",headers={"WWW-Authenticate":"Bearer"})
    now=datetime.now(timezone.utc)
    return {"access_token":jwt.encode({"sub":str(row["id"]),"iat":now,"exp":now+timedelta(minutes=TOKEN_MINUTES)},s,algorithm="HS256"),"token_type":"bearer","expires_in":TOKEN_MINUTES*60}

class TelegramSendCode(BaseModel):
    phone: str=Field(min_length=7,max_length=24)
class TelegramVerifyCode(BaseModel):
    challenge_id: str=Field(min_length=20,max_length=100)
    code: str|None=Field(default=None,min_length=3,max_length=12)
    password: str|None=Field(default=None,min_length=1,max_length=256)

def telegram_config():
    if not TELEGRAM_API_ID.isdigit() or len(TELEGRAM_API_HASH)<20:
        raise HTTPException(503,"Telegram API credentials are not configured on the server")
    return int(TELEGRAM_API_ID),TELEGRAM_API_HASH

def issue_token(user_id, s):
    now=datetime.now(timezone.utc)
    return {"access_token":jwt.encode({"sub":str(user_id),"iat":now,"exp":now+timedelta(minutes=TOKEN_MINUTES)},s,algorithm="HS256"),"token_type":"bearer","expires_in":TOKEN_MINUTES*60}

@app.post("/auth/telegram/send-code")
async def telegram_send_code(body:TelegramSendCode):
    api_id,api_hash=telegram_config()
    database(); secret()
    phone="".join(ch for ch in body.phone if ch.isdigit() or ch=="+")
    if not phone.startswith("+") or len(phone)<8:
        raise HTTPException(422,"Enter phone number with country code, e.g. +91...")
    now=asyncio.get_running_loop().time()
    recent=[t for t in telegram_rate_limits.get(phone,[]) if now-t<600]
    if len(recent)>=3:
        raise HTTPException(429,"Too many OTP requests. Wait 10 minutes before trying again.")
    recent.append(now); telegram_rate_limits[phone]=recent
    client=TelegramClient(StringSession(),api_id,api_hash)
    try:
        await client.connect()
        sent=await client.send_code_request(phone)
    except FloodWaitError as exc:
        await client.disconnect()
        raise HTTPException(429,f"Telegram rate limit. Retry after {exc.seconds} seconds.")
    except Exception:
        await client.disconnect()
        raise HTTPException(502,"Telegram could not send a code. Check the number and try again.")
    challenge_id=secrets.token_urlsafe(32)
    telegram_challenges[challenge_id]={"client":client,"phone":phone,"phone_code_hash":sent.phone_code_hash,"expires":now+300,"code_verified":False}
    return {"challenge_id":challenge_id,"expires_in":300,"message":"Verification code requested from Telegram."}

@app.post("/auth/telegram/verify-code")
async def telegram_verify_code(body:TelegramVerifyCode):
    api_id,api_hash=telegram_config()
    p=database(); s=secret()
    challenge=telegram_challenges.get(body.challenge_id)
    now_loop=asyncio.get_running_loop().time()
    if not challenge or challenge["expires"]<now_loop:
        if challenge:
            try: await challenge["client"].disconnect()
            except Exception: pass
            telegram_challenges.pop(body.challenge_id,None)
        raise HTTPException(400,"Code request expired. Request a new code.")
    client=challenge["client"]
    try:
        if not challenge["code_verified"]:
            if not body.code:
                raise HTTPException(422,"Enter the Telegram verification code.")
            await client.sign_in(phone=challenge["phone"],code=body.code,phone_code_hash=challenge["phone_code_hash"])
            challenge["code_verified"]=True
        elif body.password:
            await client.sign_in(password=body.password)
        else:
            raise HTTPException(422,"This Telegram account requires its 2-step verification password.")
    except SessionPasswordNeededError:
        challenge["code_verified"]=True
        return {"requires_password":True,"message":"Enter your Telegram 2-step verification password."}
    except (PhoneCodeInvalidError,PhoneCodeExpiredError):
        raise HTTPException(400,"Telegram code is invalid or expired.")
    except PasswordHashInvalidError:
        raise HTTPException(400,"Telegram 2-step verification password is incorrect.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502,"Telegram sign-in failed. Request a fresh code and try again.")
    try:
        me=await client.get_me()
        if not me:
            raise HTTPException(401,"Telegram did not return an authenticated user.")
        email=f"telegram-{me.id}@accounts.skygrid.invalid"
        display_name=" ".join(x for x in [getattr(me,"first_name",None),getattr(me,"last_name",None)] if x)[:80] or "Telegram User"
        async with p.acquire() as conn:
            async with conn.transaction():
                row=await conn.fetchrow("SELECT id,email,display_name,created_at FROM skygrid.users WHERE email=$1",email)
                if not row:
                    row=await conn.fetchrow("INSERT INTO skygrid.users(email,display_name,password_hash) VALUES($1,$2,$3) RETURNING id,email,display_name,created_at",email,display_name,pwd.hash(secrets.token_urlsafe(32)))
                else:
                    row=await conn.fetchrow("UPDATE skygrid.users SET display_name=$2 WHERE id=$1 RETURNING id,email,display_name,created_at",row["id"],display_name)
        telegram_challenges.pop(body.challenge_id,None)
        # Session persistence is intentionally handled in the next security phase.
        await client.disconnect()
        return {**issue_token(row["id"],s),"user":{"id":str(row["id"]),"display_name":row["display_name"]}}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(500,"Could not finish SKYGRID sign-in.")

@app.get("/auth/me")
async def me(user:User): return user

@app.post("/groups",status_code=201)
async def create_group(body:GroupCreate,user:User):
    async with database().acquire() as c:
        async with c.transaction():
            g=await c.fetchrow("INSERT INTO skygrid.groups(name,created_by) VALUES($1,$2) RETURNING id,name,created_by,created_at",body.name.strip(),user["id"])
            await c.execute("INSERT INTO skygrid.group_members(group_id,user_id,role) VALUES($1,$2,'owner')",g["id"],user["id"])
    return dict(g)
@app.get("/groups")
async def groups(user:User):
    async with database().acquire() as c:
        rows=await c.fetch("SELECT g.id,g.name,g.created_by,g.created_at,(SELECT count(*)::int FROM skygrid.group_members m2 WHERE m2.group_id=g.id) member_count FROM skygrid.groups g JOIN skygrid.group_members m ON m.group_id=g.id WHERE m.user_id=$1 ORDER BY g.created_at DESC",user["id"])
    return [dict(r) for r in rows]
@app.post("/groups/{group_id}/invite",status_code=201)
async def invite(group_id:UUID,user:User):
    code=secrets.token_urlsafe(32); digest=hashlib.sha256(code.encode()).hexdigest()
    async with database().acquire() as c:
        async with c.transaction():
            g=await c.fetchrow("SELECT id FROM skygrid.groups WHERE id=$1 AND created_by=$2",group_id,user["id"])
            if not g: raise HTTPException(404,"Group not found or you are not the owner")
            count=await c.fetchval("SELECT count(*) FROM skygrid.group_members WHERE group_id=$1",group_id)
            if count>=3: raise HTTPException(409,"Groups support up to 3 members")
            await c.execute("INSERT INTO skygrid.group_invites(group_id,token_hash,created_by,expires_at) VALUES($1,$2,$3,now()+interval '7 days')",group_id,digest,user["id"])
    return {"invite_code":code,"expires_in_seconds":604800,"note":"Single-use invite; share privately."}
@app.post("/groups/join",status_code=201)
async def join(body:JoinGroup,user:User):
    digest=hashlib.sha256(body.invite_code.encode()).hexdigest()
    async with database().acquire() as c:
        async with c.transaction():
            inv=await c.fetchrow("SELECT id,group_id FROM skygrid.group_invites WHERE token_hash=$1 AND expires_at>now() AND used_at IS NULL FOR UPDATE",digest)
            if not inv: raise HTTPException(400,"Invite invalid, expired, or already used")
            count=await c.fetchval("SELECT count(*) FROM skygrid.group_members WHERE group_id=$1",inv["group_id"])
            if count>=3: raise HTTPException(409,"Group already has 3 members")
            await c.execute("INSERT INTO skygrid.group_members(group_id,user_id,role) VALUES($1,$2,'member') ON CONFLICT DO NOTHING",inv["group_id"],user["id"])
            await c.execute("UPDATE skygrid.group_invites SET used_at=now(),used_by=$2 WHERE id=$1",inv["id"],user["id"])
            g=await c.fetchrow("SELECT id,name,created_by,created_at FROM skygrid.groups WHERE id=$1",inv["group_id"])
    return dict(g)
@app.get("/groups/{group_id}/members")
async def members(group_id:UUID,user:User):
    async with database().acquire() as c:
        ok=await c.fetchval("SELECT 1 FROM skygrid.group_members WHERE group_id=$1 AND user_id=$2",group_id,user["id"])
        if not ok: raise HTTPException(404,"Group not found")
        rows=await c.fetch("SELECT u.id,u.email,u.display_name,m.role,m.joined_at FROM skygrid.group_members m JOIN skygrid.users u ON u.id=m.user_id WHERE m.group_id=$1 ORDER BY m.joined_at",group_id)
    return [dict(r) for r in rows]
@app.get("/files")
async def list_files(user:User,group_id:UUID|None=None):
    async with database().acquire() as c:
        if group_id:
            ok=await c.fetchval("SELECT 1 FROM skygrid.group_members WHERE group_id=$1 AND user_id=$2",group_id,user["id"])
            if not ok: raise HTTPException(404,"Group not found")
            rows=await c.fetch("SELECT f.id,f.owner_id,f.group_id,f.original_name,f.mime_type,f.size_bytes,f.storage_provider,f.storage_key,f.created_at,u.display_name uploaded_by FROM skygrid.files f JOIN skygrid.users u ON u.id=f.owner_id WHERE f.group_id=$1 ORDER BY f.created_at DESC",group_id)
        else:
            rows=await c.fetch("SELECT id,owner_id,group_id,original_name,mime_type,size_bytes,storage_provider,storage_key,created_at FROM skygrid.files WHERE owner_id=$1 AND group_id IS NULL ORDER BY created_at DESC",user["id"])
    return [dict(r) for r in rows]
@app.post("/files",status_code=201)
async def register_file(body:FileMeta,user:User):
    if body.group_id:
        async with database().acquire() as c:
            ok=await c.fetchval("SELECT 1 FROM skygrid.group_members WHERE group_id=$1 AND user_id=$2",body.group_id,user["id"])
        if not ok: raise HTTPException(404,"Group not found")
    async with database().acquire() as c:
        r=await c.fetchrow("INSERT INTO skygrid.files(owner_id,group_id,original_name,mime_type,size_bytes) VALUES($1,$2,$3,$4,$5) RETURNING id,owner_id,group_id,original_name,mime_type,size_bytes,storage_provider,storage_key,created_at",user["id"],body.group_id,body.original_name,body.mime_type,body.size_bytes)
    return dict(r)
