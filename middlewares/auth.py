from typing import Optional

from fastapi import FastAPI
from passlib.context import CryptContext

import additional_funcs.users
from modules import users as users_modules
from additional_funcs import users as users_additional_funcs
from fastapi_jwt_auth import AuthJWT
from datetime import datetime, timedelta
import config


@AuthJWT.load_config
def get_config():
    return config.Settings()


@AuthJWT.token_in_denylist_loader
def check_if_token_in_denylist(decrypted_token):
    jti = decrypted_token['jti']
    entry = config.redis_deny_list.get(jti)
    return entry and entry == 'true'


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()


async def create_tokens_on_login_or_signup(authorize: AuthJWT, user_id: str, session_id: str, user_agent_header: str):
    # Create the tokens and passing to set_access_cookies or set_refresh_cookies
    access_token = authorize.create_access_token(subject=user_id + session_id)
    refresh_token_ = authorize.create_refresh_token(subject=user_id + session_id)
    """
    print(authorize.get_jti(refresh_token_), authorize.get_jti(access_token))
    config.redis_refresh_tokens.setex(authorize.get_jti(refresh_token_),
                                      timedelta(days=config.AUTHJWT_REFRESH_TOKEN_EXPIRES), user_agent_header)
    """
    await additional_funcs.users.insert_jti_in_session_id(jti_refresh=authorize.get_jti(refresh_token_),
                                                          jti_access=authorize.get_jti(access_token),
                                                          user_id=user_id, session_id=session_id)
    # Set the JWT and CSRF double submit cookies in the response
    authorize.set_access_cookies(access_token)
    authorize.set_refresh_cookies(refresh_token_)
    return authorize


async def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


async def get_user(email_or_phone_or_id: str, _id_check: Optional[bool] = False, with_password: Optional[bool] = False):
    user_from_session = True
    if _id_check:
        session_id = email_or_phone_or_id[24:]
        email_or_phone_or_id = email_or_phone_or_id[:24]
        user_from_session = await additional_funcs.users.check_user_session_in_db(session_id)
    user = await users_additional_funcs.check_user_email_password_in_db(email_or_phone_or_id, _id_check)
    if (user_from_session is True or user_from_session == user) and user is not None:
        if user["_id"] is not None:
            user["id"] = str(user["_id"])
        if user["company_id"] is not None:
            user["company_id"] = str(user["company_id"])
        del user["_id"]
        if with_password:
            return users_modules.UserInDB(**user)
        return users_modules.User(**user)


async def authenticate_user(email_or_phone: str, password: str):
    user = await get_user(email_or_phone, with_password=True)
    if not user:
        return False
    if not await verify_password(password, user.password):
        return False
    del user.password
    return user


async def revoke_token(jti: str, exp: int):
    seconds = exp - int(str(datetime.timestamp(datetime.now())).split('.')[0])
    config.redis_deny_list.setex(jti, seconds, 'true')
    return True
