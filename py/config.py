import os
from configparser import ConfigParser

config_path = os.getenv("mbib_ini", "~/.mbib.ini")
config_path = os.path.expanduser(config_path)

def read_config():
    config = ConfigParser(
                inline_comment_prefixes = [';','#'],
                allow_no_value = True
            )
    config.read(config_path)
    return config

config = read_config()

def expanded_path(key, **kw):
    '''
    expand ~ and {mbib_dir} markers in paths found in config file
    '''
    raw_path = config['paths'][key]     # fail hard if the key is missing
    path = raw_path.format(mbib_dir=os.getenv('mbib_dir'), **kw)
    return os.path.realpath(os.path.expanduser(path))

# print(expanded_path("test", bibtexkey="Hurz2010", knall="peng"))


if __name__ == '__main__':
    import pprint

    for section in config.sections():
        print("[%s]" % section)
        pprint.pprint(dict(config[section]))
        print()

