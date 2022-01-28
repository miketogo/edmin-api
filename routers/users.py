import datetime

from fastapi import APIRouter, Depends, HTTPException

import config
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm
from middlewares import users as users_middlewares
from modules import users as users_modules


router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}}
)


@router.post("/signup")
async def signup(response: Response, user: users_modules.ItemUserSignUp):
    if not await users_middlewares.check_if_data_is_free_for_registration(user.email, user.phone):
        raise HTTPException(status_code=400, detail='Email or phone are already registered')
    info_dict = user.dict()
    info_dict["password"] = users_middlewares.get_password_hash(user.password)
    info_dict["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    info_dict["fullname"] = info_dict["surname"].title() + ' ' + info_dict["name"].title()
    if info_dict["patronymic"] is not None:
        info_dict["fullname"] += ' ' + info_dict["patronymic"].title()
    config.db.users.insert_one(info_dict)
    info_dict['_id'] = str(info_dict['_id'])

    access_token_expires = datetime.timedelta(seconds=config.ACCESS_TOKEN_EXPIRE_SECONDS)
    access_token = await users_middlewares.create_access_token(
        data={"sub": info_dict['_id']}, expires_delta=access_token_expires
    )
    response.set_cookie(key="Authorization", value='Bearer ' + access_token,
                        max_age=config.ACCESS_TOKEN_EXPIRE_SECONDS, expires=config.ACCESS_TOKEN_EXPIRE_SECONDS)

    return info_dict


@router.post("/login")
async def login_for_access_token(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    user = await users_middlewares.authenticate_user(form_data.username, form_data.password)
    if not user:
        response.delete_cookie(key="Authorization")
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = datetime.timedelta(seconds=config.ACCESS_TOKEN_EXPIRE_SECONDS)
    access_token = await users_middlewares.create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )
    response.set_cookie(key="Authorization", value='Bearer ' + access_token,
                        max_age=config.ACCESS_TOKEN_EXPIRE_SECONDS, expires=config.ACCESS_TOKEN_EXPIRE_SECONDS)
    return dict(login="success")
