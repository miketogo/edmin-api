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
    company_list_doc_types = list()
    for doc_type_name in config.base_doc_types:
        doc_type_obj = companies_modules.DocTypeCreate(name=doc_type_name).dict()
        doc_type_obj['doc_type_id'] = None
        company_list_doc_types.append(doc_type_obj)
    company_dict['doc_types'] = company_list_doc_types
    company_dict['divisions'] = [companies_modules.DivisionCreate(
        name="admin", available_roles=[dict(
            name="admin",
            permissions={"can_upload_files": True,
                         "can_download_files": True,
                         "can_add_filters": True,
                         "can_change_company_data": True,
                         "can_manage_employers": True})]).dict()]
    company_dict['divisions'][0]['division_id'] = None
    company_dict['divisions'][0]['available_roles'][0]['role_id'] = None
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
                "third_parties": await companies_additional_funcs.fill_in_object_ids_dict(
                    {"third_party_id": None,
                     "name": third_party.name,
                     "folders": list()
                     })
            },
            '$set': {"recent_change": str(datetime.datetime.now().timestamp()).replace('.', '')}
        }, return_document=ReturnDocument.AFTER)
    if obj is not None:
        return await companies_additional_funcs.delete_object_ids_from_dict(obj)
    raise HTTPException(status_code=404, detail='Could not find an object')


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
        if elem[0] == 'delete_me' and elem[1]:
            obj = config.db.companies.find_one_and_update(
                {"_id": ObjectId(current_user.company_id)},
                {
                    '$pull': {"third_parties": {"third_party_id": ObjectId(third_party.third_party_id)}}
                }, return_document=ReturnDocument.AFTER)
            if obj is not None:
                return await companies_additional_funcs.delete_object_ids_from_dict(obj)
            raise HTTPException(status_code=404, detail='Could not find an object')
        if elem[0] != 'third_party_id' and elem[0] != 'delete_me':
            item_updated['third_parties.$.' + str(elem[0])] = elem[1]
    item_updated = await companies_additional_funcs.fill_in_object_ids_dict(item_updated)
    item_updated["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    obj = config.db.companies.find_one_and_update(
        {"_id": ObjectId(current_user.company_id),
         "third_parties.third_party_id": ObjectId(third_party.third_party_id)},
        {
            '$set': item_updated
        }, return_document=ReturnDocument.AFTER)
    if obj is not None:
        return await companies_additional_funcs.delete_object_ids_from_dict(obj)
    raise HTTPException(status_code=404, detail='Could not find an object')


@router.post("/create-available-signer")
async def create_available_signer(available_signer: companies_modules.AvailableSignerCreate,
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
                "available_signers": await companies_additional_funcs.fill_in_object_ids_dict(
                    {"available_signer_id": None,
                     "name": available_signer.name,
                     "surname": available_signer.surname,
                     "patronymic": available_signer.patronymic
                     })
            },
            '$set': {"recent_change": str(datetime.datetime.now().timestamp()).replace('.', '')}
        }, return_document=ReturnDocument.AFTER)
    if obj is not None:
        return await companies_additional_funcs.delete_object_ids_from_dict(obj)
    raise HTTPException(status_code=404, detail='Could not find an object')


