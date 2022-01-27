from typing import Optional
from fastapi import Form
from pydantic import BaseModel, root_validator


def form_body(cls):
    cls.__signature__ = cls.__signature__.replace(
        parameters=[
            arg.replace(default=Form(...))
            for arg in cls.__signature__.parameters.values()
        ]
    )
    return cls


class ItemAddFileInfo(BaseModel):
    file_id: str = Form(..., min_length=24, max_length=24)
    has_parent: Optional[bool]
    children: Optional[list]
    parent: Optional[str]
    status: Optional[str]
    devision: Optional[str]
    third_party: Optional[str]
    doc_date: Optional[str]
    exp_date: Optional[str]
    doc_type: Optional[str]
    signed_by: Optional[str]

    @root_validator(pre=True)
    def check_status_number_omitted(cls, values):
        if len(values) < 2:
            raise ValueError('one of the optional should be included')
        return values


@form_body
class ItemUploadFileInfo(BaseModel):
    company_id: str = Form(..., min_length=24, max_length=24)
    user_id: str = Form(..., min_length=24, max_length=24)
