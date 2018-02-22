#!/usr/bin/python

'''
application object and main UI helper classes
'''
import os, sys, time, string, traceback

# this cruft here was used to find modules imported from non-standard places
# thisdir = os.path.realpath(os.path.split(__file__)[0])
# sys.path = [p for p in sys.path if p == thisdir or not p.startswith('/data/')]
# print(sys.path)

import urwid
from urwidtrees.widgets import TreeBox
from urwidtrees.tree import Tree
from urwidtrees.decoration import CollapsibleIndentedTree as DecoratedTree
from urwid.util import is_wide_char

from urwidtools import dialog, application, widgets
from hub import hub
from config import config

class MyTreeBox(TreeBox):

    max_history = 20

    exposed = '''
              toggle_view
              toggle_refs
              edit_item
              history_back
              history_forward
              goto_clipboard
              goto_references
              goto_search
              goto_trash
              focus_element
              '''

    def __init__(self, dtree, *a, **kw):
        '''
        get hold of that blasted directory tree manually.

        also, export nicely wrapped methods to broker, so that they can also be
        invoked from within dialogs without much trouble.
        '''
        self._dtree = dtree
        self.current_focus_element = None
        self.last_mouse_press = -3600

        self.__super.__init__(*a, **kw)

        # let uth keep the nodes we visit in history.
        # if we do go back in history, let us put the nodes
        # to the 'right' into the future.
        #
        # visited nodes are the ones we actually do work on, such
        # as viewing details. Does this include viewing folders?
        self._history = []
        self._future = []

        for key in self.exposed.strip().split():
            hub.register(key, getattr(self, key))


    def delete_from_history(self, node):
        '''
        nodes can be deleted from the database, or also
        revisited de-novo, in which case we want to
        clear out their previous occurrences.
        '''
        self._history = [ n for n in self._history if n != node ]


    def add_to_history(self, node=None):
        '''
        add a 'new' node to history. node defaults to current one.

        what ch-appens if node is already in history? I suppose we
        flush all previous instances from the history.

        Should we just limit history to references alone? What activity
        on folders would qualify?

        what about deleted nodes? moved ones?

        Well it seems this might get messy very quickly.

        Where do we actually invoke this? Is there one consistent location
        that makes sense? Probably closer to the database than the UI, since
        the same actions may be invoked through menus and key-presses.
        '''
        if node is None:    # invocation from menu will trigger this case
            node = self.focus_element()

        if self._history and self._history[-1] == node:
            return

        self.delete_from_history(node)

        self._history.append(node)
        self._history = self._history[-self.max_history:]

        # I guess if we also need to reset the future.
        self._future = []


    def add_to_future(self, node):
        '''
        newly created item copies are appended here.
        '''
        assert len(self._future) == 0
        self._future.append(node)


    def history_back(self, node=None):
        '''
        invoked by a special key. I guess we have to cases:
        - we have navigated away from the key that was last stored
        - we just have closed some dialog that caused some node to
          be added to the history, but we have not yet navigated
          away.
        '''
        if node is None:    # invocation from menu will trigger this case
            node = self.focus_element()

        if not self._history:
            return

        if len(self._history) > 1 and node == self._history[-1]:
            self._future.append(self._history.pop())

        # now, the last node in _history should be the right one
        self.set_focus(self._history[-1])


    def history_forward(self, node=None):
        '''
        OK, so what happens here? why do I need to press twice?
        '''
        if node is None:    # invocation from menu will trigger this case
            node = self.focus_element()

        if not self._future:
            return

        self._history.append(self._future.pop())
        self.set_focus(self._history[-1])


    def _goto(self, node_name):
        '''
        implement shortcuts to navigate to special nodes
        '''
        node = hub.get_named_node(node_name)
        if node is not None:
            self.set_focus(node)

    def goto_clipboard(self):
        self._goto('Clipboard')

    def goto_references(self):
        self._goto('References')

    def goto_search(self):
        self._goto('Search')

    def goto_trash(self):
        self._goto('Trash')

    def focus_element(self):
        '''
        thin wrapper for general consumption
        '''
        w, focus_element = self.get_focus()
        return focus_element


    def toggle_view(self):
        """
        Collapse currently focussed position; works only if the underlying
        tree allows it.
        """
        focus_element = self.focus_element()

        if hub.is_ref(focus_element):
            hub.ref_view()
        else:
            self._tree.toggle_collapsed(focus_element)
            self.refresh()


    def edit_item(self):
        '''
        open edid dialog for reference or branch
        '''
        w, focus_element = self.get_focus()

        if hub.is_ref(focus_element):
            hub.ref_edit()
        else:
            hub.branch_edit()


    def set_focus(self, node):
        '''
        expand all nodes above the one we are focusing on,
        so that we may get rid of this confusing fold-on-leave
        '''
        parents = hub.get_nodes_above(node)

        for p in parents:
            self._tree.expand(p)
        super(MyTreeBox, self).set_focus(node)


    def toggle_refs(self):
        '''
        show/hide refs within the tree
        '''
        node = self.focus_element()
        branch = node if hub.is_branch(node) else hub.get_parent_node(node)
        hub.toggle_branches_only()
        self.refresh()
        try:
            self.set_focus(branch)
        except: # strange things happen if we press F3 immediately after program start
            pass


    def jump_letter(self, letter):
        '''
        jump among siblings by first letter. keep all of these jumped-to
        references in the history.
        '''
        tree = self._dtree
        get_text = hub.get_node_text

        current = self.focus_element()
        self.add_to_history(current)

        siblings = tree._get_siblings(current)

        next_index = siblings.index(current) + 1
        rotated_siblings = siblings[next_index:] + siblings[:next_index]

        for sibling in rotated_siblings:
            key, title = get_text(sibling)
            if key.lower().startswith(letter):
                self.set_focus(sibling)
                self.add_to_history(sibling)
                break


    def keypress(self, size, key):
        assert type(key) is str

        if not hub.process_action_key(key):
            if key in string.ascii_lowercase:
                self.jump_letter(key)
                return None
            try:
                key = self.__super.keypress(size, key)
            except:
                key = self._outer_list.keypress(size, None)

            return key


    def mouse_event(self, size, event, button, col, row, focus):
        '''
        let double click on focus element open context menu
        '''
        self.__super.mouse_event(size, event, button, col, row, focus)
        size = hub.app.get_screen_size()

        if event == 'mouse press' and button == 1:
            old_focus_element = self.current_focus_element
            self.current_focus_element = self.focus_element()

            old_last_mouse_press = self.last_mouse_press
            self.last_mouse_press = time.time()

            if self.last_mouse_press - old_last_mouse_press < 0.3 and old_focus_element == self.current_focus_element:
                hub.show_menu()

        elif button == 4:
            self.__super.keypress(size, 'up')
        elif button == 5:
            self.__super.keypress(size, 'down')


