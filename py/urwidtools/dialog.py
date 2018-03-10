#!/usr/bin/python
# -*- coding: utf-8 -*-

'''
this is from https://www.mail-archive.com/urwid@lists.excess.org/msg00516.html

There seems to be no mechanism for returning the values from the dialog. So
I guess the best we can do is to save the widgets on the dialog, return
the exit code, and leave it up to the user to deal with value retrieval.

This is all a little too prejudiced, I guess.
'''
import urwid, sys, time, string
from urwidtools import application # Grr. I will never understand how relimport works.
from urwidtools.widgets import *


class DialogListBox(urwid.ListBox):
    '''
    insert a hook for key event processing that calls back
    into the Dialog that owns the ListBox instance.
    '''
    def __init__(self, body, dialog_instance):
        self.dialog = dialog_instance
        urwid.ListBox.__init__(self, body)


    def keypress(self, size, key):
        '''
        delegate to dialog. Dialog returns True if processed the key, else False
        '''
        key = self.dialog.keypress(size, key)

        if key is not None:
            return self.__super.keypress(size, key)
        return None


class Dialog(urwid.WidgetWrap):
    # __metaclass__ = urwid.signals.MetaSignals -- as per https://stackoverflow.com/questions/20130631/
    # but seems unnecessary - I guess WidgetWrap already has the necessary bits

    signals = ["exit"]  # this is needed, however.

    title = "Dialog.title"
    messages = []
    message_style = 'error'

    outer_width = 60
    outer_height = 20
    focus_part = 'footer'

    # listbox_class = urwid.ListBox.
    listbox_class = DialogListBox

    # configure key processing.
    dismiss_keys = ['esc']


    def __init__(self, callback=None, width=None, height=None, is_root=False):
        self.setup() # hook
        callback = callback or self._process

        self.is_root = is_root
        self.parent = application.app.get_widget()

        self.width = width or self.outer_width
        self.height = height or self.outer_height

        # I guess we want two containers - one for the widgets that contain
        # actual data, and a second one that holds wrapped widgets for insertion
        # into the dialog's listbox.
        self._display_widgets = []
        self._data_widgets = {}

        self.make_widgets()
        self.listbox = self.make_body_listbox()

        self.frame = TabFrame(self.listbox, focus_part=self.focus_part)

        header_items = [urwid.Text(self.title), urwid.Divider('\u2550')]
        self.title_widget = header_items[0]

        if self.messages:
            for i, msg in enumerate(self.messages):
                header_items.append(urwid.AttrWrap(urwid.Text(msg), self.message_style))
                if i+1 < len(self.messages):
                    header_items.append(urwid.Divider())

        self.frame.header = urwid.Pile(header_items)
        w = self.frame

        # pad area around listbox
        w = urwid.Padding(w, ('fixed left',2), ('fixed right',2))
        w = urwid.Filler(w, ('fixed top',1), ('fixed bottom',1))
        w = urwid.AttrWrap(w, 'body')

        w = urwid.LineBox(w)

        # "shadow" effect
        w = urwid.Columns( [w,('fixed', 1, urwid.AttrWrap(
            urwid.Filler(urwid.Text(('border',' ')), "top") ,'shadow'))])
        w = urwid.Frame( w, footer =
            urwid.AttrWrap(urwid.Text(('border',' ')),'shadow'))

        self.view = w

        if self.is_root:
            # this dialog is the main window
            # create outermost border area
            w = urwid.Padding(w, 'center', self.width )
            w = urwid.Filler(w, 'middle', self.height )
            w = urwid.AttrWrap( w, 'border' )
        else:
            # this dialog is a child window
            # overlay it over the parent window
            # I guess here he we need to fix up the use of the palette
            w = urwid.Overlay(w, self.parent, 'center', self.width+2, 'middle', self.height+2)
            w = urwid.AttrWrap(w, 'border')

        self.view = w

        self.add_exit_buttons()

        # Call WidgetWrap.__init__ to correctly initialize ourselves
        urwid.WidgetWrap.__init__(self, self.view)
        urwid.connect_signal(self, 'exit', callback)

        # set a flag that prevents closing twice
        self._dismissed = False


    def setup(self):
        """
        hook
        """
        pass


    def make_body_listbox(self):
        '''
        hook this out so that we can fiddle with the display properties
        '''
        wrappers = []

        for w in self._display_widgets:
            wrappers.append(urwid.AttrWrap(w, None, 'reveal focus'))

        return self.listbox_class(
                            urwid.SimpleListWalker(wrappers),
                            self # give the listbox a reference to the parent dialog to support keypress handling
                       )

    def set_title(self, new_title):
        '''
        let's see if this worketh
        '''
        self.title_widget.set_text(new_title)


    def append_widget(self, widget):
        '''
        append a widget, without setting an explicit reference to it
        '''
        self._display_widgets.append(widget)


    def set_widget(self, label, widget):
        '''
        in the most simple case, we don't distinguish between
        _widgets and _data_widgets.
        '''
        self._data_widgets[label] = widget
        self.append_widget(widget)


    def add_divider(self, char=' '):
        self.append_widget(urwid.AttrWrap(urwid.Divider(char), 'body'))


    def make_widgets(self):
        '''
        hook with some dummy default implementation
        '''
        self.set_widget("line1", FocusableText("Override .make_widgets"))
        self.set_widget("line2", FocusableText("to add widgets to the dialog"))


    def get_widgets(self):
        '''
        for client code that wants to read out the dialog data
        '''
        return self._data_widgets


    def get_data(self):
        '''
        read out edit widgets, checkboxes, and radiobuttons
        '''
        widgets = self.get_widgets()
        new_data = {}

        for key, widget in list(widgets.items()):
            for attr in 'state', 'edit_text':
                value = getattr(widget, attr, None)

                if value is not None:
                    if isinstance(value, str):
                        value = value.strip()
                    new_data[key] = value
                    continue

        return new_data


    def exit_buttons(self):
        '''
        hook for creating dialog exit buttons.
        again, we need to figure out how to get hold of values.
        '''
        return [ ("Cancel", "cancel"), ("OK", "ok") ]


    def make_button(self, caption, callback, shortcut=None):
        '''
        this seems to be unused - but we should use it.
        '''
        w = MyButton(caption, callback, shortcut)
        w = urwid.AttrWrap(w, 'button normal', 'button select')

        if shortcut is not None:
            assert len(shortcut) == 1
            assert shortcut in string.ascii_lowercase
            assert shortcut not in self._button_shortcuts
            self._button_shortcuts[shortcut] = callback

        return w


    def add_exit_buttons(self):
        '''
        I guess this also needs to be hooked out.
        '''
        buttons = self.exit_buttons()

        l = []

        for b in buttons:
            if len(b) == 2:
                name, exitcode = b
                shortcut = None
            else:
                name, exitcode, shortcut = b
            b = MyButton( name, self.on_exit_button, shortcut=shortcut)
            b.exitcode = exitcode
            b = urwid.AttrWrap( b, 'button normal','button select' )
            l.append( b )

        buttons = urwid.GridFlow(l, 10, 3, 1, 'center')
        self.frame.footer = urwid.Pile( [ urwid.Divider('\u2500'),
                                        buttons ], focus_item = 1)


    def on_exit_button(self, button):
        '''
        invoked by pressing of exit buttons.
        '''
        self.exitcode = button.exitcode

        if  not self.is_root:
            self.dismiss()
            urwid.emit_signal(self, "exit")
        else:
            urwid.emit_signal(self, "exit")
            application.exit()


    def prevalidate(self):
        '''
        hook to check if dialog makes sense in present context
        '''
        return True


    def show_invalid(self):
        '''
        hook for displaying an error message if context is invalid
        '''
        pass


    def show(self):
        if self.prevalidate():
            self._show()
        else:
            self.show_invalid()


    def _show(self):
        '''
        pass the dialog's view to the application
        '''
        application.app.show_widget(self.view)


    def dismiss(self):
        '''
        just close the dialog; neither use nor discard any data.
        '''
        if not self._dismissed:
            application.app.hide_widget(self.view)
            self._dismissed = True


    def _process(self):
        '''
        wrapper that invokes custom .process if dialog was not canceled.
        '''
        if self.exitcode != 'cancel':
            self.process()


    def process(self):
        '''
        pacifier
        '''
        pass


    def keypress(self, size, key):
        '''
        Do we actually need to invoke super.keypress
        here? I don't think so - I don't think it does anything at all.
        Just let ListBox call its own super.
        '''
        if key in self.dismiss_keys: # ok that worked.
            self.dismiss()
            return None
        return key


