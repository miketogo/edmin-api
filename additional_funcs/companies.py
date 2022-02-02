from bson import ObjectId
from fastapi import HTTPException
import os

import config


async def delete_object_ids_from_list(the_lists: list):
    for elem_id in range(len(the_lists)):
        if isinstance(the_lists[elem_id], ObjectId):
            the_lists[elem_id] = str(the_lists[elem_id])
        elif isinstance(the_lists[elem_id], dict):
            the_lists[elem_id] = await delete_object_ids_from_dict(the_lists[elem_id])
        elif isinstance(the_lists[elem_id], list):
            the_lists[elem_id] = await delete_object_ids_from_list(the_lists[elem_id])
    return the_lists


async def delete_object_ids_from_dict(the_dict: dict):
    for elem in the_dict.keys():
        if isinstance(the_dict[elem], ObjectId):
            the_dict[elem] = str(the_dict[elem])
        elif isinstance(the_dict[elem], dict):
            the_dict[elem] = await delete_object_ids_from_dict(the_dict[elem])
        elif isinstance(the_dict[elem], list):
            the_dict[elem] = await delete_object_ids_from_list(the_dict[elem])
    return the_dict


async def fill_in_object_ids_list(the_list: list):
    for elem_id in range(len(the_list)):
        if isinstance(the_list[elem_id], dict):
            the_list[elem_id] = await fill_in_object_ids_dict(the_list[elem_id])
        elif isinstance(the_list[elem_id], list):
            the_list[elem_id] = await fill_in_object_ids_list(the_list[elem_id])
    return the_list


async def fill_in_object_ids_dict(the_dict: dict):
    for elem in the_dict.keys():
        if elem[-3:] == '_id' and not ObjectId.is_valid(the_dict[elem]):
            the_dict[elem] = ObjectId()
        elif elem[-3:] == '_id' and ObjectId.is_valid(the_dict[elem]):
            the_dict[elem] = ObjectId(the_dict[elem])
        elif isinstance(the_dict[elem], dict):
            the_dict[elem] = await fill_in_object_ids_dict(the_dict[elem])
        elif isinstance(the_dict[elem], list):
            the_dict[elem] = await fill_in_object_ids_list(the_dict[elem])
    return the_dict


async def get_company(company_id: str):
    current_company = config.db.companies.find_one({"_id": ObjectId(company_id)})
    if current_company is not None:
        return await delete_object_ids_from_dict(current_company)
    raise HTTPException(status_code=404, detail='Could not find the current_company')


async def unset_company_at_users_files(company_id: str):
    config.db.users.update({"company_id": ObjectId(company_id)},
                           {"$set": {"company_id": None,
                                     "division_id": None,
                                     "role_id": None}})
    files = list(config.db.files.find({"company_id": ObjectId(company_id)}))
    for file in files:
        try:
            os.remove(file['path'])
            os.remove(file['preview_path'])
        except FileNotFoundError as e:
            print(e)
    config.db.files.remove({"company_id": ObjectId(company_id)})


async def get_permissions(role_id: str):
    return True
