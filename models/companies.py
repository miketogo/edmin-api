from typing import Optional, List
from pydantic import BaseModel, validator
from bson import ObjectId
import datetime
import config


class Permissions(BaseModel):
    can_upload_files: Optional[bool] = False
    can_download_files: Optional[bool] = False
    can_add_filters: Optional[bool] = False
    can_change_company_data: Optional[bool] = False
    can_manage_employers: Optional[bool] = False


class AvailableRoles(BaseModel):
    role_id: Optional[str]
    name: str
    permissions: Optional[Permissions] = Permissions()

    @validator('role_id', allow_reuse=True)
    def check_available_roles_id_omitted(cls, value):
        if len(value) != 24 or config.db.companies.find_one({"available_roles._id": ObjectId(value)}) is None:
            raise ValueError('available_signers._id validation failed')
        return value


class Division(BaseModel):
    division_id: Optional[str]
    name: str
    available_roles: Optional[List[AvailableRoles]] = [AvailableRoles(
        name="admin",
        permissions={"can_upload_files": True,
                     "can_download_files": True,
                     "can_add_filters": True,
                     "can_change_company_data": True,
                     "can_manage_employers": True})]

    @validator('division_id', allow_reuse=True)
    def check_divisions_id_omitted(cls, value):
        if len(value) != 24 or config.db.companies.find_one({"divisions._id": ObjectId(value)}) is None:
            raise ValueError('division._id validation failed')
        return value


class ThirdParties(BaseModel):
    third_party_id: Optional[str]
    name: str

    @validator('third_party_id', allow_reuse=True)
    def check_third_parties_id_omitted(cls, value):
        if len(value) != 24 or config.db.companies.find_one({"third_parties._id": ObjectId(value)}) is None:
            raise ValueError('third_parties._id validation failed')
        return value


class AvailableSigners(BaseModel):
    available_singer_id: Optional[str]
    name: str
    surname: str
    patronymic: Optional[str] = None

    @validator('available_singer_id', allow_reuse=True)
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
    third_parties: Optional[List[ThirdParties]] = list()
    available_signers: Optional[List[AvailableSigners]] = list()
    subscription: Optional[Subscription] = Subscription()
