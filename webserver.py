from contextlib import asynccontextmanager
import datetime
import random
import string
from typing import List, Optional, Union

import aiohttp
import dateparser
from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordBearer
import sentry_sdk
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from tortoise import Tortoise

from cogs.models import Votes, WebhookAuthorization


#from cogs.models import 


SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 30


def get_random_state(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


HEADER = """<!DOCTYPE html><head>
<title>my website ig</title>
<link rel='icon' href='https://i.ibb.co/QrwTwB9/amogus-impostor.jpg'></head>"""


sentry_sdk.init(
    dsn="https://382db3ce869924bbfb49840c10e8e646@o4507268563337216.ingest.us.sentry.io/4507303480000512",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    traces_sample_rate=1.0,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    # We recommend adjusting this value in production.
    profiles_sample_rate=1.0,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model
    await Tortoise.init(
        config_file='db.yml'
    )
    await Tortoise.generate_schemas()
    yield

print('ran main')

app = FastAPI(title="my goofy api", version=".007",lifespan=lifespan)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ips = []
admins = []

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

MAX_SESSIONS = 2

_sessions: List[aiohttp.ClientSession] = []

# with open('client.yml','r') as f:
#     config = dict(yaml.safe_load(f))

async def get_session(session_num: int=0, session_name: Optional[Union[str, int]]=None, **kwargs) -> aiohttp.ClientSession:
    """Get's a session from the current pool of sessions. Will give the first session by default.
    Max amount of sessions can be changed by changing the MAX_SESSIONS variable.
    You can optionally provide a session_name to get a specific session. Depricated dont use this
    Kwargs will be passed into ClientSession constructor."""
    if len(_sessions) < MAX_SESSIONS: _sessions.append(aiohttp.ClientSession(**kwargs))
    return _sessions[session_num]

async def close_session(session: Optional[aiohttp.ClientSession]=None, session_num: int=0) -> None:
    """Closes the specified connection and removes from the connectionn pool."""
    if session is None:
        session = _sessions.pop(session_num)
    elif session in _sessions:
        _sessions.remove(session)
    await session.close()
    return

async def close_sessions(sessions: List[aiohttp.ClientSession]=[], session_nums: List[int]=[], close_all: bool=False) -> None:
    """Closes the specified connections and removes from the connection pool."""
    if close_all:
        sessions = _sessions
    for session in sessions:
        await close_session(session)
    for session_num in session_nums:
        await close_session(session_num=session_num)
    return

@app.middleware("http")
async def middleware(request: Request, call_next):
    if not await WebhookAuthorization.filter(authorization=request.headers.get('Authorization')).exists():
        return Response(status_code=401)
    return await call_next(request)

async def save_vote(request: Request, site: str, data: dict):
    addl_data = data
    del addl_data['user_id']
    del addl_data['user']
    del addl_data['username']
    del addl_data['timestamp']
    del addl_data['avatar']
    del addl_data['is_weekend']

    await Votes.create(
        user_id=data.get('user',None) or data.get('user_id',None),
        username=data.get('username',None),

        avatar=data.get('avatar',None),

        site=site,
        timestamp=dateparser.parse(data['timestamp']),
        loggedby='webhook',
        addl_data=addl_data,
        _raw=data
    )
    return Response(status_code=200)

@app.post("/webhooks/topgg")
@limiter.limit("60/minute",error_message="bro you need to stop spamming my website")
async def vote_topgg(request: Request, data: dict):
    #print(data)
   #{'user': '458657458995462154', 'type': 'test', 'query': '', 'bot': '1082452014157545502'}
    #{'user': '458657458995462154', 'type': 'upvote', 'query': '', 'isWeekend': False, 'bot': '1082452014157545502'}   
    new_dict = {
        'user_id': data['user'],
        'username': data.get('username',None),
        'timestamp': datetime.datetime.now(),
        'avatar': data.get('avatar',None),
        'is_weekend': data.get('isWeekend',False),
        # 'type': data['type'],
        # 'bot': data['bot'],
        # 'type': data['type'],
        # 'query': data['query']
    }

    for k, v in data.items():
        if k not in new_dict.keys():
            new_dict[k] = v
    return await save_vote(request, 'topgg', new_dict)

@app.post("/webhooks/dcbotlist")
@limiter.limit("60/minute",error_message="bro you need to stop spamming my website")
async def vote_dcbotlist(request: Request, data: dict):
    #print(data)
    #{'id': '458657458995462154', 'username': 'aidenpearce3066', 'avatar': '3acfe15b991e017b80f0430797927156'}
    new_dict = {
        'user_id': data['id'],
        'username': data.get('username',None),
        'timestamp': datetime.datetime.now(),
        'avatar': data.get('avatar',None),
        'is_weekend': data.get('isWeekend',False),
        # 'type': data['type'],
        # 'bot': data['bot'],
        # 'type': data['type'],
        # 'query': data['query']
    }
    return await save_vote(request, 'dcbotlist', new_dict)

@app.get("/sentry-debug")
async def trigger_error():
    raise RuntimeError("Test exception")
# @app.post("/webhooks/dclistgg")
# @limiter.limit("60/minute",error_message="bro you need to stop spamming my website")
# async def vote_dclistgg(request: Request, data: dict):
#     print(data)
#     return await save_vote(request, 'dclistgg', data)
