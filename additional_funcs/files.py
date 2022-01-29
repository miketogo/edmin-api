from preview_generator.manager import PreviewManager
from fastapi import HTTPException
from bson import ObjectId


async def create_preview(path_to_file):
    try:
        save_path = 'cache'
        manager = PreviewManager(save_path, create_folder=True)
        path_to_preview_image = manager.get_jpeg_preview(path_to_file, page=0, height=1920, width=1920)
        return path_to_preview_image
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail='Could not make a preview')


async def delete_object_ids_from_dict(the_dict: dict):
    for elem in the_dict.keys():
        if isinstance(the_dict[elem], ObjectId):
            the_dict[elem] = str(the_dict[elem])
    return the_dict
