from typing import Optional
from dataclasses import dataclass
from fastapi import Form


@dataclass
class ItemAddFileInfo:
    company_id: str
    has_parent: bool
    children: list
    parent: Optional[str] = None
    status: Optional[str] = None
    devision: Optional[str] = None
    third_party: Optional[str] = None
    doc_date: Optional[str] = None
    exp_date: Optional[str] = None
    doc_type: Optional[str] = None
    signed_by: Optional[str] = None


@dataclass
class ItemUploadFileInfo:
    company_id: str
    user_id: str

    @classmethod
    def as_form(cls, company_id: str = Form(...), user_id: str = Form(...)) -> 'ItemUploadFileInfo':
        return cls(company_id=company_id, user_id=user_id)
