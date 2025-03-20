from uvicorn_worker import UvicornWorker as BaseUvicornWorker


class DjgentelellaUvicornWorker(BaseUvicornWorker):
    CONFIG_KWARGS = {"lifespan": "off", "loop": "auto", "http": "auto"}
