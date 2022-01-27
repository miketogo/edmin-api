from preview_generator.manager import PreviewManager
from fastapi import HTTPException


async def create_preview(path_to_file):
    try:
        save_path = 'cache'
        manager = PreviewManager(save_path, create_folder=True)
        path_to_preview_image = manager.get_jpeg_preview(path_to_file, page=1, height=1920, width=1920)
        return path_to_preview_image
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail='Could not make a preview')
