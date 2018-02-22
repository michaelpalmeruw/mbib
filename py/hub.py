'''
The hub class is instantiated only once. This instance is sort of an
'explicit global namespace' within which other modules register exported
functions or objects.
'''
from collections import OrderedDict
from urwidtools import dialog

from SqliteDB import SqliteDB, IntegrityError
from config import config

class RefdbError(Exception):
    pass

class hub(object):

    BRANCH = 1
    REF = 2
    SELECTED = 1
    IN_SELECTION = 2

    # configure keys, assigned actions, and help strings
    _actions = [
        ('show_help', 'Show/hide this help dialog'),
        ('exit', 'Quit program'),
        ('show_menu', 'Show menu for current folder or reference'),
        ('history_back', 'Go back to previous folder or reference'),
        ('history_forward', 'Go forward again'),
        ('goto_references', 'Go to References folder'),
        ('goto_search', 'Go to Search'),
        ('goto_trash', 'Go to Trash'),
        ('toggle_select', 'Select or deselect current folder or reference'),
        ('show_selection_menu', 'Show menu for selected folders and references'),
        ('deselect_all', 'Deselect all folders and references'),
        ('xclip_selected', 'Copy selected bibtex keys to X clipboard (requires xclip)'),
        ('html_selected', 'Export selected references to HTML'),
        ('cite_selected_latex', 'Cite selected references in TeXstudio or Texmaker'),
        ('cite_selected_oo', 'Cite selected references in OpenOffice'),
        ('cite_key_input', 'Cite a reference in OpenOffice (by typing it in)'),
        ('mail_selected', 'Email PDF files of selected references'),
        ('new_search', 'Search for a reference'),
        ('pdf_key_input', 'Show a PDF file'),
        ('toggle_view', 'Expand/collapse current folder or reference'),
        ('edit_item', 'Edit current folder or reference'),
        ('create_ref', 'Create new reference in current folder'),
        ('create_folder', 'Create new folder in current one'),
        ('confirm_delete', 'Delete current folder or reference'),
        ('toggle_refs', 'Show/hide references'),
        ('filter_folders_dialog', 'Filter folders by name'),
        ('reset_filter_folders', 'Reset folder filter (show all folders)'),
        ('toggle_sort', 'Toggle sorting of references (by year/alphabetical)'),
    ]

    def __init__(self):
        self._registry = {}

        # create key bindings from the config file
        self.actions = OrderedDict()
        self.keys = {} # for reverse lookup

        config_keys = config['keyboard shortcuts']

        for action, comment in self._actions:
            key = config_keys.get(action, None)

            if key is None:
                continue

            key = self.mogrify_key(key)
            self.actions[key] = (action, comment)
            self.keys[action] = key
            # print(action, ':', key)


    def mogrify_key(self, key):
        '''
        urwid key names are case-sensitive. Let's guard a little against
        user case variation.
        '''
        if key == ' ':
            return 'Space'

        if len(key) == 1:
            return key

        frags = key.split()

        if len(frags) == 1:
            return key.title()

        # we can have 'meta', 'ctrl', or 'meta ctrl' prefixes
        morphed = [f.title() for f in frags[:-1]] + [frags[-1]]
        morphed = " ".join(morphed)
        morphed = morphed.replace('Meta ', 'Alt ').replace('Alt Ctrl ', 'Ctrl Alt ')

        return morphed


    def __getattr__(self, att):
        return self._registry[att]

    def register(self, name, obj):
        self._registry[name] = obj

    def register_many(self, namelist, obj):
        for name in namelist:
            self.register(name, getattr(obj, name))

    # some simple methods can be implemented right here; that doesn't hurt anything.
    def show_message(self, message):
        dialog.MessageBox(message).show()


    def process_action(self, action):
        '''
        this is the main entry point for processing function keys and keyboard shortcuts.
        I guess we need to make this context-aware - abort actions that make no sense
        in the given context, such as adding folders to references. How do we do this?

        We already have some sort of context restriction by way of the specialized
        menus in ui. Can we somehow avoid duplicating that? It rather seems to me that
        those declarations would become the duplicate. What we really need is some mapping
        of action to availability context; the menus should dynamically access that mapping
        also, instead of being hand-coded.

        The only alternative seems to be that we disable those dubious shortcuts.
        '''
        try:
            method = getattr(self, action)
        except KeyError:
            self.show_message("action '%s' not implemented" % action)
        else:
            method()


    def process_action_key(self, key):
        '''
        look up a key press on self.actions. if there, execute it. Return success code.
        '''
        key = self.mogrify_key(key)
        action = self.actions.get(key, (None,))[0]

        if action is None:
            return False

        self.process_action(action)
        return True


hub = hub()

# I guess the sequence of imports still matters ... no?
import help4mbib, ui, coredb, selections, trashcan, imex, search, editor_push

try:
    import mbiboo
    hub.uno = True
except ImportError:
    hub.uno = False
    print("uno not found - starting without OpenOffice interaction")
    for key in "oc":
        hub.actions.pop(key)
