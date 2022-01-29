import datetime

from fastapi import APIRouter, Depends, HTTPException

import config
from middlewares import auth as auth_middlewares
from additional_funcs import companies as companies_additional_funcs
from modules.users import User
from modules import companies as companies_modules
from bson import ObjectId


router = APIRouter(
    prefix="/companies",
    tags=["companies"],
    responses={404: {"description": "Not found"}}
)


@router.post("/create")
async def create_company(company: companies_modules.ItemCompanyCreate,
                         authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user: User = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user is None:
        raise HTTPException(status_code=404, detail='Could not find the current_user')
    if current_user.company_id is not None:
        raise HTTPException(status_code=400, detail='Company is already attached to the user')
    company_dict = company.dict()
    company_dict["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    config.db.companies.insert_one(company_dict)
    company_dict = await companies_additional_funcs.delete_object_ids_from_dict(company_dict)
    config.db.users.update_one({'_id': ObjectId(current_user.id)},
                               {'$set': {'company_id': ObjectId(company_dict["_id"]),
                                         "recent_change": str(datetime.datetime.now().timestamp()).replace('.', '')}})
    return company_dict
