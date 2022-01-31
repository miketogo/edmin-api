from typing import Optional
from fastapi import Form
from pydantic import BaseModel, root_validator


class ItemAddFileInfo(BaseModel):
    file_id: str = Form(..., min_length=24, max_length=24)
    children: Optional[list]
    parent: Optional[str] = Form(None, min_length=24, max_length=24)
    status: Optional[str]
    division: Optional[str] = Form(None, min_length=24, max_length=24)
    third_party: Optional[str] = Form(None, min_length=24, max_length=24)
    doc_date: Optional[str]
    exp_date: Optional[str]
    signed_by: Optional[str]

    @root_validator(pre=True)
    def check_status_number_omitted(cls, values):
        if len(values) < 2:
            raise ValueError('one of the optional should be included')
        return values


class ItemUploadFileEmpty(object):
    def __init__(self):
        self.children = list()
        self.parent = None
        self.status = None
        self.division = None
        self.third_party = None
        self.doc_date = None
        self.exp_date = None
        self.signed_by = None
