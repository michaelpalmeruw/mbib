import traceback, urwid

'''
an application manager base class.
'''

# there can only be one app instance, and it is expedient
# to store it in a global variable.
app = None

def exit():
    '''
    in module scope so that it is easier to find from dialog.py
    '''
    raise urwid.ExitMainLoop()


class Application(object):
    '''
    try to make the invocation a little more straightforward.

    We could pass along a reference to the application object to
    every dialog that gets invoked. Does that make sense?

    Also, I guess we need a dialog stack to append to and pop
    from as we open and close dialogs. Either that, or we need
    the dialogs themselves to manage the views.
    '''
    palette = [  # a default palette
        ('body','black','light gray'),
        ('border','black','light gray'),
        ('shadow','white','dark gray'),
        ('selectable','black', 'dark cyan'),
        ('focus','black','dark cyan','bold'),
        ('focustext','light gray','dark blue'),
        ('button normal','light gray', 'dark blue', 'standout'),
        ('button select','white', 'dark green'),
       ]

    def __init__(self):
        global app
        app = self

        self._loop = urwid.MainLoop(
                       None,
                       palette=self.palette,
                       unhandled_input=self.unhandled_input)

        # self.footer = self.get_footer()

        self._widget_stack = []
        root = self.get_root_widget()
        self.show_widget(root)


    def get_screen_size(self):
        return self._loop.screen.get_cols_rows()


    def get_root_widget(self):
        raise NotImplementedError


    def unhandled_input(self, key):
        '''
        example implementation: exit on q
        '''
        if hasattr(key, 'lower') and  key.lower() == 'q':
            raise urwid.ExitMainLoop()


    def get_widget(self):
        try:
            return self._widget_stack[-1]
        except IndexError:
            return None


    def show_widget(self, widget):
        self._widget_stack.append(widget)
        self._loop.widget = widget


    def hide_widget(self, widget=None):
        '''
        hm. This just hides the topmost widget,
        which may not be the one we want to hide.
        '''
        if widget is None:
            widget = self._widget_stack[-1]

        self._widget_stack.remove(widget)
        self._loop.widget = self._widget_stack[-1]
        self.refresh_screen()


    def refresh_screen(self):
        '''
        let client code request a screen update
        '''
        self._loop.draw_screen()


    def exit(self):
        '''
        delegate to module level function
        '''
        exit()


    def at_begin_loop(self):
        '''
        hook for running code after setup is complete, but before event loop
        '''
        pass


    def __call__(self):
        '''
        catch exceptions and display the traceback
        '''
        self.at_begin_loop()

        try:
            self._loop.run()
        except:
            tb = traceback.format_exc()
            print(tb)
            input("An unhandled error occurred. Press <enter> to quit")

