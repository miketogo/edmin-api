from datetime import timedelta
from typing import Optional

from fastapi import FastAPI
from passlib.context import CryptContext
from modules import users as users_modules
from additional_funcs import users as users_additional_funcs
from fastapi_jwt_auth import AuthJWT
from pydantic import BaseModel
import json
import config

SECRET_KEY = config.SECRET_KEY
ALGORITHM = config.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = config.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = config.REFRESH_TOKEN_EXPIRE_DAYS


class Settings(BaseModel):
    authjwt_secret_key: str = SECRET_KEY
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
    access_expires: int = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_expires: int = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)


@AuthJWT.load_config
def get_config():
    return Settings()


@AuthJWT.token_in_denylist_loader
def check_if_token_in_denylist(decrypted_token):
    jti = decrypted_token['jti']
    entry = config.redis_connection.get(jti)
    return entry and entry == 'true'


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()


async def refresh_token(authorize, current_user_id):
    # Create the tokens and passing to set_access_cookies or set_refresh_cookies
    access_token = authorize.create_access_token(subject=current_user_id)
    refresh_token_ = authorize.create_refresh_token(subject=current_user_id)
    # Set the JWT and CSRF double submit cookies in the response
    authorize.set_access_cookies(access_token)
    authorize.set_refresh_cookies(refresh_token_)
    return authorize


async def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


async def get_user(email_or_phone_or_id: str, _id_check: Optional[bool] = False):
    user = await users_additional_funcs.check_user_email_password_in_db(email_or_phone_or_id, _id_check)
    if user is not None:
        if user["_id"] is not None:
            user["id"] = str(user["_id"])
        if user["company_id"] is not None:
            user["company_id"] = str(user["company_id"])
        del user["_id"]
        return users_modules.UserInDB(**user)


async def authenticate_user(email_or_phone: str, password: str):
    user = await get_user(email_or_phone)
    if not user:
        return False
    if not await verify_password(password, user.password):
        return False
    del user.password
    return user
