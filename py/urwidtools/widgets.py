'''
some wrapped or decorated widgets pilfered from here, there, and everywhere.

urwid contains a class IntEdit, which allows only integers as input. The
implementation looks as if it can easily be adapted to other restrictions:

class IntEdit(Edit):
    """Edit widget for integer values"""

    def valid_char(self, ch):
        """
        Return true for decimal digits.
        """
        return len(ch)==1 and ch in "0123456789"

We could use this to restrict characters allowed in bibtex identifiers.
We should probably implement some such restriction across all our code.
I think a good rule is to allow only letters, digits, and reasonable
punctuation such as _-:!

Class Edit actually has its own non-trivial valid_char method, so we should
start from that one. Probably call it first and then apply further restrictions.
'''

import urwid, curses


class ButtonLabel(urwid.SelectableIcon):
    '''
    move cursor out of view, or if applicable use cursor
    to highlight keyboard shortcut.
    '''
    def set_text(self, label):
        self._cursor_position = len(label) + 1
        self.__super.set_text(label)


class MyButton(urwid.Button):
    '''
    - override __init__ to use ButtonLabel instead of urwid.SelectableIcon

    - make button_left and button_right plain strings and variable width -
    any string, including an empty string, can be set and displayed

    - otherwise, we leave Button behaviour unchanged

    Ha,ha. We could actually abuse the cursor to highlight the applicable
    keyboard shortcut. Wouldn't that be cute?
    '''
    button_left =  "["
    button_right = "]"

    def __init__(self, label, on_press=None, user_data=None, shortcut=None):
        self._label = ButtonLabel("")

        cols = urwid.Columns([
            ('fixed', len(self.button_left), urwid.Text(self.button_left)),
            self._label,
            ('fixed', len(self.button_right), urwid.Text(self.button_right))],
            dividechars=1)
        super(urwid.Button, self).__init__(cols)

        if on_press:
            urwid.connect_signal(self, 'click', on_press, user_data)

        if shortcut is not None:
            label = "%s (%s)" % (label, shortcut)

        self.set_label(label)


class PlainButton(MyButton):
    button_left = button_right = ""


class FocusableText(urwid.WidgetWrap):
    '''
    A plain text widget that can acquire the focus when
    displayed in a listbox or tree
    '''
    low = 'body'
    high = 'focus'

    def __init__(self, txt, low=None, high=None):
        t = urwid.Text(str(txt))
        low = low or self.low
        high = high or self.high
        w = urwid.AttrMap(t, low, high)
        urwid.WidgetWrap.__init__(self, w)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class MyColumns(urwid.Columns):
    '''
    specify the width of the first column, which
    will contain the labels.
    '''
    def __init__(self, first_width, max_width, *a, **kw):
        self.first = first_width
        self.max_width = max_width
        self.__super.__init__(*a, **kw)

    def column_widths(self, size, focus=False):
        widths = urwid.Columns.column_widths(self, size, focus)
        total = sum(widths)
        return [self.first, min(self.max_width, total-self.first)] # widths


class FocusableTwoColumn(urwid.WidgetWrap):
    '''
    two text widgets in columns and selectable. add some padding as well.
    '''
    label_width = 24
    divide_chars = 2
    min_width = 20
    max_width = 80
    padding_left = 0
    padding_right = 3

    def __init__(self, left, right, low='body', high='focus'):

        columns = MyColumns(
                      self.label_width,
                      self.max_width,
                      [urwid.Text(left), urwid.Text(right)],
                      dividechars=self.divide_chars,
                      focus_column=None,
                      min_width=self.min_width,
                      box_columns=None
                  )
        wrapped = urwid.Padding(columns, left=self.padding_left, right=self.padding_right)
        wrapped = urwid.AttrWrap(wrapped, low, high)
        urwid.WidgetWrap.__init__(self, wrapped)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class TabFrame(urwid.Frame):
    '''
    TabFrame makes urwid.Frame switch focus between
    body and footer when pressing 'tab'
    '''
    def keypress(self, size, key):
        if key == 'tab':
            if self.focus_part == 'body':
                try:
                    self.set_focus('footer')
                except IndexError: # sometimes there is no footer
                    pass
                return None
            elif self.focus_part == 'footer':
                self.set_focus('body')
                return None
            else:
                # do default action if
                # focus_part is 'header'
                self.__super.keypress(size, key)
        return self.__super.keypress(size, key)