class ReferenceDisplay(widgets.FocusableTwoColumn):
    '''
    tweak the geometry here
    '''
    label_width = 22
    max_width = 70


class DbTree(Tree):
    '''
    a tree class that displays the reference database as presented by coredb
    '''
    root = "Stuff" # seems to be needed but never shows up.

    def __init__(self, *a, **kw):
        self.debug = debug
        super(DbTree, self).__init__(*a, **kw)


    def __getitem__(self, pos):
        '''
        obtain one tree item for display. Must check back with the database
        to look for updates.
        '''
        text_tuple, selected = hub.get_node_display_info(pos)
        key, title = text_tuple

        if selected == 0:
            low, high = 'body', 'focus'
        elif selected == hub.SELECTED:
            low, high = 'selected body', 'selected focus'
        else:
            low, high = 'in selection body', 'in selection focus'

        nodeinfo = str(pos) if self.debug else ''

        if title is None or hub.is_branch(pos):
            return widgets.FocusableText(key + nodeinfo, low, high)
        else:
            widget = urwid.Pile([ReferenceDisplay(key, nodeinfo + title, low, high), urwid.Divider()])
            return widget


    def _get_siblings(self, pos):
        """
        lists the parent directory of pos
        """
        parent = hub.get_parent_node(pos)

        if parent is None:
            return [pos]

        return hub.get_child_nodes(parent)


    # Tree API
    def parent_position(self, pos):
        return hub.get_parent_node(pos)


    def first_child_position(self, pos):
        '''
        return first child if present, else None
        '''
        children = hub.get_child_nodes(pos)
        return None if not children else children[0]


    def is_leaf(self, pos):
        """checks if given position has no children"""
        return self.first_child_position(pos) is None


    def last_child_position(self, pos):
        '''
        return last child if present, else None
        '''
        children = hub.get_child_nodes(pos)
        return None if not children else children[-1]


    def _sibling_pos(self, pos, siblings):
        '''
        shared code for next_sibling_position and prev_sibling_position

        hack around the problem of object identity
        '''
        return siblings.index(pos)


    def next_sibling_position(self, pos):
        '''
        where is this actually used?
        '''
        siblings = self._get_siblings(pos)
        try:
            myindex = siblings.index(pos)
            #hub.app.set_status(str(siblings[0]))
        except ValueError:
            return None

        if myindex + 1 < len(siblings):  # pos is not the last entry
            return siblings[myindex + 1]
        return None


    def prev_sibling_position(self, pos):
        siblings = self._get_siblings(pos)
        try:
            myindex = siblings.index(pos)
        except ValueError:
            return None

        if myindex > 0:  # pos is not the first entry
            return siblings[myindex - 1]
        return None


