'''
this defines the context menus for folders and references.
'''
import urwid, pprint, time
from urwidtools import dialog, widgets, application

from hub import hub
from utils import pubmed_search_url, xclip
from config import config

class ResetStatusMixin(object):
    '''
    let dialogs erase the previous status line upon opening
    '''
    def setup(self):
        hub.app.set_status("")
        super(ResetStatusMixin, self).setup()

class SelectionMenu(ResetStatusMixin, dialog.Menu):
    '''
    a menu with actions to perform on selected items. similar to
    BibMenu, but just different enough to deserve its own class.
    '''
    # outer_height = 12 this is dynamically determined in .setup
    outer_width = 60

    #    ref_details = ('toggle_view', 'Show details', 's'),
    choices = [
        ('cite_selected_oo', 'Cite in OpenOffice', 'o'),
        ('cite_selected_latex', 'Cite in TexStudio or Texmaker', 'l'),
        ('xclip_selected', 'Copy selected bibtex keys to X clipboard'),
        None,
        ('html_selected', 'Export selected references to HTML','h'),
        ('bibtex_selected', 'Export selected references to BibTex','b'),
        None,
        ('mail_selected','Email PDF files of selected references', 'm'),
        ('deselect_all', 'Deselect all selected items', 't'),
        ('confirm_delete_selected', 'Delete all selected items', 'd'),
    ]

    def prevalidate(self):
        return hub.count_selected_items() > 0

    def show_invalid(self):
        hub.show_errors("Nothing has been selected")

    def setup(self):
        super(SelectionMenu, self).setup()

        self.menu_choices = self.choices + [None, ('', 'Cancel', 'Esc')]

        self.title = "Work on selected folders and references"

        # restrict dimensions of menu to contents + padding
        self.outer_height = len(self.menu_choices) + 5

        w = max([len(mc[1]) for mc in [_f for _f in self.menu_choices if _f]] + [len(self.title)])
        self.outer_width = w + 14  # need enough space for shortcuts


    def process_choice(self, button, value):
        '''
        just hand it off to the hub.
        '''
        self.dismiss()

        if value:
            hub.process_action(value)

hub.register('show_selection_menu', lambda *a: SelectionMenu().show())


