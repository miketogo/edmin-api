import datetime

from fastapi import File, APIRouter, Depends, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from modules.files import ItemAddFileInfo
from middlewares.files import create_preview
from pymongo import ReturnDocument
from bson import ObjectId
from fastapi.responses import Response
from middlewares import users as users_middlewares
from modules.users import User
import config


router = APIRouter(
    prefix="/files",
    tags=["files"],
    responses={404: {"description": "Not found"}}
)


@router.post("/upload")
async def create_file(response: Response, current_user: User = Depends(users_middlewares.get_current_active_user),
                      file: UploadFile = File(...)):
    if current_user.company_id is None:
        raise HTTPException(status_code=400, detail="No company is attached")
    await users_middlewares.refresh_token(response, current_user.id)
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
            "has_parent": False,
            "children": list(),
            "parent": None,
            "status": None,
            "division": None,
            "third_party": None,
            "effective_date": None,
            "expiration_date": None,
            "signed_by": None,
            "recent_change": str(datetime.datetime.now().timestamp()).replace('.', '')
    }
    config.db.files.insert_one(info_dict)
    info_dict = await users_middlewares.delete_object_ids_from_dict(info_dict)
    return info_dict


@router.post("/add_info")
async def add_file_info(data: ItemAddFileInfo, response: Response,
                        current_user: User = Depends(users_middlewares.get_current_active_user)):
    if current_user.company_id is None:
        raise HTTPException(status_code=400, detail="No company is attached")
    await users_middlewares.refresh_token(response, current_user.id)
    item_updated = dict()
    file_id = data.file_id
    for elem in data:
        if elem[0] != 'file_id':
            item_updated[str(elem[0])] = elem[1]
    item_updated["recent_change"] = str(datetime.datetime.now().timestamp()).replace('.', '')
    obj = config.db.files.find_one_and_update({'_id': ObjectId(file_id)},
                                              {'$set': item_updated}, return_document=ReturnDocument.AFTER)
    if obj is not None:
        obj = await users_middlewares.delete_object_ids_from_dict(obj)
        return obj
    raise HTTPException(status_code=400, detail='No such Object_id was found')


@router.get("/uploads/cache/{file_name}")
async def get_uploaded_file(file_name):
    try:
        return StreamingResponse(open(f'cache/{file_name}', mode="rb"))

    except FileNotFoundError as e:
        print(e)
        raise HTTPException(status_code=404, detail='file not found')
