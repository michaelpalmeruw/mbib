'''
let's try to cobble together the bits and pieces here.

Let's first try to insert something at the cursor position,
because so far we don't.

What's the logic here?

- first, figure out if we have a connection to Office
  and a text document. I guess that should be

I guess we want to import this conditionally - if uno is
not there, then the user may not care about libreoffice
at all. Well, I guess this kind of stuff can ultimately
go into a config file.

Is it a good idea to throw this into one pot with the
LaTeX editors? Fewer shortcuts, but the process IS kind
of involved. I will give it a miss then.
'''
import os, sys, uno
from hub import hub, RefdbError, IntegrityError
from config import config

NoConnectException = uno.getClass("com.sun.star.connection.NoConnectException")
RuntimeException = uno.getClass("com.sun.star.uno.RuntimeException")
IllegalArgumentException = uno.getClass("com.sun.star.lang.IllegalArgumentException")
DisposedException = uno.getClass("com.sun.star.lang.DisposedException")
IOException = uno.getClass("com.sun.star.io.IOException")
NoSuchElementException = uno.getClass("com.sun.star.container.NoSuchElementException")

PropertyValue = uno.getClass("com.sun.star.beans.PropertyValue")
DIRECT_VALUE = uno.Enum("com.sun.star.beans.PropertyState","DIRECT_VALUE")


class ConnectionError(Exception):
    pass

class LibreOffice(object):
    '''
    adapted from Bibus. I guess we want to delay the creation of the connection
    until it is actually requested, so the connection setup must be removed
    from __init__.
    '''

    key_mapping = {
        'bibtexkey' : 'Identifier',
        'reftype'   : 'Bibliography-Type',
        'url'       : 'URL'
    }

    pipe_str = "uno:pipe,name=%s;urp;StarOffice.ComponentContext"
    tcp_str =  "uno:socket,host=localhost,port=%s;urp;StarOffice.ComponentContext"

    def __init__(self):
        self._db = hub.sqlite
        self.smgr = None


    def get_connection(self):
        '''
        connection setup. This should normally be done only once, I guess,
        though it
        '''
        # if self.smgr is not None: return
        # All this does is go belly up if LibreOffice is opened after mbib.
        # speed penalty of reconnecting every time seems imperceptible -
        # even with a large document. Maybe uno does caching already.

        localContext = uno.getComponentContext()
        resolver = localContext.ServiceManager.createInstanceWithContext(
                            "com.sun.star.bridge.UnoUrlResolver",
                            localContext
                )

        # adapted from bibOOoBase

        con_pars = dict(config['libreoffice'])

        if con_pars['mode'] == 'tcp':
            con_str = self.tcp_str % con_pars['port']
        else:
            assert con_pars['mode'] == 'pipe'
            con_str = self.pipe_str % con_pars['name']

        try:
            # connect to the running office
            ctx = resolver.resolve(con_str)
            self.smgr = ctx.ServiceManager
            self.desktop = self.smgr.createInstanceWithContext( "com.sun.star.frame.Desktop",ctx)
            self.oTrans = self.smgr.createInstanceWithContext("com.sun.star.util.URLTransformer", ctx)

        except NoConnectException as e:
            raise ConnectionError(e.Message)

        except IllegalArgumentException as e:
            raise ConnectionError(e.Message)

        except RuntimeException as e:
               raise ConnectionError(e.Message)


    def __getattr__(self, att):
        return getattr(hub.coredb, att)


    def get_document(self):
        '''
        get hold of current document, and I think also of its cursor position
        '''
        self.get_connection()

        try:
            self.model = self.desktop.getCurrentComponent()

            if self.model and self.model.getImplementationName() == 'SwXTextDocument':
                # this is a text document

                self.controller = self.model.getCurrentController()
                self.cursor = self.controller.getViewCursor()    # Current ViewCursor

                # access the document's text property
                self.text = self.model.Text

                # bibus has a lot of ministrations here regarding the actual bibliography,
                # but I want to see if I can get away with just leaving it alone.

            else:
                raise ConnectionError

        except DisposedException as e:
            raise ConnectionError


    def insert_ref(self, refdict):
        '''
        insert a single reference into the document
        '''
        self.get_document()

        ref = self.model.createInstance("com.sun.star.text.TextField.Bibliography")

        tmp = [PropertyValue(key.title(), 0, value, DIRECT_VALUE) for key, value in refdict.items()]
        ref.Fields = tuple(tmp)

        c = self.cursor.Text.createTextCursorByRange(self.cursor)
        c.Text.insertTextContent(c, ref, True)
        self.smgr  # some script I found said I need to invoke some UNO object in order to make it stick
                   # not sure that is true. we can test later.


    def oo_cite(self, node=None, status=True):
        '''
        insert a single reference into openoffice
        '''
        if node is None:
            node = hub.tree.focus_element()

        assert hub.is_ref(node)

        raw_data = self.get_ref_dict(node)

        adapted = {}
        junk = "branches abstract selected pmid reftype_id purpose ref_id"

        for key, value in raw_data.items():
            if key in junk:
                continue
            new_key = self.key_mapping.get(key, key.title())
            adapted[new_key] = value

        self.insert_ref(adapted)

        if status:
            hub.set_status_bar('cited %s' % adapted['Identifier'])


    def cite_by_key(self, bibtexkey):
        '''
        find a reference by key and cite it in OpenOffice.

        We select a real branch_id here. We could just fake one to
        get past is_ref, but the point of using a real one is that
        it excludes references in the trash; this is consistent
        with the menu restrictions. I guess this should be documented
        somewhere.
        '''
        fake_node = hub.node_for_bibtexkey(bibtexkey)

        if fake_node is None:
            hub.show_errors("reference '%s' not found" % bibtexkey)
            return

        try:
            self.oo_cite(fake_node)
        except ConnectionError:
            hub.show_errors("No active Writer document found")


    def cite_selected_oo(self):
        '''
        cite all currently selected references.
        '''
        selected_refs = hub.get_selected_refs() # list of (ref__id, branch_id) tuples

        if len(selected_refs) == 0:
            hub.show_errors("No references selected")
            return

        seen = set()

        for ref_id, branch_id in selected_refs:
            if ref_id in seen:
                continue
            seen.add(ref_id)
            fake_node = (hub.REF, ref_id, branch_id)

            try:
                self.oo_cite(fake_node, status=False)
            except ConnectionError:
                hub.show_errors("No active Writer document found")
                return

        suffix = "" if len(seen) == 1 else "s"
        hub.set_status_bar('cited %s reference%s' % (len(seen), suffix))


_export = '''
          oo_cite
          cite_by_key
          cite_selected_oo
          '''

#
hub.register_many(_export.split(), LibreOffice())


if __name__ == '__main__':

    lo = LibreOffice()

    dummy_ref = {
        'Identifier' : 'Mouse1984', # THIS is the magic incantation - and it has to be uppercase.
        'Author'     : 'Mickey Mouse',
        'Bibliography-Type'       : 'Article',
        'Journal'    : 'J Irrepr Res',
        'Volume'     : '42',
        'Year'       : '1984',
        'Title'      : 'Little Red Riding Rhodococcus',
        'URL'        : 'http://google.ca'
    }

    lo.insert_ref(dummy_ref)