class BibMenu(ResetStatusMixin, dialog.Menu):
    '''
    well, I can see this growing quickly - with special cases for files, folders, and special folders ...
    '''
    # outer_height = 12 this is dynamically determined in .setup
    outer_width = 60

    # context menus differ for refs and folders, as well as by special folders.
    # the applicable menu is configured using nested dicts. None inserts a menu
    # separator.
    # We try to keep things consistent by defining some standard items first.

    _items = dict(
        ref_details = ('toggle_view', 'Show details', 's'),
        ref_edit = ('edit_item', 'Edit details', 'e'),
        ref_pdf = ('show_pdf', 'Show PDF file', 'p'),
        ref_delete = ('confirm_delete', 'Delete from this folder', 'd'),
        ref_delete_others = ('confirm_delete_others', 'Delete from other folders', 'k'),
        ref_erase = ('confirm_erase', 'Delete from all folders', 'r'),
        ref_oocite = ('oo_cite', 'Cite in OpenOffice', 'o'),
        #
        branch_details = ('toggle_view', 'Expand/collapse', 'x'),
        branch_new_ref = ('create_ref', 'Add new reference', 'r'),
        branch_new_folder = ('create_folder', 'Add sub-folder', 'f'),
        branch_pubmed = ('pubmed_input', 'Import references from Pubmed', 'm'),
        branch_bibimport = ('bibtex_input', 'Import references from BibTex', 'p'),
        branch_doi = ('doi_input', 'Import references from DOI', 'i'),
        branch_bibtex = ('bibtex_filename', 'Export to BibTex', 'b'),
        branch_html = ('html_filename', 'Export to HTML file', 'h'),
        branch_select = ('select_refs', 'Select references in folder', 'l'),
        # branch_recurse = ('select_recursively', 'Select references in folder and sub-folders', 'u'),
        branch_copy = ('copy_selected', 'Copy selected items here', 'c'),
        branch_move = ('move_selected', 'Move selected items here', 'v'),
        branch_flatten = ('confirm_flatten', 'Flatten folder', 't'),
        branch_delete_others = ('confirm_delete_others', 'Delete references from other folders', 'k'),
        branch_rename = ('edit_item', 'Rename folder', 'n'),
        branch_delete = ('confirm_delete', 'Delete folder', 'd'),
        #
        # branch_deselect = ('deselect_all', 'Deselect all folders and references','t'), # h for hide.
        branch_cite_ref = ('cite_key_input', 'Cite in OpenOffice', 'o'),
        #
        search_new = ('new_search', 'New search', 's'),
        search_edit = ('edit_search', 'Edit last search', 'e'),
        search_clear = ('reset_search', 'Reset search', 'r'),
        #
        trash_empty = ('empty_trash', 'Empty Trash', 'y'),
        trash_recycle = ('recycle_trash', 'Recycle Trash', 'z'),
        #
        recycled_empty = ('empty_recycled', 'Delete all', 'd'),
        #
        recently_clear = ('clear_recent', 'Remove all items', 'r'),
    )


    menus = {
        'ref' : {
            'default' : (
                _items['ref_details'],
                _items['ref_edit'],
                None,
                _items['ref_oocite'],
                _items['ref_pdf'],
                None,
                _items['ref_delete'],
                _items['ref_delete_others'],
                _items['ref_erase']
            ),
            'in_trash' : (
                _items['ref_details'],
                _items['ref_pdf'],
            ),
            #
            'in_recycled' : (
                _items['ref_details'],
                _items['ref_edit'],
                None,
                _items['ref_oocite'],
                _items['ref_pdf'],
                None,
                _items['ref_delete']
            ),
            #
            'in_search' :( # deleting a ref from a search result makes little sense.
                _items['ref_details'],
                _items['ref_edit'],
                None,
                _items['ref_oocite'],
                _items['ref_pdf'],
                None,
                _items['ref_erase']
            ),
        },
        #
        'branch' : {
            'default' : (
                _items['branch_details'],
                None,
                _items['branch_new_ref'],
                _items['branch_new_folder'],
                None,
                _items['branch_pubmed'],
                _items['branch_doi'],
                _items['branch_bibimport'],
                None,
                _items['branch_bibtex'],
                _items['branch_html'],
                None,
                _items['branch_select'],
                _items['branch_copy'],
                _items['branch_move'],
                None,
                _items['branch_delete_others'],
                _items['branch_delete'],
                _items['branch_flatten'],
                _items['branch_rename'],
            ),
            #
        'all' : (
                _items['branch_details'],
            ),
            #
        'recently added' : (
                 _items['branch_details'],
                 _items['recently_clear'],
            ),
            #
        'references' : (
                _items['branch_details'],
                _items['branch_new_folder'],
                _items['branch_move'],
                _items['branch_bibtex'],
                _items['branch_html'],
            ),
            #
        'search' : (
                _items['branch_details'],
                _items['branch_select'],
                None,
                _items['search_new'],
                _items['search_edit'],
                _items['search_clear']
            ),
            #
        'trash' : (
                _items['branch_details'],
                _items['trash_empty'],
                _items['trash_recycle']
            ),
            #
        'recycled' : (
                _items['branch_details'],
                _items['branch_select'],
                _items['recycled_empty'],
            ),
         }
    }


    def setup(self):
        super(BibMenu, self).setup()

        self.node = hub.tree.focus_element()

        # work out which menu options to present. we have a dict with
        # two layers; I guess we leave it to refdb to work out the
        # location.

        a, b = hub.get_menu_keys(self.node)
        choices = self.menus[a][b]
        self.menu_choices = [c for c in choices if c is None or hub.uno or c[0] != 'oo_cite']
        self.menu_choices += [None, ('', 'Cancel', 'Esc')]

        self.title = "Work on %s" % hub.node_short_info(self.node)

        # restrict dimensions of menu to contents + padding
        self.outer_height = len(self.menu_choices) + 5

        w = max([len(mc[1]) for mc in [_f for _f in self.menu_choices if _f]] + [len(self.title)])
        self.outer_width = w + 14  # need enough space for shortcuts


    def process_choice(self, button, value):
        '''
        just hand it off to the hub.
        '''
        self.dismiss()

        if value:
            hub.process_action(value)