class DialogWithLabels(Dialog):
    '''
    let's take the pain out of making dialog with labeled widgets.
    '''
    label_width = 15
    min_width = 12
    max_width = 80
    divide_chars = 2

    def setup(self):
        self._widget_map = {}


    def focused_widget(self):
        w = self.listbox.get_focus()[0]

        while hasattr(w, "original_widget"):
            w = w.original_widget

        return self._widget_map[w]


    def set_widget(self, label, widget, title=None):
        '''
        create a text widget for the title, store the
        data widget, and create a wrapper for both.
        '''
        if isinstance(label, str):
            if title is None:
                title = label
            lw = urwid.Text(title)
        elif title is None:
            title = ""

        # tw = urwid.AttrWrap(urwid.Text(title),'body','body') fails with height > 1
        columns = MyColumns(
                      self.label_width,
                      self.max_width,
                      [lw, widget],
                      dividechars = self.divide_chars,
                      focus_column = None,
                      min_width = self.min_width,
                      box_columns = None
                  )
        self._data_widgets[label] = widget
        self._display_widgets.append(urwid.AttrWrap(columns, 'body'))
        self._widget_map[columns] = widget


class MessageBox(Dialog):
    '''
    an innocuous message box. Well, the problem is that it does
    not scroll on overflow.
    '''
    title = r''' \\|//
( @ @ )
 ( ~ )'''
    message_style = 'body'
    focus_part = 'footer'

    outer_width = 50
    outer_height = 20

    def __init__(self, messages, *a, **kw):
        if isinstance(messages, str):
            messages = [messages]
        self.body_messages = messages
        self.__super.__init__(*a, **kw)

    def make_widgets(self):
        for message in self.body_messages:
            self.append_widget(urwid.Text(message))
            self.add_divider()

    def make_body_listbox(self):
        '''
        hook this out so that we can fiddle with the display properties
        '''
        return self.listbox_class(
                            urwid.SimpleListWalker([urwid.AttrWrap(w, self.message_style) for w in self._display_widgets]),
                            self # give the listbox a reference to the parent dialog to support keypress handling
                       )

    def exit_buttons(self):
        return [ ("OK", "ok") ]


