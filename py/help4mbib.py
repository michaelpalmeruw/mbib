import urwid, textwrap
from urwidtools import dialog, widgets, application
from hub import hub


class HelpDialog(dialog.DialogWithLabels):
    '''
    we need the BoxAdapter to tell urwid the height of our listbox.
    '''
    label_width = 10
    divide_chars = 2

    inner_height = 15
    outer_height = inner_height + 7

    inner_width = 60
    outer_width = inner_width + 6

    title = "Help".ljust(label_width+divide_chars) + "(use \u2191/\u2193 to scroll)"

    dismiss_keys = ['esc', 'f1']
    focus_part = 'body'

    def make_widgets(self):
        actions = list(hub.actions.items())

        for i, thing in enumerate(actions):
            key, tpl = thing
            action, help_text = tpl
            self.set_widget(key, urwid.Text(help_text))

            if i+1 < len(actions):
                self.add_divider()


    def exit_buttons(self):
        '''
        hook for creating dialog exit buttons.
        again, we need to figure out how to get hold of values.
        '''
        return [ ("OK", "ok") ]

hub.register('show_help', lambda *args: HelpDialog().show())


class ErrorDialog(dialog.MessageBox):
    '''
    just pass a list of errors and display them. Why do I have this here, under help?

    Also, this isn't so great - it can easily overflow, and the we can't scroll. We
    should rather be adding widgets to the body. Well, let's wait an see. show_errors
    does take a 'height' argument that can be adjusted when needed.
    '''
    title = 'Error'
    message_style = 'error'
    outer_height = 10


hub.register('show_errors', lambda errors, *a, **kw: ErrorDialog(errors, *a, **kw).show())


class InfoDialog(ErrorDialog):
    '''
    for success messages and other benign infos
    '''
    title = "Info"
    message_style = "body"


hub.register('show_info', lambda info, *a, **kw: InfoDialog(info, *a, **kw).show())