hub.register('show_menu', lambda *a: BibMenu().show())


class RefEditBase(ResetStatusMixin, dialog.DialogWithLabels):
    '''
    base class for RefEdit and RefAdd. They can't very well inherit from each other
    because their __init__ methods conflict.
    '''
    inner_height = 20
    outer_height = inner_height + 7

    inner_width = 66
    outer_width = inner_width + 7

    title = "Edit reference"

    show_all = True  # show both empty and populated fields

    # listbox_class = dialog.DismissOnKey('f4') not a good idea - it is
    # better to have to cancel or accept explicitly.
    focus_part = 'body'

    sequence = """
               bibtexkey
               reftype
               title
               keywords
               comment
               author
               institution
               journal
               volume
               number
               pages
               booktitle
               editor
               publisher
               url
               doi
               pmid
               year
               purpose
               abstract
               """

    sequence = sequence.strip().split()
    label_width = max([len(s) for s in sequence])

    url_types = dict(
                  url = "%s",
                  doi = "http://dx.doi.org/%s",
                  pmid = "https://www.ncbi.nlm.nih.gov/pubmed/%s"
                )

    def value_widget(self, value):
        '''
        make widget for value overrideable
        '''
        return urwid.AttrWrap(urwid.Edit("", str(value)), 'body', 'editing')


    def url_widget(self, key, value):
        '''
        hook for making url into a button. by default, we don't.
        '''
        return self.value_widget(value)


    def cross_list(self):
        '''
        hook for RefView
        '''
        return []


    def make_widgets(self):

        pairs = [('bibtexkey', self.stored_data.get('bibtexkey',''))]
        pairs.extend(self.cross_list())

        for key in self.sequence[1:]:
            value = self.stored_data.get(key, '')

            if self.show_all or value or key == 'pmid':
                pairs.append((key, value))

        for i, pair in enumerate(pairs):
            if len(pair) == 2:
                key, value = pair
                title = key
            else:
                key, value, title = pair

            if key in self.url_types:
                widget = self.url_widget(key, value)
            elif key == 'crosslist':
                widget = value # we can implement right then and there.
            else:
                widget = self.value_widget(value)

            self.set_widget(key, widget, title)

            if i+1 < len(pairs):
                self.add_divider()


class RefEdit(RefEditBase):

    xclip_key = hub.keys['xclip_selected'] #  "meta x"  # I guess this could also be made configurable

    def __init__(self, errors, *a, **kw):
        self.messages = errors
        self.__super.__init__(*a, **kw)

    def setup(self):
        self.__super.setup()
        self.reference = hub.tree.focus_element()
        self.stored_data = hub.get_ref_dict(self.reference)

    def process(self):
        '''
        read out any changed data and send them off for processing.
        '''
        hub.update_reference(self.stored_data, self.get_data())

    def keypress(self, size, key):

        if hub.mogrify_key(key) == self.xclip_key:
            f = self.focused_widget()

            for attr in 'edit_text', 'text', 'label': # label is for buttons - not sure if text is used at all
                value = getattr(f, attr, None)
                if value is not None:
                    break
            else:
                value = str(f)

            if value is not None:
                xclip(value)

            return None

        return self.__super.keypress(size, key)