class Confirmation(Dialog):
    '''
    is this used anywhere? yes.
    '''
    title = 'Confirm operation'

    outer_width = 50
    outer_height = 10

    def make_widgets(self):
        self.add_divider()
        self.set_widget('question', urwid.Text(self.make_question()))

    def make_question(self):
        return "Fries with that?"


class SimpleEdit(DialogWithLabels):
    '''
    a dialog with a single edit field.
    '''
    title = "SimpleEdit.title"
    prompt = "SimpleEdit.prompt:_"
    multiline = False

    outer_width = 50
    outer_height = 10
    focus_part = 'body'

    def initial_text(self):
        return ''

    def make_widgets(self):
        self.add_divider()
        self.set_widget('edit', urwid.Edit('', self.initial_text(), multiline=self.multiline), self.prompt)

    def get_edit_text(self):
        return self.get_data()['edit'].strip()


class Menu(Dialog):
    '''
    A dialog with a vertical stack of buttons.

    Let us start simple: We offer pairs of keys and labels, and we simply set
    the menu choice as an attribute and exit.
    '''
    focus_part = 'body'

    _firstnames = 'Graham John Terry Eric Terry Michael'.split()
    _labels = 'Chapman Cleese Gilliam Idle Jones Palin'.split()

    menu_choices = list(zip( _firstnames, _labels ))

    def setup(self):
        self.shortcut_keys = {}

    def add_exit_buttons(self):
        pass

    def make_widgets(self):
        '''
        A-haah. We already have an opinionated way to process menu choices.
        We don't configure separate callbacks for buttons, but rather have
        a single callback that receives different arguments.

        Should we adopt this for Dialog also?
        '''
        for item in self.menu_choices:
            if item is None: # foobars.
                self._display_widgets.append(urwid.Divider('\u2500'))
                continue
            if len(item) == 2:
                action, label = item
                shortcut = None
            else:
                action, label, shortcut = item
            button = MyButton(label,shortcut=shortcut)

            urwid.connect_signal(button, 'click', self.process_choice, action)

            if shortcut is not None:
                assert shortcut not in self.shortcut_keys, "shortcut %s already taken" % shortcut
                self.shortcut_keys[shortcut] = action

            self.set_widget(label, urwid.AttrWrap(button, 'body', 'button select'))


    def keypress(self, size, key):
        '''
        process menu shortcuts. For simplicity, we let this take precedence
        over superclass method.
        '''
        action = self.shortcut_keys.get(key, None)

        if action is not None:
            self.process_choice(None, action) # None is a dummy "button" argument

        return super(Menu, self).keypress(size, key)


    def process_choice(self, button, action):
        '''
        why would they pass in the button? Well, maybe for changing its label or something.
        '''
        self.dismiss()
        MessageBox("you chose '%s'" % action).show()


