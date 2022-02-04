import datetime

from fastapi import File, APIRouter, Depends, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from models.files import ItemAddFileInfo, ItemUploadFileEmpty
from additional_funcs.files import create_preview
from pymongo import ReturnDocument
from bson import ObjectId
from middlewares import auth as auth_middlewares
from additional_funcs import files as files_additional_funcs
import config
import os


router = APIRouter(
    prefix="/files",
    tags=["files"],
    responses={404: {"description": "Not found"}}
)


@router.post("/upload")
async def create_file(authorize: auth_middlewares.AuthJWT = Depends(),
                      file: UploadFile = File(...)):
    authorize.jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None:
        raise HTTPException(status_code=400, detail="No company is attached")
    file_read = await file.read()
    with open(f'files/{file.filename}', 'wb') as doc:
        doc.write(file_read)
        file_size = len(file_read)
    preview_link, file_object_id = await create_preview(f'files/{file.filename}')
    os.rename(f'files/{file.filename}', f'files/{file_object_id}.{file.filename.split(".")[-1]}')
    info_dict = {
            "name": file.filename,
            "path": f'files/{file_object_id}.{file.filename.split(".")[-1]}',
            "content_type": file.content_type,
            "size": file_size,
            "preview_path": preview_link,
            "upload_date": (datetime.datetime.now()).strftime("%d.%m.%Y %H:%M:%S"),
            "uploaded_by": ObjectId(current_user.id),
            "company_id": ObjectId(current_user.company_id),
            "recent_change": str(datetime.datetime.now().timestamp()).replace('.', '')
    }
    info_dict_of_an_empty_doc = ItemUploadFileEmpty().__dict__
    for key in info_dict_of_an_empty_doc.keys():
        info_dict[key] = info_dict_of_an_empty_doc[key]
    config.db.files.insert_one(info_dict)
    info_dict = await files_additional_funcs.delete_object_ids_from_dict(info_dict)
    return info_dict


@router.post("/add_info")
async def add_file_info(data: ItemAddFileInfo, authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None:
        raise HTTPException(status_code=400, detail="No company is attached")
    item_updated = dict()
    file_id = data.file_id

    if data.third_party_folder_id is not None and data.third_party_id is None:
        file = config.db.files.find_one({'_id': ObjectId(file_id),
                                         'company_id': ObjectId(current_user.company_id)})
        if file is None or file['third_party_id'] is None:
            raise HTTPException(status_code=400, detail='Attempt to set folder id to the file without third_party')
    elif data.third_party_folder_id is not None and data.third_party_id is not None:
        obj = config.db.companies.find_one({'_id': ObjectId(current_user.company_id),
                                            "third_parties": {
                                                "$elemMatch": {
                                                    "third_party_id": ObjectId(data.third_party_id),
                                                    "folders": {
                                                        "$elemMatch": {
                                                            "third_party_folder_id":
                                                                ObjectId(data.third_party_folder_id)}}}}})
        if obj is None:
            raise HTTPException(status_code=400, detail='Folder id not attached to company third_party')

    for elem in data:
        if elem[0][-3:] == '_id' and elem[0] != 'file_id' and elem[1] is not None and elem[0][:6] != 'delete':
            await files_additional_funcs.check_if_ids_are_connected_to_the_company(elem, current_user.company_id)
        if elem[0] != 'file_id' and elem[1] is not None and elem[0][:6] != 'delete':
            item_updated[str(elem[0])] = elem[1]
        elif elem[0][:6] == 'delete' and elem[1]:
            item_updated[str(elem[0][7:])] = elem[1]
    item_updated = await files_additional_funcs.fill_in_object_ids_dict(item_updated)
    item_updated["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    obj = config.db.files.find_one_and_update({'_id': ObjectId(file_id),
                                               'company_id': ObjectId(current_user.company_id)},
                                              {'$set': item_updated}, return_document=ReturnDocument.AFTER)
    if obj is not None:
        if data.delete_third_party_id or (data.third_party_id is not None and data.third_party_folder_id is None):
            obj = config.db.files.find_one_and_update({'_id': ObjectId(file_id),
                                                       'company_id': ObjectId(current_user.company_id)},
                                                      {'$set': {"third_party_folder_id": None}},
                                                      return_document=ReturnDocument.AFTER)
        obj = await files_additional_funcs.delete_object_ids_from_dict(obj)
        return obj
    raise HTTPException(status_code=400, detail='No such Object_id was found')


