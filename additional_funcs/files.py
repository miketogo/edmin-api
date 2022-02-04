from preview_generator.manager import PreviewManager
from fastapi import HTTPException
from bson import ObjectId
from shutil import move, rmtree

import config


async def create_preview(path_to_file):
    try:
        save_path_aka_object_id = str(ObjectId())
        manager = PreviewManager(save_path_aka_object_id, create_folder=True)
        path_to_preview_image = manager.get_jpeg_preview(path_to_file, page=0, height=1920, width=1920)
        new_path_to_preview_image_name = \
            rf'{save_path_aka_object_id}.{path_to_preview_image.split("/")[-1].split(".")[-1]}'
        move(path_to_preview_image, config.full_save_preview_file_path + '/' + new_path_to_preview_image_name)
        rmtree(save_path_aka_object_id, ignore_errors=True)
        return f'cache/{new_path_to_preview_image_name}', save_path_aka_object_id
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail='Could not make a preview')


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
        if elem[-3:] == '_id' and not ObjectId.is_valid(the_dict[elem]) and not isinstance(the_dict[elem], bool):
            the_dict[elem] = ObjectId()
        elif elem[-3:] == '_id' and ObjectId.is_valid(the_dict[elem]) and not isinstance(the_dict[elem], bool):
            the_dict[elem] = ObjectId(the_dict[elem])
        elif isinstance(the_dict[elem], bool) and the_dict[elem]:
            the_dict[elem] = None
        elif isinstance(the_dict[elem], dict):
            the_dict[elem] = await fill_in_object_ids_dict(the_dict[elem])
        elif isinstance(the_dict[elem], list):
            the_dict[elem] = await fill_in_object_ids_list(the_dict[elem])
    return the_dict


async def check_if_ids_are_connected_to_the_company(the_tuple: tuple, company_id: str, base_file_id: str):
    if the_tuple[0] == 'parent_id' and the_tuple[1] != base_file_id:
        obj = config.db.files.find_one({"_id": ObjectId(the_tuple[1])})
        if obj is not None and str(obj['company_id']) == company_id \
                and (obj['parent_id'] is None or str(obj['parent_id']) != base_file_id):
            return True
    elif the_tuple[0] == 'available_signer_id':
        obj = config.db.companies.find_one({"_id": ObjectId(company_id),
                                            "available_signers.available_signer_id": ObjectId(the_tuple[1])})
        if obj is not None:
            return True
    elif the_tuple[0] == 'division_id':
        obj = config.db.companies.find_one({"_id": ObjectId(company_id),
                                            "divisions.division_id": ObjectId(the_tuple[1])})
        if obj is not None:
            return True
    elif the_tuple[0] == 'third_party_id':
        obj = config.db.companies.find_one({"_id": ObjectId(company_id),
                                            "third_parties.third_party_id": ObjectId(the_tuple[1])})
        if obj is not None:
            return True

    elif the_tuple[0] == 'third_party_folder_id':
        obj = list(config.db.companies.aggregate(
                [{"$unwind": "$third_parties"},
                 {"$unwind": "$third_parties.folders"},
                 {"$match": {"third_parties.folders.third_party_folder_id": ObjectId(the_tuple[1])}}]))
        if len(obj) != 0:
            return True

    elif the_tuple[0] == 'doc_type_id':
        obj = config.db.companies.find_one({"_id": ObjectId(company_id),
                                            "doc_types.doc_type_id": ObjectId(the_tuple[1])})
        if obj is not None:
            return True

    raise HTTPException(status_code=400, detail='one of the ids was not found in db')


async def search_for_parents(parent_file_id: str, history_list: list):
    obj = config.db.files.find_one({'_id': ObjectId(parent_file_id)})
    if obj is not None:
        history_list.append(obj)
        return await search_for_parents(obj['parent_id'], history_list)
    return history_list
