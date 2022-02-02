from typing import Optional, List
from pydantic import BaseModel, validator, root_validator, Field
from fastapi import Form
from bson import ObjectId
import datetime
import config


class CreatePermissions(BaseModel):
    can_upload_files: Optional[bool] = False
    can_download_files: Optional[bool] = False
    can_add_filters: Optional[bool] = False
    can_change_company_data: Optional[bool] = False
    can_manage_employers: Optional[bool] = False


class EditPermissions(BaseModel):
    can_upload_files: Optional[bool] = None
    can_download_files: Optional[bool] = None
    can_add_filters: Optional[bool] = None
    can_change_company_data: Optional[bool] = None
    can_manage_employers: Optional[bool] = None


class AvailableRolesCreate(BaseModel):
    name: str
    permissions: Optional[CreatePermissions] = CreatePermissions()


class AvailableRolesCreateWithId(BaseModel):
    division_id: str = Form(..., min_length=24, max_length=24)
    name: str
    permissions: Optional[CreatePermissions] = CreatePermissions()

    @validator('division_id', allow_reuse=True)
    def check_divisions_id_omitted(cls, value):
        if not ObjectId.is_valid(value) \
                or config.db.companies.find_one({"divisions.division_id": ObjectId(value)}) is None:
            raise ValueError('division._id validation failed')
        return value


class AvailableRolesEdit(BaseModel):
    role_id: str = Form(..., min_length=24, max_length=24)
    name: Optional[str]
    permissions: Optional[EditPermissions]
    delete_me: Optional[bool] = False

    @validator('role_id', allow_reuse=True)
    def check_available_roles_id_omitted(cls, value):
        if not ObjectId.is_valid(value) or not len(list(config.db.companies.aggregate(
                [{"$unwind": "$divisions"},
                 {"$unwind": "$divisions.available_roles"},
                 {"$match": {"divisions.available_roles.role_id": ObjectId(value)}}]))) == 1:
            raise ValueError('divisions.available_signers.role_id validation failed')
        return value

    @root_validator(pre=True)
    def check_optional_amount_omitted(cls, values):
        if not len(values) - int('third_party_id' in values) > 0:
            raise ValueError('one of the optional should be included')
        if 'delete_me' in values and not values['delete_me']:
            raise ValueError(f"Parse 'delete_me' True and to delete'")
        for v in values.keys():
            if values[v] is None:
                raise ValueError(f"Field '{v}' must not be None")

        return values


class DivisionCreate(BaseModel):
    name: str
    available_roles: Optional[List[AvailableRolesCreate]] = Field(AvailableRolesCreate(
        name="admin",
        permissions={"can_upload_files": True,
                     "can_download_files": True,
                     "can_add_filters": True,
                     "can_change_company_data": True,
                     "can_manage_employers": True}), min_items=1)


class DivisionEdit(BaseModel):
    division_id: str = Form(..., min_length=24, max_length=24)
    name: Optional[str] = Field(nullable=False)
    available_roles: Optional[List[AvailableRolesEdit]] = Field(nullable=False)
    delete_me: Optional[bool] = False

    @validator('division_id', allow_reuse=True)
    def check_divisions_id_omitted(cls, value):
        if not ObjectId.is_valid(value) \
                or config.db.companies.find_one({"divisions.division_id": ObjectId(value)}) is None:
            raise ValueError('division._id validation failed')
        return value

    @root_validator(pre=True)
    def check_optional_amount_omitted(cls, values):
        if not len(values) - int('division_id' in values) > 0:
            raise ValueError('one of the optional should be included')
        if 'delete_me' in values and not values['delete_me']:
            raise ValueError(f"Parse 'delete_me' True and to delete'")
        for v in values.keys():
            if values[v] is None:
                raise ValueError(f"Field '{v}' must not be None")

        return values


class ThirdPartyCreate(BaseModel):
    name: str


class ThirdPartyEdit(BaseModel):
    third_party_id: str = Form(..., min_length=24, max_length=24)
    name: Optional[str] = Field(nullable=False)
    delete_me: Optional[bool] = False

    @validator('third_party_id', allow_reuse=True)
    def check_third_parties_id_omitted(cls, value):
        if not ObjectId.is_valid(value) \
                or config.db.companies.find_one({"third_parties.third_party_id": ObjectId(value)}) is None:
            raise ValueError('third_parties._id validation failed')
        return value

    @root_validator(pre=True)
    def check_optional_amount_omitted(cls, values):
        if not len(values) - int('third_party_id' in values) > 0:
            raise ValueError('one of the optional should be included')
        if 'delete_me' in values and not values['delete_me']:
            raise ValueError(f"Parse 'delete_me' True and to delete'")
        for v in values.keys():
            if values[v] is None:
                raise ValueError(f"Field '{v}' must not be None")

        return values


class AvailableSignerCreate(BaseModel):
    name: str
    surname: str
    patronymic: Optional[str] = None


class AvailableSignerEdit(BaseModel):
    available_signer_id: str = Form(..., min_length=24, max_length=24)
    name: Optional[str] = Field(nullable=False)
    surname: Optional[str] = Field(nullable=False)
    patronymic: Optional[str] = Field(nullable=False)
    delete_patronymic: Optional[bool] = False
    delete_me: Optional[bool] = False

    @validator('available_signer_id', allow_reuse=True)
    def check_available_signers_id_omitted(cls, value):
        if not ObjectId.is_valid(value):
            raise ValueError('available_signers._id validation failed')
        return value

    @root_validator(pre=True)
    def check_optional_amount_omitted(cls, values):
        if not len(values) - int('available_signer_id' in values) > 0:
            raise ValueError('one of the optional should be included')
        if 'delete_me' in values and not values['delete_me']:
            raise ValueError(f"Parse 'delete_me' True and to delete'")
        for v in values.keys():
            if values[v] is None:
                raise ValueError(f"Field '{v}' must not be None")
        if ('patronymic' in values and 'delete_patronymic' in values) \
                or ('delete_patronymic' in values and not values['delete_patronymic']):
            raise ValueError(f"Parse 'delete_patronymic' True and do not parse patronymic to delete'")
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