class ProgressBar(Dialog):
    '''
    higher level progress bar widget.

    Over its lifetime, tasks are processed from 0 to target. The display
    goes from initial_percent to final_percent, in steps of interval.
    The client code calls .update to set a new completed value, whereupon
    the widget updates itself if needed.
    '''
    outer_width = 50
    outer_height = 6
    incomplete = 'body'    # palette color for incomplete fraction
    complete = 'focus'     #    ...


    def __init__(self,
                 target,
                 start = 0,
                 title = "working hard for a better future ...",
                 initial_percent = 0,
                 final_percent = 100,
                 interval = 10,
                 **kw):

        self.start = start
        self.target = target
        self.title = title

        self.current_percent = self.initial_percent = initial_percent
        self.final_percent = final_percent
        self.interval = interval

        self.__super.__init__(**kw)
        self.set_title(self.title)


    def make_widgets(self):
        self.set_widget('bar', urwid.ProgressBar(self.incomplete, self.complete, done=self.final_percent))


    def update(self, newcount):
        '''
        calculate the current percentage that should be displayed
        '''
        completed_fraction = 1.0 * (newcount - self.start)/(self.target - self.start)
        total_steps = (self.final_percent - self.initial_percent) / self.interval

        completed_steps = int(completed_fraction * total_steps)
        display_percent = self.initial_percent + completed_steps * self.interval

        if display_percent > self.current_percent:
            self.current_percent = display_percent
            self.set_completion(self.current_percent)

    def set_completion(self, nr):
        bar = self.get_widgets()['bar']
        bar.set_completion(nr)
        application.app.refresh_screen() # is this needed, or is time.sleep enough? No, it's needed

        if nr >= self.final_percent:
            time.sleep(0.25)
            self.dismiss()

    def show(self):
        self.__super.show()
        self.set_completion(self.initial_percent)

    def add_exit_buttons(self):
        pass


'''
here some pilfered stuff that might help us with implementing double clicks
but maybe we should simply treat a click on an already selected element
as a double click. Wouldn't that be simplest? I think so.

def mouse_event(self, size, event, button, col, row, focus):
    # time between the two clicks activating a double click
    DOUBLE_CLICK_TIME = 0.25
    DRAG_PROTECT_TIME = 0.1
    # mouse buttons which can trigger a double click
    DOUBLE_CLICKABLE = [1]

    if event == 'mouse press' and  button in DOUBLE_CLICKABLE:
        last = self.last_click
        now = time.time()

        if button in last:
            delta = now - last[button]

            # check for double click
            if delta > DRAG_PROTECT_TIME and delta < DOUBLE_CLICK_TIME:
                # add the magic offset
                button += 10

        # save current click
        last[button] = now

    urwid.Frame.mouse_event(self, size, event, button, col, row, focus)

'''
