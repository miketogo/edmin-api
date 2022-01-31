from typing import Optional
from pydantic import BaseModel, validator
from validate_email import validate_email
from bson import ObjectId
import config


class ItemUserSignUp(BaseModel):
    email: str
    password: str
    phone: str
    name: str
    surname: str
    patronymic: Optional[str] = None
    division_id: Optional[str] = None
    company_id: Optional[str] = None
    role_id: Optional[str] = None

    @validator('email', allow_reuse=True)
    def check_email_omitted(cls, value):
        if not validate_email(value):
            raise ValueError('email validation failed')
        return value

    @validator('company_id', allow_reuse=True)
    def check_company_id_omitted(cls, value):
        if len(value) != 24 or config.db.companies.find_one({"_id": ObjectId(value)}) is None:
            raise ValueError('company_id validation failed')
        return value

    @validator('division_id', allow_reuse=True)
    def check_division_omitted(cls, value):
        if len(value) != 24 or config.db.users.find_one({"division_id": ObjectId(value)}) is None:
            raise ValueError('division_id validation failed')
        return value

    @validator('role_id', allow_reuse=True)
    def check_role_id_omitted(cls, value):
        if len(value) != 24 or config.db.users.find_one({"role_id": ObjectId(value)}) is None:
            raise ValueError('role_id validation failed')
        return value


class ItemUserLoginIn(BaseModel):
    email_or_phone: str
    password: str


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
