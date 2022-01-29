from typing import Optional, List
from pydantic import BaseModel, validator
from bson import ObjectId
import datetime
import config


class Permissions(BaseModel):
    fly: Optional[bool] = False
    walk: Optional[bool] = False


class Divisions(BaseModel):
    id: Optional[str]
    name: str
    permissions: Optional[Permissions] = Permissions()

    @validator('id', allow_reuse=True)
    def check_divisions_id_omitted(cls, value):
        if len(value) != 24 or config.db.companies.find_one({"divisions._id": ObjectId(value)}) is None:
            raise ValueError('available_signers._id validation failed')
        return value


class AvailableRoles(BaseModel):
    id: Optional[str]
    name: str
    permissions: Optional[Permissions] = Permissions()

    @validator('id', allow_reuse=True)
    def check_available_roles_id_omitted(cls, value):
        if len(value) != 24 or config.db.companies.find_one({"available_roles._id": ObjectId(value)}) is None:
            raise ValueError('available_signers._id validation failed')
        return value


class ThirdParties(BaseModel):
    id: Optional[str]
    name: str

    @validator('id', allow_reuse=True)
    def check_third_parties_id_omitted(cls, value):
        if len(value) != 24 or config.db.companies.find_one({"third_parties._id": ObjectId(value)}) is None:
            raise ValueError('available_signers._id validation failed')
        return value


class AvailableSigners(BaseModel):
    id: Optional[str]
    name: str
    surname: str
    patronymic: Optional[str] = None

    @validator('id', allow_reuse=True)
    def check_available_signers_id_omitted(cls, value):
        if len(value) != 24 or config.db.companies.find_one({"available_signers._id": ObjectId(value)}) is None:
            raise ValueError('available_signers._id validation failed')
        return value


class Subscription(BaseModel):
    name: Optional[str] = None
    price: Optional[str] = None
    price_value: Optional[int] = None
    start_date: Optional[str] = None
    expiration_date: Optional[str] = None

    @validator('start_date', allow_reuse=True)
    def check_start_date_omitted(cls, value):
        if value is not None:
            try:
                datetime.datetime.strptime(value, "%d.%m.%Y")
            except ValueError as e:
                print(e)
                raise ValueError('subscription.start_date validation failed')
        return value

    @validator('expiration_date', allow_reuse=True)
    def check_expiration_date_omitted(cls, value):
        if value is not None:
            try:
                datetime.datetime.strptime(value, "%d.%m.%Y")
            except ValueError as e:
                print(e)
                raise ValueError('subscription.expiration_date validation failed')
        return value


class ItemCompanyCreate(BaseModel):
    name: str
    address: str
    available_roles: Optional[List[AvailableRoles]] = list()
    divisions: Optional[List[Divisions]] = list()
    third_parties: Optional[List[ThirdParties]] = list()
    available_signers: Optional[List[AvailableSigners]] = list()
    subscription: Optional[Subscription] = Subscription()
