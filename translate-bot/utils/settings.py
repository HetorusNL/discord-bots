import json
from pathlib import Path


class Settings:
    defaults = {
        "command_prefix": "/",
    }

    @classmethod
    def get(cls, guild_id, setting, default=None):
        settings = cls.load_guild_settings_file(guild_id)

        # try to get the setting from the file
        if settings.get(setting) is not None:
            value = settings.get(setting)
        else:
            # otherwise return default value if provided
            if default:
                value = default
            else:
                # otherwise return the value from defaults
                value = cls.defaults.get(setting, default)

        # print(f"[ Settings.get ] ({guild_id}) {setting}: {value}")
        return value

    @classmethod
    def set(cls, guild_id, setting, value):
        settings = {**cls.defaults, **cls.load_guild_settings_file(guild_id)}
        # print(f"[ Setting.set ] ({guild_id}) {setting}: {value}")
        settings[setting] = value
        cls.store_guild_settings_file(guild_id, settings)

    @classmethod
    def delete(cls, guild_id, setting):
        settings = {**cls.defaults, **cls.load_guild_settings_file(guild_id)}
        # print(f"[ Settings.del ] ({guild_id}) {setting}")
        if setting in settings:
            del settings[setting]
        cls.store_guild_settings_file(guild_id, settings)

    @classmethod
    def load_guild_settings_file(cls, guild_id):
        return cls.load_settings_file(f"guild_data/{guild_id}.json")

    @classmethod
    def store_guild_settings_file(cls, guild_id, settings):
        cls.on_guild_id(guild_id)
        cls.store_settings_file(settings, f"guild_data/{guild_id}.json")

    @classmethod
    def load_settings_file(cls, filename="data/settings.json"):
        try:
            # try to open the settings file with fallback to initial values
            with open(filename) as f:
                settings = json.load(f)
        except:
            print(f"failed to open {filename}, initial values used!")
            settings = {}
            # in case it's the settings.json file, write the default settings file to disk
            if filename == "data/settings.json":
                Path("data").mkdir(exist_ok=True)  # ensure the data directory exists
                with open(filename, "w") as f:
                    json.dump(settings, f)

        return settings

    @classmethod
    def store_settings_file(cls, settings, filename="data/settings.json", defaults=None):
        defaults = cls.defaults if defaults is None else defaults
        with open(filename, "w") as f:
            Path(filename).parent.mkdir(exist_ok=True)  # ensure the directory exists
            json.dump({**defaults, **settings}, f, indent=2)

    @classmethod
    def on_guild_id(cls, guild_id):
        # ensure guild_id exists in the global settings file (lookup purposes)
        settings = cls.load_settings_file()
        if "guilds" not in settings:
            settings["guilds"] = []
        if guild_id not in settings["guilds"]:
            settings["guilds"].append(guild_id)
            cls.store_settings_file(settings, defaults={})
