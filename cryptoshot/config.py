import json

from .exceptions import LoadConfigException
from .types import Config


def get_config(config_path: str) -> Config:
    try:
        with open(config_path, "r") as config_file:
            config: Config = json.load(config_file)

            # TODO: check required fields are valid

            return config
    except Exception as e:
        raise LoadConfigException(e)
