from typing import Optional
from dataclasses import dataclass
from bson import ObjectId


@dataclass
class ItemAddFileInfo:
    company_id: ObjectId
    has_parent: bool
    children: list
    parent: Optional[ObjectId] = None
    status: Optional[str] = None
    devision: Optional[ObjectId] = None
    third_party: Optional[ObjectId] = None
    doc_date: Optional[str] = None
    exp_date: Optional[str] = None
    doc_type: Optional[ObjectId] = None
    signed_by: Optional[ObjectId] = None
