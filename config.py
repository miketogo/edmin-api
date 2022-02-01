from pymongo import MongoClient
import os
from dotenv import load_dotenv
import redis
from pydantic import BaseModel
from datetime import timedelta

server_host = 'localhost'
port = 3000

load_dotenv(dotenv_path='venv/.env')


redis_deny_list = redis.StrictRedis(host='localhost', port=6379, db=0)
redis_refresh_tokens = redis.StrictRedis(host='localhost', port=6379, db=1)

client = MongoClient(port=27017)
db = client.edmin

AUTHJWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
AUTHJWT_REFRESH_TOKEN_EXPIRES = timedelta(days=60)

AUTHJWT_PRIVATE_KEY_PATH = os.getenv('AUTHJWT_PRIVATE_KEY_PATH')
AUTHJWT_PUBLIC_KEY_PATH = os.getenv('AUTHJWT_PUBLIC_KEY_PATH')
AUTHJWT_ALGORITHM = os.getenv('ALGORITHM')


try:
    with open(AUTHJWT_PRIVATE_KEY_PATH, 'r') as file:
        private_key = file.read()
except FileNotFoundError:
    raise FileNotFoundError('Could not found private key in venv, check .env')
try:
    with open(AUTHJWT_PUBLIC_KEY_PATH, 'r') as file:
        public_key = file.read()
except FileNotFoundError:
    raise FileNotFoundError('Could not found public key in venv, check .env')


class Settings(BaseModel):
    authjwt_algorithm: str = AUTHJWT_ALGORITHM
    authjwt_public_key: str = public_key
    authjwt_private_key: str = private_key
    # Configure application to store and get JWT from cookies
    authjwt_token_location: set = {"cookies"}
    # Only allow JWT cookies to be sent over https
    authjwt_cookie_secure: bool = True
    # Enable csrf double submit protection. default is True
    authjwt_cookie_csrf_protect: bool = True
    # Change to 'lax' in production to make your website more secure from CSRF Attacks, default is None
    authjwt_cookie_samesite: str = 'lax'
    # The request methods that will use CSRF protection.
    authjwt_csrf_methods: set = {"PUT"}
    # denylist conf
    authjwt_denylist_enabled: bool = True
    authjwt_denylist_token_checks: set = {"access", "refresh"}
    authjwt_access_token_expires: int = AUTHJWT_ACCESS_TOKEN_EXPIRES
    authjwt_refresh_token_expires: int = AUTHJWT_REFRESH_TOKEN_EXPIRES
