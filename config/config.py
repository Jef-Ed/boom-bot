import yaml

class Config:
    def __init__(self, config_path="config/config.yml"):
        with open(config_path, "r") as file:
            self.config = yaml.safe_load(file)

    def get(self, key, default=None):
        keys = key.split(".")
        value = self.config
        try:
            for k in keys:
                value = value[k]
        except KeyError:
            return default
        return value