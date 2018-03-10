'''
The hub class is instantiated only once. This instance is sort of an
'explicit global namespace' within which other modules register exported
functions or objects.
'''
from collections import OrderedDict
from urwidtools import dialog

from SqliteDB import SqliteDB, IntegrityError
from config import config
from utils import Null        # dummy class that we substitute for
                              # dialog.ProgressBar  when in batch mode

class RefdbError(Exception):
    pass

class hub(object):

    BRANCH = 1
    REF = 2
    SELECTED = 1
    IN_SELECTION = 2

    # configure keys, assigned actions, and help strings. The order of this list
    # will only affect the order of display in the help dialog; the corresponding
    # keyboard shortcuts are assigned in the .ini file.
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
        ('deselect_all', 'Deselect all folders and references'),
        ('xsel_selected', 'Copy selected bibtex keys to X clipboard (requires xsel)'),
        ('bibtex_selected', 'Export selected references to BibTex'),
        ('html_selected', 'Export selected references to HTML'),
        ('cite_selected_latex', 'Cite selected references in TeXstudio or Texmaker'),
        ('cite_selected_oo', 'Cite selected references in OpenOffice'),
        ('cite_key_input', 'Cite a reference in OpenOffice (by typing it in)'),
        ('mail_selected', 'Email PDF files of selected references'),
        ('new_search', 'Search for a reference'),
        ('pdf_key_input', 'Show a PDF file'),
        ('toggle_view', 'Expand/collapse current folder or show current reference'),
        ('edit_item', 'Edit current folder or reference'),
        ('create_ref', 'Create new reference in current folder'),
        ('create_folder', 'Create new folder in current one'),
        ('confirm_delete', 'Delete current folder or reference'),
        ('show_selection_menu', 'Show menu for selected folders and references'),
        ('toggle_sort', 'Toggle sorting of references (alphabetical or by year)'),
        ('toggle_refs', 'Show/hide references'),
        ('filter_folders_dialog', 'Filter folders by name'),
        ('reset_filter_folders', 'Reset folder filter (show all folders)'),
    ]

    def __init__(self):
        self.is_batch = True   #  default - gets switched in mbib.py if not in batch mode
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
        '''
        we disable messages if we are in batch mode, so that
        client code doesn't have to worry
        '''
        if not self.is_batch:
            dialog.MessageBox(message).show()


    def progress_bar(self, target, **kw):
        '''
        supply a proper progressbar when not it batchmode,
        else a do-nothing class instance
        '''
        if self.is_batch:
            return Null()
        else:
            return dialog.ProgressBar(target, **kw)


    def set_status_bar(self, *a, **kw):
        if not self.is_batch:
            self.app.set_status(*a, **kw)


    def process_action(self, action):
        '''
        this is the main entry point for processing function keys and keyboard shortcuts.
        I guess we need to make this context-aware - abort actions that make no sense
        in the given context, such as adding folders to references. How do we do this?

        Update: this is now implemented in the .prevalidate methods of the corresponding
        dialogs in the ui module. The .prevalidate method can look at the tree and decide
        if the currently active item should permit the requested operation. In this manner,
        we can catch requests made through both menus and global keyboard shortcuts.
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

