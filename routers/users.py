import datetime

from fastapi import APIRouter, Depends, HTTPException

import additional_funcs.users
import config
from fastapi.requests import Request
from middlewares import auth as auth_middlewares
from additional_funcs import users as users_additional_funcs
from models import users as users_modules


router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}}
)


@router.post("/signup")
async def signup(request: Request, user: users_modules.ItemUserSignUp,
                 authorize: auth_middlewares.AuthJWT = Depends()):
    if not await users_additional_funcs.check_if_data_is_free_for_registration(user.email, user.phone):
        raise HTTPException(status_code=400, detail='Email or phone are already registered')
    info_dict = user.dict()
    info_dict["password"] = auth_middlewares.get_password_hash(user.password)
    info_dict["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    config.db.users.insert_one(info_dict)
    info_dict = await users_additional_funcs.delete_object_ids_from_dict(info_dict)
    session_id = await users_additional_funcs.update_last_login(info_dict['_id'], request.headers.get("user-agent"))
    await auth_middlewares.create_tokens_on_login_or_signup(authorize, info_dict['_id'], session_id,
                                                            request.headers.get("user-agent"))
    del info_dict['password']
    return info_dict


@router.post("/login")
async def login_for_access_token(request: Request, user: users_modules.ItemUserLoginIn,
                                 authorize: auth_middlewares.AuthJWT = Depends()):
    user = await auth_middlewares.authenticate_user(user.email_or_phone, user.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    session_id = await users_additional_funcs.update_last_login(user.id, request.headers.get("user-agent"))
    await auth_middlewares.create_tokens_on_login_or_signup(authorize, user.id, session_id,
                                                            request.headers.get("user-agent"))
    return user


@router.post('/refresh-jwt')
async def refresh(authorize: auth_middlewares.AuthJWT = Depends()):
    # checking if refresh token is available for refresh
    authorize.jwt_refresh_token_required()
    await auth_middlewares.revoke_token(authorize.get_raw_jwt()['jti'], authorize.get_raw_jwt()['exp'])
    current_user = authorize.get_jwt_subject()
    # refresh refresh token
    new_refresh_token = authorize.create_refresh_token(subject=current_user)
    authorize.set_refresh_cookies(new_refresh_token)
    jti = authorize.get_jti(new_refresh_token)
    await additional_funcs.users.insert_jti_in_session_id(user_id=current_user[:24],
                                                          session_id=current_user[24:],
                                                          jti_refresh=jti)
    # refresh access token
    new_access_token = authorize.create_access_token(subject=current_user)
    authorize.set_access_cookies(new_access_token)
    jti = authorize.get_jti(new_access_token)
    await additional_funcs.users.insert_jti_in_session_id(user_id=current_user[:24],
                                                          session_id=current_user[24:],
                                                          jti_access=jti)
    # checking if access token is available for refresh to revoke it
    try:
        authorize.jwt_required()
        await auth_middlewares.revoke_token(authorize.get_raw_jwt()['jti'], authorize.get_raw_jwt()['exp'])
    except Exception as e:
        print(e)
    return dict(msg="The token has been refreshed")


@router.post('/fresh-jwt')
async def create_fresh_jwt(authorize: auth_middlewares.AuthJWT = Depends()):
    # checking if access token is available for refresh
    authorize.jwt_required()
    await auth_middlewares.revoke_token(authorize.get_raw_jwt()['jti'], authorize.get_raw_jwt()['exp'])
    current_user = authorize.get_jwt_subject()
    new_fresh_token = authorize.create_access_token(subject=current_user, fresh=True, expires_time=5)
    authorize.set_access_cookies(new_fresh_token)
    return dict(msg="Fresh token has been set")


@router.delete('/access-revoke')
async def access_revoke(authorize: auth_middlewares.AuthJWT = Depends()):
    # checking if access token is available for refresh
    authorize.jwt_required()
    authorize.unset_access_cookies()
    await auth_middlewares.revoke_token(authorize.get_raw_jwt()['jti'], authorize.get_raw_jwt()['exp'])
    return dict(msg="Access token has been revoke")


@router.delete('/refresh-revoke')
async def refresh_revoke(authorize: auth_middlewares.AuthJWT = Depends()):
    # checking if refresh token is available for refresh
    authorize.jwt_refresh_token_required()
    authorize.unset_refresh_cookies()
    await auth_middlewares.revoke_token(authorize.get_raw_jwt()['jti'], authorize.get_raw_jwt()['exp'])
    return dict(msg="Refresh token has been revoke")


@router.delete("/logout")
async def logout_and_delete_access_token(authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    sub = authorize.get_jwt_subject()
    await additional_funcs.users.unset_active_session_in_db(user_id=sub[:24], session_id=sub[24:])
    await auth_middlewares.revoke_token(authorize.get_raw_jwt()['jti'], authorize.get_raw_jwt()['exp'])
    authorize.jwt_refresh_token_required()
    await auth_middlewares.revoke_token(authorize.get_raw_jwt()['jti'], authorize.get_raw_jwt()['exp'])
    authorize.unset_jwt_cookies()
    return dict(msg="logout success")


@router.get("/check-jwt")
async def get_user_object(authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    return current_user