hub.register('ref_edit', lambda errors=None, *a, **kw: RefEdit(errors, *a, **kw).show())


class RefAdd(RefEditBase):
    '''
    I'm wondering about the processing sequence here. Can we, without excessive contortions,
    just keep the dialog open until all errors are dealt with? Or maybe rather, not discard the
    data and redisplay the dialog.

    The question is how do we do that without recursion? We shouldn't show the dialog
    within a dialog.

    We really need some simple means for getting a simple bit of data from the user.
    '''
    stored_data = {} # dummy

    def prevalidate(self):
        '''
        make sure we are in the right kind of folder
        '''
        node = hub.tree.focus_element()
        return hub.is_branch(node) and node[1] not in hub.coredb.special_branch_ids

    def show_invalid(self):
        hub.show_errors("'Create reference' is not available here")

    def setup(self):
        self.__super.setup()
        self.node = hub.tree.focus_element()
        self.title = "Add reference to folder '%s'" % hub.get_branch_title(self.node)


    def process(self):
        '''
        read out any changed data and send them off for processing.
        '''
        hub.add_reference(self.get_data(), self.node)


hub.register('create_ref', lambda *a, **kw: RefAdd(*a, **kw).show())


class RefView(RefEdit):
    title = "View reference"

    show_all = False  # hide empty fields
    messages = ['you foobared', 'try again']
    focus_part = 'body'

    def value_widget(self, value):
        return urwid.Text(str(value))

    def process(self):
        '''
        just clobber it
        '''
        pass

    def cross_list(self):
        '''
        OK, so that works basically. Now, the idea is
        - to return 'crosslist' as the key, which will trigger insertion
        - of a button created right here and passed back as 'value'
        - title should be blank except for the firs field.
        '''
        # return [('howdi', 'rowdi', "shtuff")]

        branches = self.stored_data['branches']
        rv = []

        for i, branch in enumerate(branches):
            title = "also in" if i == 0 else ""
            button = widgets.PlainButton(branch['name'], self.show_other, branch)
            wb = urwid.AttrWrap(button, 'body', 'dimfocus')
            rv.append(('crosslist', wb, title))

        return rv

    def show_other(self, *args):
        # hub.show_info(str(args))
        branch_data = args[-1]
        #other_folder = (hub.BRANCH, branch_data['branch_id'], branch_data['parent_id'])
        #hub.tree.set_focus(other_folder)
        other = (hub.REF, branch_data['ref_id'], branch_data['branch_id'])
        hub.tree.set_focus(other)
        self.dismiss()

    def url_widget(self, key, value):
        '''
        make a button that will open the url in a browser. Him. Can we apply this to
        both pmid and doi? Doththithtwork?
        '''
        if value:
            url = self.url_types[key] % value

        elif key == 'pmid':  # this should be the only other allowed case
            value = "search"
            url = pubmed_search_url(self.stored_data)

        btn = widgets.PlainButton(value, self.show_url)
        btn.url = url

        return urwid.AttrWrap(btn, 'body', 'dimfocus')

    def pubmed_search_widget(self):
        '''
        take some of the stored data and take user to pubmed with prefilled search
        '''
        btn = widgets.PlainButton("search", self.show_url)
        btn.url = "https://www.ncbi.nlm.nih.gov/pubmed/"

        return urwid.AttrWrap(btn, 'body', 'dimfocus')


    def show_url(self, button):
        import webbrowser
        webbrowser.open(button.url)

    def add_exit_buttons(self):
        pass


hub.register('ref_view', lambda errors=None, *a, **kw: RefView(errors, *a, **kw).show())


