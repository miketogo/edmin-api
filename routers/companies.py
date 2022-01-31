import datetime

from fastapi import APIRouter, Depends, HTTPException

import config
from middlewares import auth as auth_middlewares
from additional_funcs import companies as companies_additional_funcs
from models import companies as companies_modules
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
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is not None:
        raise HTTPException(status_code=400, detail='Company is already attached to the user')
    company_dict = company.dict()
    company_dict['divisions'] = [companies_modules.Division(name="admin").dict()]
    company_dict["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    company_dict = await companies_additional_funcs.fill_in_object_ids_dict(company_dict)
    config.db.companies.insert_one(company_dict)
    config.db.users.update_one({'_id': ObjectId(current_user.id)},
                               {'$set': {'company_id': company_dict["_id"],
                                         'division_id': company_dict["divisions"][0]["division_id"],
                                         'role_id': company_dict["divisions"][0]["available_roles"][0]["role_id"],
                                         "recent_change": str(datetime.datetime.now().timestamp()).replace('.', '')}})
    company_dict = await companies_additional_funcs.delete_object_ids_from_dict(company_dict)
    return company_dict


@router.get("/check-jwt")
async def get_company_object(authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    current_company = await companies_additional_funcs.get_company(current_user.company_id)
    return current_company
