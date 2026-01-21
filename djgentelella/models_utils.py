import datetime
import logging
import os
from pathlib import Path

from django.utils.text import slugify

logger = logging.getLogger("djgentelella")


def get_file_name(instance, name):
    model_name = str(type(instance).__name__).lower()

    return "%s-%s" % (
        model_name,
        name
    )


def upload_files_by_model_and_dates(instance, filename):
    """
    Create a directory structure of the type model/date/file. Usage:

        myfile = models.FileField(upload_to=upload_files_by_model_and_dates)
    """
    date = int(datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    path = Path(filename)
    extension = path.suffix

    if extension == ".zip":
        name = path.stem
    else:
        name = get_file_name(instance, slugify(path.stem))

    model_name = str(type(instance).__name__).lower()
    return f"{model_name}/{date}/{name}{extension}"


def upload_files_by_model_and_month(instance, filename):
    """
    Create a directory structure of the type model/yearmonth/file. Usage:

        myfile = models.FileField(upload_to=upload_files_by_model_and_dates)
    """
    dates = datetime.datetime.now().strftime("%Y%m")
    path = Path(filename)
    extension = path.suffix

    if extension == ".zip":
        name = path.stem
    else:
        name = get_file_name(instance, slugify(path.stem))

    model_name = str(type(instance).__name__).lower()
    return f"{model_name}/{dates}/{name}{extension}"


def delete_file_and_folder(file_field):
    """
        Delete the file associated with file_field and, if the containing folder is empty,
        delete it.
    """
    if not file_field:
        return

    # Obtener la ruta absoluta del archivo
    file_path = file_field.path
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info(f"Deleted file: {file_path}")
        except Exception as e:
            logger.error(f"Error deleting file: {file_path}", exc_info=e)

    # Obtener la carpeta contenedora del archivo
    directory = os.path.dirname(file_path)

    # Intentar eliminar la carpeta, si está vacía.
    if os.path.exists(directory):
        # Listar el contenido de la carpeta
        files = os.listdir(directory)
        if not files:
            try:
                os.rmdir(directory)
                logger.info(f"Folder created: {directory}")
            except Exception as e:
                logger.error(f"Error deleting folder: {directory}", exc_info=e)
