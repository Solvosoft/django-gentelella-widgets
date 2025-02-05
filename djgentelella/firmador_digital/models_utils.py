import datetime
from pathlib import Path

from django.utils.text import slugify


def upload_files(instance, filename):
    date = int(datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    path = Path(filename)
    extension = path.suffix
    name = slugify(path.stem)
    model_name= str(type(instance).__name__).lower()
    return f"{model_name}/{date}/{name}{extension}"
