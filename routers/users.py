import datetime

from fastapi import APIRouter, Depends, HTTPException

import config
from fastapi.requests import Request
from middlewares import auth as auth_middlewares
from additional_funcs import users as users_additional_funcs
from modules import users as users_modules


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
    info_dict["fullname"] = info_dict["surname"].title() + ' ' + info_dict["name"].title()
    info_dict["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    if info_dict["patronymic"] is not None:
        info_dict["fullname"] += ' ' + info_dict["patronymic"].title()
    config.db.users.insert_one(info_dict)
    info_dict = await users_additional_funcs.delete_object_ids_from_dict(info_dict)
    await users_additional_funcs.update_last_login(info_dict['_id'], request.headers.get("user-agent"))
    await auth_middlewares.refresh_token(authorize, info_dict['_id'])
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
    await auth_middlewares.refresh_token(authorize, user.id)
    await users_additional_funcs.update_last_login(user.id, request.headers.get("user-agent"))
    return user


@router.post('/refresh-jwt')
def refresh(authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_refresh_token_required()

    current_user = authorize.get_jwt_subject()
    new_access_token = authorize.create_access_token(subject=current_user)
    # Set the JWT and CSRF double submit cookies in the response
    authorize.set_access_cookies(new_access_token)
    return dict(msg="The token has been refreshed")


@router.delete('/access-revoke')
def access_revoke(authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()

    jti = authorize.get_raw_jwt()['jti']
    auth_middlewares.denylist.add(jti)
    return dict(msg="Access token has been revoke")


@router.delete('/refresh-revoke')
def refresh_revoke(authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_refresh_token_required()

    jti = authorize.get_raw_jwt()['jti']
    auth_middlewares.denylist.add(jti)
    return dict(msg="Refresh token has been revoke")


@router.delete("/logout")
async def logout_and_delete_access_token(authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    authorize.unset_jwt_cookies()
    return dict(msg="logout success")


@router.get("/check-jwt")
async def get_user_object(authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user: users_modules.User = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)

    if current_user is None:
        raise HTTPException(status_code=404, detail='Could not find the current_user')

    return current_user
