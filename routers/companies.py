import datetime

from fastapi import APIRouter, Depends, HTTPException

import config
from middlewares import auth as auth_middlewares
from additional_funcs import companies as companies_additional_funcs
from models import companies as companies_modules
from pymongo import ReturnDocument
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
    company_dict['third_parties'] = list()
    company_dict['available_signers'] = list()
    company_dict['subscription'] = companies_modules.Subscription().dict()
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


@router.post("/create-third-party")
async def create_third_party(third_party: companies_modules.ThirdPartyCreate,
                             authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or not await companies_additional_funcs.get_permissions(current_user.role_id):
        raise HTTPException(status_code=400, detail='Company is not attached to the user'
                                                    ' or does not have permissions for that action')
    obj = config.db.companies.find_one_and_update(
        {"_id": ObjectId(current_user.company_id)},
        {
            '$push': {
                "third_parties": {"third_party_id": ObjectId(),
                                  "name": third_party.name
                                  }
            },
            '$set': {"recent_change": str(datetime.datetime.now().timestamp()).replace('.', '')}
        }, return_document=ReturnDocument.AFTER)
    return await companies_additional_funcs.delete_object_ids_from_dict(obj)


@router.patch("/edit-third-party")
async def edit_third_party(third_party: companies_modules.ThirdPartyEdit,
                           authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or not await companies_additional_funcs.get_permissions(current_user.role_id):
        raise HTTPException(status_code=400, detail='Company is not attached to the user'
                                                    ' or does not have permissions for that action')
    item_updated = dict()
    for elem in third_party:
        if elem[0] != 'third_party_id':
            item_updated['third_parties.$.' + str(elem[0])] = elem[1]
    item_updated = await companies_additional_funcs.fill_in_object_ids_dict(item_updated)
    item_updated["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    obj = config.db.companies.find_one_and_update(
        {"_id": ObjectId(current_user.company_id),
         "third_parties.third_party_id": ObjectId(third_party.third_party_id)},
        {
            '$set': item_updated
        }, return_document=ReturnDocument.AFTER)
    return await companies_additional_funcs.delete_object_ids_from_dict(obj)


@router.get("/check-jwt")
async def get_company_object(authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    current_company = await companies_additional_funcs.get_company(current_user.company_id)
    return current_company
