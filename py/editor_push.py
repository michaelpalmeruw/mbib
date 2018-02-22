# this is the adapted from
# http://blog.eduardofleury.com/wp-content/uploads/2007/09/abstractnamespace.txt

# this is also the Python3 version. Well, it seems we do
# have to create a new socket every time, because otherwise
# we get a BrokenPipeError

# given the minuscule differences between Texstudio and Texmaker, we could also
# just unify the two - search for either texstudio or texmaker, and if we find
# one of them, pick the right cite template.

'''
listening in on the traffic between jabref and texstudio, we see

 2018/01/12 11:27:38.497618  length=36 from=0 to=35
... --insert-cite#!#\\cite{Jiang1996}< 2018/01/12 11:27:38.497926  length=3 from=0 to=2
ack> 2018/01/12 11:27:46.929498  length=70 from=0 to=69
...B--insert-cite#!#\\cite{Kaul1996,Kienker1997,Krissinel2007,Lang2003}< 2018/01/12 11:27:46.929795  length=3 from=0 to=2

with texmaker:

...+texmaker#!#-insert#!#\\cite{Czabotar2013}#!#< 2018/01/12 11:23:46.088984  length=3 from=0 to=2
ack> 2018/01/12 11:24:48.591871  length=77 from=0 to=76
...Itexmaker#!#-insert#!#\\cite{Gase1999,Gibrat1996,Gill1989,Grandjean2007}#!#< 2018/01/12 11:24:48.592023  length=3 from=0 to=2
ack> 2018/01/12 11:25:30.246938  length=77 from=0 to=76
...Itexmaker#!#-insert#!#\\cite{Gase1999,Gibrat1996,Gill1989,Grandjean2007}#!#< 2018/01/12 11:25:30.247156  length=3 from=0 to=2
ack> 2018/01/12 11:25:46.500213  length=44 from=0 to=43
...(texmaker#!#-insert#!#\\cite{Jiang1996}#!#< 2018/01/12 11:25:46.500380  length=3 from=0 to=2

'''

from socket import *
import re, fnmatch, os
from config import config
from hub import hub

# for finding those bluddy sockets, we may use this trick:
# re.compile(fnmatch.translate(pattern), re.IGNORECASE) and then findall
# or something, guard against the lockfile.


class PushkeyError(Exception):
    pass


class EditorPusher(object):

    app_strings = dict(
        texstu = r"...#--insert-cite#!#\cite{%s}",
        texmak = r"...texmaker#!#-insert#!#\cite{%s}#!#"
    )

    socket_dir = config['paths']['socketpath']

    def get_connection(self):
        n_sockets = 0

        for key, template in self.app_strings.items():
            pattern = '*%s*' % key
            fn_pat = re.compile(fnmatch.translate(pattern), re.IGNORECASE)

            sockets = [x for x in os.listdir(self.socket_dir) \
                              if fn_pat.match(x) \
                                 and not 'lockfile' in x \
                                 and not 'original' in x]
            ls = len(sockets)
            n_sockets += ls

            if ls == 1:
                self.fn = '%s/%s' % (self.socket_dir, sockets[0])
                self.cite_template = template

        if n_sockets == 0:
            raise PushkeyError("No running Texmaker or TeXstudio instance found")
        elif n_sockets > 1:
            raise PushkeyError("Multiple running Texmaker or TeXstudio instances found")


    def cite(self, refstring):
        '''
        push that string.
        '''
        try:
            self.get_connection()
        except PushkeyError as e:
            hub.show_errors(str(e))
            return

        msg = self.cite_template % refstring

        sock = socket(AF_UNIX, SOCK_STREAM)
        sock.connect(self.fn)
        sock.send(msg.encode("utf-8"))
        sock.send("\n".encode("utf-8"))

        # Block until new message arrives
        # msg = sock.recv(10)

        # forsooth. All this does is slow everything down ...
        # if we axe it, everything works smoothly. We
        # can probably rely on getting some exception if
        # the connection fails and not bother with the reply.

        # When the socket is closed cleanly, recv unblocks and returns ""
        # if not msg:
            # print("It seems the other side has closed its connection")

        sock.close()


    def cite_selected_latex(self):
        selected_refs = hub.get_selected_bibtexkeys()

        if len(selected_refs) == 0:
            hub.show_errors("No references selected")
            return

        self.cite(','.join(selected_refs))

    def cite_selected_node(self, node=None):
        '''
        cite reference key in latex.
        '''
        if node is None:
            node = hub.tree.focus_element()
        assert hub.is_ref(node), "Can cite only references, not folders"





_export = '''
          cite_selected_latex
          '''

hub.register_many(_export.split(), EditorPusher())


if __name__ == '__main__':
    ts = TexStudioMaker()

    for key in "hans wurst knall peng".split():
        ts.cite(key)



