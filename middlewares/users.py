from datetime import datetime, timedelta
from typing import Optional, Dict

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from fastapi.security.utils import get_authorization_scheme_param
from fastapi.requests import Request
from bson import ObjectId
import config

SECRET_KEY = config.SECRET_KEY
ALGORITHM = config.ALGORITHM
ACCESS_TOKEN_EXPIRE_SECONDS = config.ACCESS_TOKEN_EXPIRE_SECONDS


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    id: Optional[str] = None


class User(BaseModel):
    id: str
    email: str
    phone: str
    name: str
    surname: str
    fullname: str
    patronymic: Optional[str] = None
    division: Optional[str] = None
    role: Optional[str] = None
    company_id: Optional[str] = None


class UserInDB(User):
    password: str


class OAuth2PasswordBearer(OAuth2):
    def __init__(
        self,
        token_url: str,
        scheme_name: Optional[str] = None,
        scopes: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
        auto_error: bool = True,
    ):
        if not scopes:
            scopes = {}
        flows = OAuthFlowsModel(password={"tokenUrl": token_url, "scopes": scopes})
        super().__init__(
            flows=flows,
            scheme_name=scheme_name,
            description=description,
            auto_error=auto_error,
        )

    async def __call__(self, request: Request) -> Optional[str]:
        cookie_authorization: str = request.cookies.get("Authorization")

        cookie_scheme, cookie_param = get_authorization_scheme_param(
            cookie_authorization
        )
        scheme, param = None, None

        if cookie_scheme.lower() == "bearer":
            authorization = True
            scheme = cookie_scheme
            param = cookie_param

        else:
            authorization = False

        if not authorization or scheme.lower() != "bearer":
            if self.auto_error:
                raise HTTPException(
                    status_code=401, detail="Not authenticated"
                )
            else:
                return None
        return param


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(token_url="/users/login")

app = FastAPI()


async def refresh_token(response, current_user):
    access_token_expires = timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS)
    access_token = await create_access_token(
        data={"sub": current_user.id}, expires_delta=access_token_expires
    )
    response.set_cookie(key="Authorization", value='Bearer ' + access_token,
                        max_age=ACCESS_TOKEN_EXPIRE_SECONDS, expires=ACCESS_TOKEN_EXPIRE_SECONDS)
    return response


async def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


async def get_user(email_or_phone_or_id: str, _id_check: Optional[bool] = False):
    user = await check_user_email_password_in_db(email_or_phone_or_id, _id_check)
    if user is not None:
        user["id"] = str(user["_id"])
        del user["_id"]
        return UserInDB(**user)


async def authenticate_user(email_or_phone: str, password: str):
    user = await get_user(email_or_phone)
    if not user:
        return False
    if not await verify_password(password, user.password):
        return False
    return user


async def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        _id: str = payload.get("sub")
        if _id is None:
            raise credentials_exception
        token_data = TokenData(id=_id)
    except JWTError:
        raise credentials_exception
    user = await get_user(token_data.id, _id_check=True)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    return current_user


async def check_if_data_is_free_for_registration(email: str, phone: str):
    user_email_check = config.db.users.find_one({"email": email})
    user_phone_check = config.db.users.find_one({"phone": phone})
    if user_email_check is not None or user_phone_check is not None:
        return False
    return True


async def check_user_email_password_in_db(email_or_phone_or_id: str, _id_check: Optional[bool] = False):
    user_email_check = config.db.users.find_one({"email": email_or_phone_or_id})
    user_phone_check = config.db.users.find_one({"phone": email_or_phone_or_id})

    if user_email_check is not None:
        return user_email_check
    elif user_phone_check is not None:
        return user_phone_check
    elif _id_check:
        user__id_check = config.db.users.find_one({"_id": ObjectId(email_or_phone_or_id)})
        print(user__id_check)
        if user__id_check is not None:
            return user__id_check
    return None
