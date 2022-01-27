from preview_generator.manager import PreviewManager

cache_path = 'cache'
pdf_or_odt_to_preview_path = 'files/Договор 9301 2021 22.11.2021.docx (1).pdf'

manager = PreviewManager(cache_path, create_folder=True)
path_to_preview_image = manager.get_jpeg_preview(pdf_or_odt_to_preview_path, page=1, height=1920, width=1920)

print(path_to_preview_image)