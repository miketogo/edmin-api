from pymongo import MongoClient
import os
from dotenv import load_dotenv
import redis
from pydantic import BaseModel

redis_connection = redis.StrictRedis(host='localhost', port=6379, db=0)

load_dotenv()


client = MongoClient(port=27017)
db = client.edmin

AUTHJWT_SECRET_KEY = os.getenv('SECRET_KEY')


class Settings(BaseModel):
    authjwt_secret_key: str = AUTHJWT_SECRET_KEY
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