class BranchEdit(dialog.SimpleEdit):
    '''
    we can keep this simple.
    '''
    title_prefix = "Rename folder"
    prompt = "New name:"
    label_width = len(prompt)

    def setup(self):
        self.__super.setup()
        self.node = hub.tree.focus_element()
        self.current_name, weg = hub.get_node_text(self.node)
        self.title = "%s '%s'" % (self.title_prefix, self.current_name)

    def prevalidate(self):
        '''
        make sure we are in the right kind of folder
        '''
        node = hub.tree.focus_element()
        return hub.is_branch(node) and node[1] not in hub.coredb.special_branch_ids

    def show_invalid(self):
        hub.show_errors('This folder is protected and cannot be renamed')

    def process(self):
        '''
        read out any changed data and send them off for processing.
        '''
        new_name = self.get_edit_text()

        if self.current_name != new_name:
            hub.update_branch(self.node, self.current_name, new_name)

hub.register('branch_edit', lambda *a, **kw: BranchEdit(*a, **kw).show())


class BranchFilter(dialog.SimpleEdit):
    '''
    filter branches recursively. Let's see how well that works ...

    I guess the idea is to filter all branches, top to bottom,
    that match the searched for phrase at any level? Show all
    precursors and descendants of each matching folder?

    Also, how do we deactivate this again?
    '''
    title = "Filter folders by name"
    prompt = "Search string: "

    def process(self):
        hub.filter_folders(self.get_edit_text())

    hub.register('filter_folders_dialog', lambda *a, **kw: BranchFilter(*a, **kw).show())


class BranchAdd(BranchEdit):
    '''
    add one from scratch.
    '''
    title_prefix = "Add sub-folder to"
    edit_prefix = "Sub-folder name: "

    def prevalidate(self):
        '''
        make sure we are in the right kind of folder
        '''
        node = hub.tree.focus_element()
        return hub.is_branch(node) \
               and (node[1] not in hub.coredb.special_branch_ids \
                    or hub.coredb.special_branch_names['References'] == node[1])

    def show_invalid(self):
        hub.show_errors("'Create folder' is not available here")

    def process(self):
        hub.add_folder(self.node, self.get_edit_text())

hub.register('create_folder', lambda *a, **kw: BranchAdd(*a, **kw).show())


class MbibConfirmation(dialog.Confirmation):
    '''
    some boilerplate to allow for more declarative confirmation dialogues
    '''
    confirmation_threshold = 3
    processor_name = "process_node"  # dummy example
    question = "You really want to do this?"

    def make_question(self):
        return self.question

    def show(self):
        '''
        here, we hook in checking against a threshold: if the urgency
        of this confirmation falls below a certain user-configured
        value, then the confirmation dialog is skipped, and the action
        carried out.
        '''
        self.__super.show()
        ct = config['preferences'].getint('confirmation_threshold')

        if ct > self.confirmation_threshold:
            self.dismiss()
            self.process()

    def process(self):
        '''
        invoke the preconfigured processor without arguments
        '''
        method = getattr(hub, self.processor_name)
        method()


class ConfirmDeleteSelected(MbibConfirmation):
    '''
    confirm deletion of selected items
    '''
    processor_name = "delete_selected"
    question = "Delete all selected references and/or folders?"

hub.register('confirm_delete_selected', lambda *a, **kw: ConfirmDeleteSelected(*a, **kw).show())


class NodeConfirmation(MbibConfirmation):
    '''
    some common boiler plate for confirmation dialogs
    '''
    ref_question = "Fries with %s?"
    branch_question = "Ketchup with %s?"

    def setup(self):
        self.__super.setup()
        self.node = hub.tree.focus_element()
        self.node_info = hub.node_short_info(self.node)

    def make_question(self):
        template = self.ref_question if hub.is_ref(self.node) else self.branch_question
        return template % self.node_info

    def process(self):
        '''
        invoke configured processor on current node
        '''
        method = getattr(hub, self.processor_name)
        method(self.node)


class ConfirmDelete(NodeConfirmation):
    processor_name = "delete_node"
    ref_question = "Delete %s from this folder?"
    branch_question = "Delete %s?"

