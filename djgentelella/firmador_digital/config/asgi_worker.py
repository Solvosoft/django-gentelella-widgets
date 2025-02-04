from uvicorn_worker import UvicornWorker as BaseUvicornWorker


class UvicornWorker(BaseUvicornWorker):
    CONFIG_KWARGS = {"lifespan": "off", "loop": "auto", "http": "auto"}
