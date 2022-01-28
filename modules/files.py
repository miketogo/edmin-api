from typing import Optional
from fastapi import Form
from pydantic import BaseModel, root_validator, validator
from bson import ObjectId
import config


class ItemAddFileInfo(BaseModel):
    file_id: str = Form(..., min_length=24, max_length=24)
    has_parent: Optional[bool]
    children: Optional[list]
    parent: Optional[str]
    status: Optional[str]
    division: Optional[str]
    third_party: Optional[str]
    doc_date: Optional[str]
    exp_date: Optional[str]
    doc_type: Optional[str]
    signed_by: Optional[str]

    @root_validator(pre=True)
    def check_status_number_omitted(cls, values):
        if len(values) < 2:
            raise ValueError('one of the optional should be included')
        if 'has_parent' in values and values['has_parent'] and 'parent' not in values:
            raise ValueError('if field "has_parent" is true then parent field should not be empty')
        return values

    @validator('parent', check_fields=False)
    def check_parent_omitted(cls, value):
        if value is not None and (len(value) != 24
                                  or config.db.files.find_one({"_id": ObjectId(value)}) is None):
            raise ValueError('parent validation failed')
        return value
