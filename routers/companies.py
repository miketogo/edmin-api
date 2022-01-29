import datetime

from fastapi import APIRouter, Depends, HTTPException

import config
from fastapi.responses import Response
from middlewares import users as users_middlewares
from modules import users as users_modules
from modules import companies as companies_modules
from bson import ObjectId


router = APIRouter(
    prefix="/companies",
    tags=["companies"],
    responses={404: {"description": "Not found"}}
)


@router.post("/create")
async def create_company(response: Response,
                         company: companies_modules.ItemCompanyCreate,
                         current_user: users_modules.User
                         = Depends(users_middlewares.get_current_active_user)):
    await users_middlewares.refresh_token(response, current_user.id)
    print(current_user.company_id, type(current_user.company_id))
    if current_user.company_id is not None:
        raise HTTPException(status_code=400, detail='Company is already attached to the user')
    company_dict = company.dict()
    company_dict["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    config.db.companies.insert_one(company_dict)
    company_dict = await users_middlewares.delete_object_ids_from_dict(company_dict)
    config.db.users.update_one({'_id': ObjectId(current_user.id)},
                               {'$set': {'company_id': ObjectId(company_dict["_id"]),
                                         "recent_change": str(datetime.datetime.now().timestamp()).replace('.', '')}})
    return company_dict
