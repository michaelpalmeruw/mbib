import os
from configparser import ConfigParser

config_path = os.environ.get("mbib_ini", "~/.mbib.ini")
config_path = os.path.expanduser(config_path)

def read_config():
    config = ConfigParser(
                inline_comment_prefixes = [';','#'],
                allow_no_value = True
            )
    config.read(config_path)
    return config

config = read_config()


if __name__ == '__main__':
    import pprint

    for section in config.sections():
        print("[%s]" % section)
        pprint.pprint(dict(config[section]))
        print()