hub.register('confirm_delete', lambda *a, **kw: ConfirmDelete(*a, **kw).show())


class ConfirmDeleteOthers(NodeConfirmation):
    processor_name = "delete_other_instances"
    ref_question = "Delete %s from all other folders?"
    branch_question = "Delete references in %s from all other folders?"

hub.register('confirm_delete_others', lambda *a, **kw: ConfirmDeleteOthers(*a, **kw).show())


class ConfirmErase(NodeConfirmation):
    #outer_height = 13
    processor_name = "erase_node"
    ref_question = "Delete %s from ALL folders?"

hub.register('confirm_erase', lambda *a, **kw: ConfirmErase(*a, **kw).show())

class ConfirmFlatten(NodeConfirmation):
    outer_height = 13
    processor_name="flatten_folder"
    branch_question = "Erase all nested sub-folders and move their references to folder '%s'?"

hub.register('confirm_flatten', lambda *a, **kw: ConfirmFlatten(*a, **kw).show())


class SearchForm(RefAdd):
    '''
    we again just need an empty form; the differences kick in only in downstream.

    I might prune the fields here a little - 'tis just too much, ain't it.
    '''
    title = "Search for references"

    sequence = """
               bibtexkey
               reftype
               purpose
               title
               keywords
               comment
               author
               journal
               year
               abstract
               pmid
               doi
               url
               volume
               number
               pages
               booktitle
               editor
               publisher
               """
    sequence = sequence.strip().split()
    label_width = max([len(s) for s in sequence])

    def setup(self):
        self.__super.setup()
        self.title = "New search"

    def prevalidate(self):
        '''
        search can be accessed from anywhere
        '''
        return True

    def process(self):
        '''
        read out any changed data and send them off for processing.
        '''
        hub.search_references(self.get_data())

hub.register('new_search', lambda *a: SearchForm().show())


class EditSearch(SearchForm):

    def setup(self):
        self.__super.setup()

        stored = hub.saved_search()

        if stored is not None:
            self.stored_data = stored
            self.title = "Edit search"
        else:
            self.title = "New search (no stored search available)"

hub.register('edit_search', lambda *a: EditSearch().show())


class PubmedInput(dialog.SimpleEdit):
    title = "Import from Pubmed"
    prompt = "Paste pmids or give filename:"
    label_width = len(prompt)
    multiline = True

    def setup(self):
        self.__super.setup()
        self.node = hub.tree.focus_element()

    def process(self):
        '''
        read out any changed data and send them off for processing.
        '''
        hub.import_pubmed(self.node, self.get_edit_text())

hub.register('pubmed_input', lambda *a: PubmedInput().show())


class DoiInput(dialog.SimpleEdit):
    title = "Import from DOI"
    prompt = "Paste dois or give filename:"
    label_width = len(prompt)
    multiline = True

    def setup(self):
        self.__super.setup()
        self.node = hub.tree.focus_element()

    def process(self):
        '''
        read out any changed data and send them off for processing.
        '''
        hub.import_doi(self.node, self.get_edit_text())

hub.register('doi_input', lambda *a: DoiInput().show())


class BibtexInput(dialog.SimpleEdit):
    '''
    paste bibtex code for import
    '''
    title = "Import references from BibTex"
    prompt = "paste BibTex or give filename:"
    label_width = len(prompt)
    multiline = True

    outer_width = 70
    outer_height = 30

    def setup(self):
        self.__super.setup()
        self.node = hub.tree.focus_element()

    def process(self):
        '''
        read out any changed data and send them off for processing.
        '''
        hub.import_bibtex(self.node, self.get_edit_text())

hub.register('bibtex_input', lambda *a: BibtexInput().show())


class SelectedToHtml(dialog.SimpleEdit):
    '''
    shove selected references into an HTML file
    '''
    title = "Export selected references to HTML"
    prompt = "File name:"
    label_width = len(prompt)
    multiline = False

    def process(self):
        hub.export_html(file_name=self.get_edit_text())

