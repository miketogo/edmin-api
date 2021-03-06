from typing import Optional

from fastapi import FastAPI, HTTPException
from passlib.context import CryptContext

import additional_funcs.users
from models import users as users_modules
from additional_funcs import users as users_additional_funcs
from fastapi_jwt_auth import AuthJWT
from datetime import datetime, timedelta
from bson import ObjectId
import config


@AuthJWT.load_config
def get_config():
    return config.Settings()


@AuthJWT.token_in_denylist_loader
def check_if_token_in_denylist(decrypted_token):
    jti = decrypted_token['jti']
    entry = config.redis_deny_list.get(jti)
    return entry and entry == b'true'


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
        user = await users_additional_funcs.delete_object_ids_from_dict(user)
        user['permissions'] = None
        user['is_division_admin'] = False
        user['is_role_admin'] = False
        user['id'] = user['_id']
        if user["role_id"] is not None:
            user["role_id"] = str(user["role_id"])
            obj = list(config.db.companies.aggregate(
                [{"$unwind": "$divisions"},
                 {"$unwind": "$divisions.available_roles"},
                 {"$match": {"divisions.available_roles.role_id": ObjectId(user['role_id'])}}]))
            if len(obj) == 1:
                user['permissions'] = obj[0]['divisions']['available_roles']['permissions']
                if obj[0]['divisions']['name'] == 'admin':
                    user['is_division_admin'] = True
                if obj[0]['divisions']['available_roles']['name'] == 'admin':
                    user['is_role_admin'] = True
        elif user['division_id'] is not None:
            user['permissions'] = dict(can_upload_files=False,
                                       can_download_files=True,
                                       can_add_filters=False,
                                       can_change_company_data=False,
                                       can_manage_employers=False,)

        del user["_id"]
        if with_password:
            return users_modules.UserInDB(**user)
        return users_modules.User(**user)
    raise HTTPException(status_code=404, detail='Could not find the current_user')


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
