from typing import Optional
from fastapi import Form
from pydantic import BaseModel, root_validator, validator
import config
from bson import ObjectId


class ItemUploadFileEmpty(object):
    def __init__(self):
        self.parent_id = None
        self.status = None
        self.division_id = None
        self.third_party_id = None
        self.doc_date = None
        self.exp_date = None
        self.available_signer_id = None


class ItemAddFileInfo(BaseModel):
    file_id: str = Form(..., min_length=24, max_length=24)
    parent_id: Optional[str] = Form(None, min_length=24, max_length=24)
    status: Optional[str]
    division_id: Optional[str] = Form(None, min_length=24, max_length=24)
    third_party_id: Optional[str] = Form(None, min_length=24, max_length=24)
    doc_date: Optional[str]
    exp_date: Optional[str]
    available_signer_id: Optional[str] = Form(None, min_length=24, max_length=24)
    delete_third_party_id: Optional[bool] = False
    delete_division_id: Optional[bool] = False
    delete_parent_id: Optional[bool] = False
    delete_available_signer_id: Optional[bool] = False

    @root_validator(pre=True)
    def check_optional_amount_omitted(cls, values):
        if not len(values) - int('file_id' in values) > 0:
            raise ValueError('one of the optional should be included')

        if ('parent_id' in values and 'delete_parent_id' in values) \
                or ('delete_parent_id' in values and not values['delete_parent_id']):
            raise ValueError(f"Parse 'delete_parent_id' True and do not parse parent_id to delete'")

        if ('available_signer_id' in values and 'delete_available_signer_id' in values) \
                or ('delete_available_signer_id' in values and not values['delete_available_signer_id']):
            raise ValueError(f"Parse 'delete_available_signer_id' True and do not parse available_signer_id to delete'")

        if ('division_id' in values and 'delete_division_id' in values) \
                or ('delete_division_id' in values and not values['delete_division_id']):
            raise ValueError(f"Parse 'delete_division_id' True and do not parse division_id to delete'")

        if ('third_party_id' in values and 'delete_third_party_id' in values) \
                or ('delete_third_party_id' in values and not values['delete_third_party_id']):
            raise ValueError(f"Parse 'delete_third_party_id' True and do not parse third_party_id to delete'")
        return values

    @validator('division_id', allow_reuse=True)
    def check_divisions_id_omitted(cls, value):
        if not ObjectId.is_valid(value) \
                or config.db.companies.find_one({"divisions.division_id": ObjectId(value)}) is None:
            raise ValueError('division._id validation failed')
        return value

    @validator('third_party_id', allow_reuse=True)
    def check_third_parties_id_omitted(cls, value):
        if not ObjectId.is_valid(value) \
                or config.db.companies.find_one({"third_parties.third_party_id": ObjectId(value)}) is None:
            raise ValueError('third_parties._id validation failed')
        return value

    @validator('available_signer_id', allow_reuse=True)
    def check_available_signers_id_omitted(cls, value):
        if not ObjectId.is_valid(value) \
                or config.db.companies.find_one({"available_signers._id": ObjectId(value)}) is None:
            raise ValueError('available_signers._id validation failed')
        return value