@router.delete("/delete/{file_id}")
async def delete_file(file_id, authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    if not ObjectId.is_valid(file_id):
        raise HTTPException(status_code=400, detail='Not valid Object_id')
    file = config.db.files.find_one({"_id": ObjectId(file_id)})
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or file is None or str(file['company_id']) != current_user.company_id:
        raise HTTPException(status_code=400, detail="No company is attached")
    config.db.files.remove({"_id": ObjectId(file_id)})
    try:
        os.remove(file['path'])
        os.remove(file['preview_path'])
    except FileNotFoundError as e:
        print(e)
    return dict(msg="The file has been deleted")


@router.get("/get-file/{file_id}")
async def get_file(file_id, authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    if not ObjectId.is_valid(file_id):
        raise HTTPException(status_code=400, detail='Not valid Object_id')
    file = config.db.files.find_one({"_id": ObjectId(file_id)})
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or file is None or str(file['company_id']) != current_user.company_id:
        raise HTTPException(status_code=400, detail="No company is attached")
    file = await files_additional_funcs.delete_object_ids_from_dict(file)
    return file


@router.get("/get-by-third-party/{third_party_id}")
async def get_file(third_party_id, authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    if not ObjectId.is_valid(third_party_id):
        raise HTTPException(status_code=400, detail='Not valid Object_id')
    company = list(config.db.companies.aggregate([{"$unwind": "$third_parties"},
                                                  {"$match": {
                                                      "third_parties.third_party_id": ObjectId(third_party_id)}}]))
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or len(company) != 1 or str(company[0]['_id']) != current_user.company_id:
        raise HTTPException(status_code=400, detail="No company is attached")
    company = company[0]

    files_not_in_folders = config.db.files.find({
            'third_party_id': ObjectId(third_party_id),
            'third_party_folder_id': None})
    files_with_doc_types = dict()
    files_without_doc_types = list()
    for file in files_not_in_folders:
        if file['doc_type_id'] not in files_with_doc_types.keys() and file['doc_type_id'] is not None:
            files_with_doc_types[str(file['doc_type_id'])] = list()
            files_with_doc_types[str(file['doc_type_id'])].append(file['_id'])
        elif file['doc_type_id'] is not None:
            files_with_doc_types[str(file['doc_type_id'])].append(file['_id'])
        else:
            files_without_doc_types.append(file["_id"])
    files_not_in_folders = dict()
    files_not_in_folders['without_doc_type'] = files_without_doc_types
    files_not_in_folders['with_doc_type'] = files_with_doc_types

    files_in_folders = dict()
    folders = company['third_parties']['folders']
    for folder in folders:
        third_party_folder_id = ObjectId(folder['third_party_folder_id'])
        files = config.db.files.find({'third_party_folder_id': third_party_folder_id})
        files_with_doc_types = dict()
        files_without_doc_types = list()
        for file in files:
            if file['doc_type_id'] not in files_with_doc_types.keys() and file['doc_type_id'] is not None:
                files_with_doc_types[str(file['doc_type_id'])] = list()
                files_with_doc_types[str(file['doc_type_id'])].append(file['_id'])
            elif file['doc_type_id'] is not None:
                files_with_doc_types[str(file['doc_type_id'])].append(file['_id'])
            else:
                files_without_doc_types.append(file["_id"])
        files_in_folders[str(third_party_folder_id)] = dict()
        files_in_folders[str(third_party_folder_id)]['without_doc_type'] = files_without_doc_types
        files_in_folders[str(third_party_folder_id)]['with_doc_type'] = files_with_doc_types

    dict_to_return = dict()
    dict_to_return['files_not_in_folders'] = files_not_in_folders
    dict_to_return['files_in_folders'] = files_in_folders
    dict_to_return = await files_additional_funcs.delete_object_ids_from_dict(dict_to_return)
    return dict_to_return


@router.get("/get-by-third-party-folder-id/{third_party_folder_id}")
async def get_file(third_party_folder_id, authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    if not ObjectId.is_valid(third_party_folder_id):
        raise HTTPException(status_code=400, detail='Not valid Object_id')
    company = list(config.db.companies.aggregate(
        [{"$unwind": "$third_parties"},
         {"$unwind": "$third_parties.folders"},
         {"$match": {"third_parties.folders.third_party_folder_id": ObjectId(third_party_folder_id)}}]))
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or len(company) != 1 or str(company[0]['_id']) != current_user.company_id:
        raise HTTPException(status_code=400, detail="No company is attached")

    files_in_folder = config.db.files.find({
            'third_party_folder_id': ObjectId(third_party_folder_id)})
    files_with_doc_types = dict()
    files_without_doc_types = list()
    for file in files_in_folder:
        if file['doc_type_id'] not in files_with_doc_types.keys() and file['doc_type_id'] is not None:
            files_with_doc_types[str(file['doc_type_id'])] = list()
            files_with_doc_types[str(file['doc_type_id'])].append(file['_id'])
        elif file['doc_type_id'] is not None:
            files_with_doc_types[str(file['doc_type_id'])].append(file['_id'])
        else:
            files_without_doc_types.append(file["_id"])
    files_in_folder = dict()
    files_in_folder['without_doc_type'] = files_without_doc_types
    files_in_folder['with_doc_type'] = files_with_doc_types

    dict_to_return = dict()
    dict_to_return['files_in_folders'] = files_in_folder
    dict_to_return = await files_additional_funcs.delete_object_ids_from_dict(dict_to_return)
    return dict_to_return


@router.get("/get-file-history/{file_id}")
async def get_file_history(file_id, authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    if not ObjectId.is_valid(file_id):
        raise HTTPException(status_code=400, detail='Not valid Object_id')
    file = config.db.files.find_one({"_id": ObjectId(file_id)})
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or file is None or str(file['company_id']) != current_user.company_id:
        raise HTTPException(status_code=400, detail="No company is attached")
    history_list = list()
    history_list.append(file)
    file_history = await files_additional_funcs.search_for_parents(str(file['parent_id']), history_list)
    return await files_additional_funcs.delete_object_ids_from_list(file_history)


@router.get("/uploads/cache/{file_id}")
async def get_uploaded_file(file_id, authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    file = config.db.files.find_one({"_id": ObjectId(file_id)})
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or file is None or str(file['company_id']) != current_user.company_id:
        raise HTTPException(status_code=400, detail="No company is attached")
    try:
        return StreamingResponse(open(file['preview_path'], mode="rb"))

    except FileNotFoundError as e:
        print(e)
        raise HTTPException(status_code=404, detail='file not found')


@router.get("/uploads/files/{file_id}")
async def get_uploaded_file(file_id, authorize: auth_middlewares.AuthJWT = Depends()):
    authorize.jwt_required()
    file = config.db.files.find_one({"_id": ObjectId(file_id)})
    current_user = await auth_middlewares.get_user(authorize.get_jwt_subject(), _id_check=True)
    if current_user.company_id is None or file is None or str(file['company_id']) != current_user.company_id:
        raise HTTPException(status_code=400, detail="No company is attached")
    try:
        return FileResponse(file['path'],
                            media_type=file['content_type'],
                            filename=file['name'])

    except FileNotFoundError as e:
        print(e)
        raise HTTPException(status_code=404, detail='file not found')
