import json

from .exceptions import LoadConfigException
from .types import Config


def load_config(config_path: str) -> Config:
    try:
        with open(config_path, "r") as config_file:
            config: Config = json.load(config_file)

            # TODO: check required fields are valid

            return config
    except (OSError, json.JSONDecodeError) as e:
        raise LoadConfigException(e)