hub.register('html_selected', lambda *a: SelectedToHtml().show() )


class SelectedToBibtex(dialog.SimpleEdit):
    '''
    shove selected references into an HTML file
    '''
    title = "Export selected references to BibTex"
    prompt = "File name:"
    label_width = len(prompt)
    multiline = False

    def process(self):
        hub.export_bibtex(file_name=self.get_edit_text())

hub.register('bibtex_selected', lambda *a: SelectedToBibtex().show() )


class BibfileInput(dialog.SimpleEdit):
    '''
    just specify a folder name. There seems to be no file browser widget;
    we will simply use os.path.abspath to evaluate the string given here.
    '''
    title = "Export BibTex file"
    prompt = "File name:"
    label_width = len(prompt)
    multiline = False

    def setup(self):
        self.__super.setup()
        self.node = hub.tree.focus_element()
        assert hub.is_branch(self.node)

    def initial_text(self):
        '''
        use the node name as the initial text
        '''
        node_name, weg = hub.get_node_text(self.node)
        return node_name.replace(' ','_') + '.bib'

    def process(self):
        '''
        read out any changed data and send them off for processing.
        '''
        hub.export_bibtex(node=self.node, file_name=self.get_edit_text())

hub.register('bibtex_filename', lambda *a: BibfileInput().show())


class HtmlfileInput(dialog.SimpleEdit):
    '''
    just specify a folder name. There seems to be no file browser widget;
    we will simply use os.path.abspath to evaluate the string given here.
    '''
    title = "Export HTML file"
    prompt = "File name:"
    label_width = len(prompt)
    multiline = False

    def setup(self):
        self.__super.setup()
        self.node = hub.tree.focus_element()
        assert hub.is_branch(self.node)

    def initial_text(self):
        '''
        use the node name as the initial text
        '''
        node_name, weg = hub.get_node_text(self.node)
        return node_name.replace(' ','_') + '.html'

    def process(self):
        '''
        read out any changed data and send them off for processing.
        '''
        hub.export_html(node=self.node, file_name=self.get_edit_text())

hub.register('html_filename', lambda *a: BibfileInput().show())


class CiteInput(dialog.SimpleEdit):
    '''
    shortcut for citing a reference by exact bibtexkey
    we use 'like', however, to make the search case-insensitive.
    '''
    title = "Cite reference in OOo"
    prompt = "BibTeX key:"
    label_width = len(prompt)
    multiline = False

    def process(self):
        hub.cite_by_key(self.get_edit_text())

hub.register('cite_key_input', lambda *a: CiteInput().show())


class PdfInput(dialog.SimpleEdit):
    '''
    shortcut for citing a reference by exact bibtexkey
    we use 'like', however, to make the search case-insensitive.
    '''
    title = "Show a PDF file"
    prompt = "BibTeX key:"
    label_width = len(prompt)
    multiline = False

    def process(self):
        hub.show_pdf_bibtexkey(self.get_edit_text())

hub.register('pdf_key_input', lambda *a: PdfInput().show())


"""
class EditKeywords(dialog.SimpleEdit):
    '''
    retired - simply moving up keywords in the sequence of
    fields does the job.

    edit keywords for highlighted reference. We will just
    pretend that the
    '''
    title = "Edit keywords"
    prompt = "Keywords:"
    label_width = len(prompt)
    multiline = True

    def setup(self):
        self.__super.setup()
        self.reference = hub.tree.focus_element()
        self.stored_data = hub.get_ref_dict(self.reference)
        self.old_keywords = self.stored_data.get('keywords', '')

    def initial_text(self):
        return self.old_keywords.strip()

    def process(self):
        '''
        update keywords
        '''
        new_data = dict(keywords=self.get_edit_text())
        hub.update_reference(self.stored_data, new_data)


hub.register('edit_keywords', lambda *a: EditKeywords().show())
"""