@router.patch("/edit-available-signer")
async def edit_available_signer(available_signer: companies_modules.AvailableSignerEdit,
                                authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or not await companies_additional_funcs.get_permissions(current_user.role_id):
        raise HTTPException(status_code=400, detail='Company is not attached to the user'
                                                    ' or does not have permissions for that action')
    item_updated = dict()
    for elem in available_signer:
        if elem[0] == 'delete_me' and elem[1]:
            obj = config.db.companies.find_one_and_update(
                {"_id": ObjectId(current_user.company_id)},
                {
                    '$pull': {"available_signers":
                              {"available_signer_id": ObjectId(available_signer.available_signer_id)}}
                }, return_document=ReturnDocument.AFTER)
            if obj is not None:
                return await companies_additional_funcs.delete_object_ids_from_dict(obj)
            raise HTTPException(status_code=404, detail='Could not find an object')
        if elem[0] != 'available_signer_id' and elem[0] != 'delete_me':
            item_updated['available_signers.$.' + str(elem[0])] = elem[1]
    item_updated["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    obj = config.db.companies.find_one_and_update(
        {"_id": ObjectId(current_user.company_id),
         "available_signers.available_signer_id": ObjectId(available_signer.available_signer_id)},
        {
            '$set': await companies_additional_funcs.fill_in_object_ids_dict(item_updated)
        }, return_document=ReturnDocument.AFTER)
    if obj is not None:
        return await companies_additional_funcs.delete_object_ids_from_dict(obj)
    raise HTTPException(status_code=404, detail='Could not find an object')


@router.post("/create-division")
async def create_division(division: companies_modules.DivisionCreate,
                          authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or not await companies_additional_funcs.get_permissions(current_user.role_id):
        raise HTTPException(status_code=400, detail='Company is not attached to the user'
                                                    ' or does not have permissions for that action')
    if division.name == "admin":
        raise HTTPException(status_code=400, detail='Division name cannot be "admin"')
    available_roles = list()
    for available_role in division.available_roles:
        if not isinstance(available_role, tuple):
            available_role = available_role.dict()
            available_role["role_id"] = None
            available_roles.append(available_role)
        else:
            available_role = division.available_roles.dict()
            available_role["role_id"] = None
            available_roles.append(available_role)
            break
    insert_item = {"division_id": None,
                   "name": division.name,
                   "available_roles": available_roles
                   }
    obj = config.db.companies.find_one_and_update(
        {"_id": ObjectId(current_user.company_id)},
        {
            '$push': {
                "divisions": await companies_additional_funcs.fill_in_object_ids_dict(insert_item)
            },
            '$set': {"recent_change": str(datetime.datetime.now().timestamp()).replace('.', '')}
        }, return_document=ReturnDocument.AFTER)
    if obj is not None:
        return await companies_additional_funcs.delete_object_ids_from_dict(obj)
    raise HTTPException(status_code=404, detail='Could not find an object')


@router.patch("/edit-division")
async def edit_division(division: companies_modules.DivisionEdit,
                        authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or not await companies_additional_funcs.get_permissions(current_user.role_id):
        raise HTTPException(status_code=400, detail='Company is not attached to the user'
                                                    ' or does not have permissions for that action')
    if division.name == "admin":
        raise HTTPException(status_code=400, detail='Division name cannot be "admin"')
    item_updated = dict()
    for elem in division:
        if elem[0] == 'delete_me' and elem[1]:
            obj = config.db.companies.find_one_and_update(
                {"_id": ObjectId(current_user.company_id),
                 "divisions": {"$elemMatch": {"division_id": ObjectId(division.division_id),
                                              "name": {"$ne": "admin"}}}},
                {
                    '$pull': {"divisions": {"division_id": ObjectId(division.division_id)}}
                }, return_document=ReturnDocument.AFTER)
            if obj is not None:
                return await companies_additional_funcs.delete_object_ids_from_dict(obj)
            raise HTTPException(status_code=404, detail='Could not find an object')
        elif elem[0] != 'division_id' and elem[1] is not None and elem[0] != 'delete_me':
            item_updated['divisions.$.' + str(elem[0])] = elem[1]
    item_updated["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    obj = config.db.companies.find_one_and_update(
        {"_id": ObjectId(current_user.company_id),
         "divisions.division_id": ObjectId(division.division_id),
         "divisions.$.name": {"$ne": "admin"}},
        {
            '$set': await companies_additional_funcs.fill_in_object_ids_dict(item_updated)
        }, return_document=ReturnDocument.AFTER)
    if obj is not None:
        return await companies_additional_funcs.delete_object_ids_from_dict(obj)
    raise HTTPException(status_code=404, detail='Could not find an object')


@router.delete("/delete/{company_id}")
async def delete_company(company_id, authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.fresh_jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or company_id != current_user.company_id:
        raise HTTPException(status_code=400, detail="No company is attached")
    config.db.files.remove({"_id": ObjectId(company_id)})
    await companies_additional_funcs.unset_company_at_users_files(company_id)
    config.db.companies.remove({"_id": ObjectId(company_id)})
    return dict(msg="The company has been deleted")


@router.post("/create-available-role")
async def create_available_role(available_role: companies_modules.AvailableRolesCreateWithId,
                                authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or not await companies_additional_funcs.get_permissions(current_user.role_id):
        raise HTTPException(status_code=400, detail='Company is not attached to the user'
                                                    ' or does not have permissions for that action')
    obj = config.db.companies.find_one_and_update(
        {"_id": ObjectId(current_user.company_id),
         "divisions.division_id": ObjectId(available_role.division_id)},
        {
            '$push': {
                "divisions.$.available_roles": await companies_additional_funcs.fill_in_object_ids_dict(
                    {"role_id": None,
                     "name": available_role.name,
                     "permissions": available_role.permissions.dict()
                     })
            },
            '$set': {"recent_change": str(datetime.datetime.now().timestamp()).replace('.', '')}
        }, return_document=ReturnDocument.AFTER)
    if obj is not None:
        return await companies_additional_funcs.delete_object_ids_from_dict(obj)
    raise HTTPException(status_code=404, detail='Could not find an object')


@router.post("/edit-available-role")
async def create_available_role(available_role: companies_modules.AvailableRolesEdit,
                                authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or not await companies_additional_funcs.get_permissions(current_user.role_id):
        raise HTTPException(status_code=400, detail='Company is not attached to the user'
                                                    ' or does not have permissions for that action')
    available_role_obj = list(config.db.companies.aggregate(
                [{"$unwind": "$divisions"},
                 {"$unwind": "$divisions.available_roles"},
                 {"$match": {"divisions.available_roles.role_id": ObjectId(available_role.role_id)}}]))[0]
    if available_role_obj['divisions']['name'] == "admin" \
            or available_role_obj['divisions']['available_roles']['name'] == "admin":
        raise HTTPException(status_code=400, detail='Division name cannot be "admin"')
    item_updated = dict()
    array_filters = [{'outer.division_id': available_role_obj['divisions']['division_id']},
                     {"inner.role_id": ObjectId(available_role.role_id)}]
    for elem in available_role:
        if elem[0] == 'delete_me' and elem[1]:
            obj = config.db.companies.find_one_and_update(
                {"_id": ObjectId(current_user.company_id),
                 "divisions": {"$elemMatch": {"division_id": available_role_obj['divisions']['division_id'],
                                              "name": {"$ne": "admin"}}}},
                {
                    '$pull': {"divisions": {"available_roles": {"role_id": ObjectId(available_role.role_id)}}}
                }, return_document=ReturnDocument.AFTER)
            if obj is not None:
                return await companies_additional_funcs.delete_object_ids_from_dict(obj)
            raise HTTPException(status_code=404, detail='Could not find an object')
        elif elem[0] != 'role_id' and elem[1] is not None and elem[0] != 'delete_me':
            item_updated['divisions.$[outer].available_roles.$[inner].' + str(elem[0])] = elem[1]
    item_updated["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    obj = config.db.companies.find_one_and_update(
        {"_id": ObjectId(current_user.company_id)},
        {
            '$set': await companies_additional_funcs.fill_in_object_ids_dict(item_updated)
        }, array_filters=array_filters, return_document=ReturnDocument.AFTER)
    if obj is not None:
        return await companies_additional_funcs.delete_object_ids_from_dict(obj)
    raise HTTPException(status_code=404, detail='Could not find an object')


@router.post("/create-doc-type")
async def create_doc_type(doc_type: companies_modules.DocTypeCreate,
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
                "doc_types": await companies_additional_funcs.fill_in_object_ids_dict(
                    {"doc_type_id": None,
                     "name": doc_type.name
                     })
            },
            '$set': {"recent_change": str(datetime.datetime.now().timestamp()).replace('.', '')}
        }, return_document=ReturnDocument.AFTER)
    if obj is not None:
        return await companies_additional_funcs.delete_object_ids_from_dict(obj)
    raise HTTPException(status_code=404, detail='Could not find an object')


@router.patch("/edit-doc-type")
async def edit_doc_type(doc_type: companies_modules.DocTypeEdit,
                        authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or not await companies_additional_funcs.get_permissions(current_user.role_id):
        raise HTTPException(status_code=400, detail='Company is not attached to the user'
                                                    ' or does not have permissions for that action')
    item_updated = dict()
    for elem in doc_type:
        if elem[0] != 'doc_type_id':
            item_updated['doc_types.$.' + str(elem[0])] = elem[1]
    item_updated["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    obj = config.db.companies.find_one_and_update(
        {"_id": ObjectId(current_user.company_id),
         "doc_types": {"$elemMatch": {"doc_type_id": ObjectId(doc_type.doc_type_id),
                                      "name": {"$nin": config.base_doc_types}}}},
        {
            '$set': await companies_additional_funcs.fill_in_object_ids_dict(item_updated)
        }, return_document=ReturnDocument.AFTER)
    if obj is not None:
        return await companies_additional_funcs.delete_object_ids_from_dict(obj)
    raise HTTPException(status_code=404, detail='Could not find an object')


@router.post("/create-third-party-folder")
async def create_third_party_folder(third_party_folder: companies_modules.ThirdPartyFolderCreate,
                                    authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or not await companies_additional_funcs.get_permissions(current_user.role_id):
        raise HTTPException(status_code=400, detail='Company is not attached to the user'
                                                    ' or does not have permissions for that action')
    obj = config.db.companies.find_one_and_update(
        {"_id": ObjectId(current_user.company_id),
         "third_parties.third_party_id": ObjectId(third_party_folder.third_party_id)},
        {
            '$push': {
                "third_parties.$.folders": await companies_additional_funcs.fill_in_object_ids_dict(
                    {"third_party_folder_id": None,
                     "name": third_party_folder.name
                     })
            },
            '$set': {"recent_change": str(datetime.datetime.now().timestamp()).replace('.', '')}
        }, return_document=ReturnDocument.AFTER)
    if obj is not None:
        return await companies_additional_funcs.delete_object_ids_from_dict(obj)
    raise HTTPException(status_code=404, detail='Could not find an object')


@router.post("/edit-third-party-folder")
async def edit_third_party_folder(third_party_folder: companies_modules.ThirdPartyFolderEdit,
                                  authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or not await companies_additional_funcs.get_permissions(current_user.role_id):
        raise HTTPException(status_code=400, detail='Company is not attached to the user'
                                                    ' or does not have permissions for that action')
    available_role_obj = list(config.db.companies.aggregate(
                [{"$unwind": "$third_parties"},
                 {"$unwind": "$third_parties.folders"},
                 {"$match": {"third_parties.folders.third_party_folder_id":
                             ObjectId(third_party_folder.third_party_folder_id)}}]))[0]
    item_updated = dict()
    array_filters = [{'outer.third_party_id': available_role_obj['third_parties']['third_party_id']},
                     {"inner.third_party_folder_id": ObjectId(third_party_folder.third_party_folder_id)}]
    for elem in third_party_folder:
        if elem[0] == 'delete_me' and elem[1]:
            obj = config.db.companies.find_one_and_update(
                {"_id": ObjectId(current_user.company_id),
                 "third_parties": {"$elemMatch": {"third_party_id":
                                                  available_role_obj['third_parties']['third_party_id']}}},
                {
                    '$pull': {"third_parties": {"folders": {"third_party_folder_id":
                                                            ObjectId(third_party_folder.third_party_folder_id)}}}
                }, return_document=ReturnDocument.AFTER)
            if obj is not None:
                config.db.files.update({"third_party_folder_id": ObjectId(third_party_folder.third_party_folder_id),
                                        "$set": {"third_party_folder_id": None}})
                return await companies_additional_funcs.delete_object_ids_from_dict(obj)
            raise HTTPException(status_code=404, detail='Could not find an object')
        elif elem[0] != 'third_party_folder_id' and elem[1] is not None and elem[0] != 'delete_me':
            item_updated['third_parties.$[outer].folders.$[inner].' + str(elem[0])] = elem[1]
    item_updated["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    obj = config.db.companies.find_one_and_update(
        {"_id": ObjectId(current_user.company_id)},
        {
            '$set': await companies_additional_funcs.fill_in_object_ids_dict(item_updated)
        }, array_filters=array_filters, return_document=ReturnDocument.AFTER)
    if obj is not None:
        return await companies_additional_funcs.delete_object_ids_from_dict(obj)
    raise HTTPException(status_code=404, detail='Could not find an object')


@router.get("/check-jwt")
async def get_company_object(authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    current_company = await companies_additional_funcs.get_company(current_user.company_id)
    return current_company