class BibApp(application.Application):

    palette = []

    # read color palette from config file
    for key, value in config['palette'].items():
        fg, bg = value.split(',')
        palette.append((key, fg.strip(), bg.strip()))


    def at_begin_loop(self):
        '''
        process startup options
        '''
        if config['preferences'].getboolean('clear_imports'):
            hub.clear_recent()

        if config['preferences'].getboolean('clear_selections'):
            hub.deselect_all()


    def unhandled_input(self, k):
        pass

    def exit_application(self):
        raise urwid.ExitMainLoop()

    def get_root_widget(self):
        dtree = DbTree()

        # We hide the usual arrow tip and use a customized collapse-icon.
        conf = config['preferences']

        decorated_tree = DecoratedTree(
                                dtree,
                                is_collapsed=lambda pos: dtree.depth(pos) >= conf.getint('open_level'),
                                arrow_tip_char=None,
                                icon_frame_left_char=None,
                                icon_frame_right_char=None,
                                icon_collapsed_char="+",
                                icon_expanded_char="-",
                        )

        # stick it into a TreeBox and use 'body' color attribute for gaps
        self.tree = MyTreeBox(dtree, decorated_tree)
        wrapped_tree = urwid.AttrMap(self.tree, 'body') # this simply colors the background
        #add a text footer

        left_bottom = urwid.Text(' Press %s for help, %s to quit' \
                      % (hub.keys['show_help'], hub.keys['exit']))
        self._status = urwid.Text('', align='right')
        cols = urwid.Columns([left_bottom, self._status])

        footer = urwid.AttrMap(cols, 'footer')
        #enclose all in a frame
        root_widget = urwid.Frame(wrapped_tree, footer=footer)
        return root_widget


    def refresh(self):
        '''
        with updating references, this works only as long as we DON'T clear
        the cache.

        The cache gets populated only by get_child_nodes and get_parent in refdb,
        so I guess that neither of these gets invoked when we simply close the
        dialog and call refresh. That means __getitem__ needs to work harder
        to retrieve a missing entry from the database.
        '''
        self.tree.refresh()


    def set_status(self, *args):
        '''
        use the status bar to display update information.
        '''
        args = [str(arg).strip() for arg in args]
        msg = " ".join(args) + " "
        self._status.set_text(msg)
        hub.app.refresh_screen()


if __name__ == "__main__":

    debug = False # currently not enabled - would have to go into bash script
    batch_arg = os.environ.get('mbib_batch', None)

    # print("batch_arg", batch_arg)

    if batch_arg is None:
        _app = BibApp()
        hub.register('app', _app)
        hub.register('tree', _app.tree)
        hub.register('exit', _app.exit)
        hub.app()
    else:
        from batchmode import BatchMode
        BatchMode([batch_arg])()


