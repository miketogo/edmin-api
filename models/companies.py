from typing import Optional, List
from pydantic import BaseModel, validator, root_validator
from fastapi import Form
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
    role_id: Optional[str] = Form(None, min_length=24, max_length=24)
    name: str
    permissions: Optional[Permissions] = Permissions()

    @validator('role_id', allow_reuse=True)
    def check_available_roles_id_omitted(cls, value):
        if len(list(config.db.companies.aggregate(
                [{"$unwind": "$divisions"},
                 {"$unwind": "$divisions.available_roles"},
                 {"$match": {"divisions.available_roles.role_id": ObjectId(value)}}]))) == 1:
            raise ValueError('divisions.available_signers.role_id validation failed')
        return value


class Division(BaseModel):
    division_id: Optional[str] = Form(None, min_length=24, max_length=24)
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
        if config.db.companies.find_one({"divisions.division_id": ObjectId(value)}) is None:
            raise ValueError('division._id validation failed')
        return value


class ThirdPartyCreate(BaseModel):
    name: str


class ThirdPartyEdit(BaseModel):
    third_party_id: str = Form(None, min_length=24, max_length=24)
    name: Optional[str]

    @validator('third_party_id', allow_reuse=True)
    def check_third_parties_id_omitted(cls, value):
        if config.db.companies.find_one({"third_parties.third_party_id": ObjectId(value)}) is None:
            raise ValueError('third_parties._id validation failed')
        return value

    @root_validator(pre=True)
    def check_optional_amount_omitted(cls, values):
        if not len(values) - int('third_party_id' in values) > 0:
            raise ValueError('one of the optional should be included')
        return values


class AvailableSignerCreate(BaseModel):
    name: str
    surname: str
    patronymic: Optional[str] = None


class AvailableSignerEdit(BaseModel):
    available_signer_id: str = Form(None, min_length=24, max_length=24)
    name: Optional[str]
    surname: Optional[str]
    patronymic: Optional[str]

    @validator('available_signer_id', allow_reuse=True)
    def check_available_signers_id_omitted(cls, value):
        if config.db.companies.find_one({"available_signers._id": ObjectId(value)}) is None:
            raise ValueError('available_signers._id validation failed')
        return value

    @root_validator(pre=True)
    def check_optional_amount_omitted(cls, values):
        if not len(values) - int('available_signer_id' in values) > 0:
            raise ValueError('one of the optional should be included')
        return values


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