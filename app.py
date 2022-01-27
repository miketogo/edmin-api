import asyncio
import datetime

from fastapi import FastAPI, UploadFile, File, Depends
from uvicorn import Config, Server
from pymongo import MongoClient
from middlewares.files import create_preview
from routes.files import ItemUploadFileInfo


client = MongoClient(port=27017)
db = client.edmin


app = FastAPI()


@app.post("/files/upload")
async def create_file(file: UploadFile = File(...), data: ItemUploadFileInfo = Depends(ItemUploadFileInfo.as_form)):
    file_readed = await file.read()
    with open(f'files/{file.filename}', 'wb') as doc:
        doc.write(file_readed)
        file_size = len(file_readed)
    preview_link = await create_preview(f'files/{file.filename}')
    info_dict = {
            "file_name": file.filename,
            "file_content_type": file.content_type,
            "file_size": file_size,
            "preview_link": preview_link,
            "upload_date": (datetime.datetime.now()).strftime("%d.%m.%Y %H:%M:%S"),
            "uploaded_by": data.user_id,
            "company_id": data.company_id
        }
    db.files.insert_one(info_dict)
    new_info_dict = info_dict.copy()
    new_info_dict['_id'] = str(new_info_dict['_id'])
    return new_info_dict


if __name__ == "__main__":
    loop_main = asyncio.new_event_loop()
    config_server = Config(app=app, loop=loop_main, host='localhost', port=3000)
    server = Server(config_server)
    loop_main.run_until_complete(server.serve())
