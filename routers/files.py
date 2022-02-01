import datetime

from fastapi import File, APIRouter, Depends, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from models.files import ItemAddFileInfo, ItemUploadFileEmpty
from additional_funcs.files import create_preview
from pymongo import ReturnDocument
from bson import ObjectId
from middlewares import auth as auth_middlewares
from additional_funcs import files as files_additional_funcs
import config


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
    preview_link = await create_preview(f'files/{file.filename}')
    info_dict = {
            "name": file.filename,
            "path": f'files/{file.filename}',
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
    for elem in data:
        if elem[0][-3:] == '_id' and elem[0] != 'file_id' and elem[1] is not None:
            await files_additional_funcs.check_if_ids_are_connected_to_the_company(elem, current_user.company_id)
        if elem[0] != 'file_id' and elem[1] is not None:
            item_updated[str(elem[0])] = elem[1]
    item_updated = await files_additional_funcs.fill_in_object_ids_dict(item_updated)
    item_updated["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    obj = config.db.files.find_one_and_update({'_id': ObjectId(file_id),
                                               'company_id': ObjectId(current_user.company_id)},
                                              {'$set': item_updated}, return_document=ReturnDocument.AFTER)
    if obj is not None:
        obj = await files_additional_funcs.delete_object_ids_from_dict(obj)
        return obj
    raise HTTPException(status_code=400, detail='No such Object_id was found')


@router.get("/uploads/cache/{file_name}")
async def get_uploaded_file(file_name):
    try:
        return StreamingResponse(open(f'cache/{file_name}', mode="rb"))

    except FileNotFoundError as e:
        print(e)
        raise HTTPException(status_code=404, detail='file not found')
