import datetime

from fastapi import APIRouter, Depends, HTTPException

import config
from fastapi.responses import Response
from fastapi.requests import Request
from fastapi.security import OAuth2PasswordRequestForm
from middlewares import users as users_middlewares
from modules import users as users_modules


router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}}
)


@router.post("/signup")
async def signup(response: Response, request: Request, user: users_modules.ItemUserSignUp):
    if not await users_middlewares.check_if_data_is_free_for_registration(user.email, user.phone):
        raise HTTPException(status_code=400, detail='Email or phone are already registered')
    info_dict = user.dict()
    info_dict["password"] = users_middlewares.get_password_hash(user.password)
    info_dict["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    info_dict["fullname"] = info_dict["surname"].title() + ' ' + info_dict["name"].title()
    info_dict["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    if info_dict["patronymic"] is not None:
        info_dict["fullname"] += ' ' + info_dict["patronymic"].title()
    config.db.users.insert_one(info_dict)
    info_dict = await users_middlewares.delete_object_ids_from_dict(info_dict)
    await users_middlewares.update_last_login(info_dict['_id'], request.headers.get("user-agent"))
    await users_middlewares.refresh_token(response, info_dict['_id'])
    del info_dict['password']
    return info_dict


@router.post("/login")
async def login_for_access_token(response: Response, request: Request,
                                 form_data: OAuth2PasswordRequestForm = Depends()):
    user = await users_middlewares.authenticate_user(form_data.username, form_data.password)
    if not user:
        response.delete_cookie(key="Authorization")
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    await users_middlewares.refresh_token(response, user.id)
    await users_middlewares.update_last_login(user.id, request.headers.get("user-agent"))
    return user


@router.post("/logout")
async def logout_and_delete_access_token(response: Response,
                                         current_user: users_modules.User
                                         = Depends(users_middlewares.get_current_active_user)):
    response.delete_cookie(key="Authorization")
    return dict(logout="success")


@router.post("/cheek-jwt")
async def logout_and_delete_access_token(response: Response,
                                         current_user: users_modules.User
                                         = Depends(users_middlewares.get_current_active_user)):
    await users_middlewares.refresh_token(response, current_user.id)
    return current_user
