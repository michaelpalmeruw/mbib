'''
format a set of references to reasonable html. harrrumph.
I guess I want to reuse this after all. However, I will
keep it dumb and subordinate it to imex.

Need to deal with missing values some time - switch to some
custom formatter that substitutes values.

Well, this is really rather slow, much slower than bibtex -
can we speed it up a bit? Or at least give it a progress
bar.
'''
import sys, re, textwrap, pprint
from latex2html import Latex2Html
from hub import hub


class ReferenceFormatter(object):

    # formats for different types of records
    journal_with_url = '''\
        %(author)s (%(year)s)
        %(title)s.
        <a href="%(url)s" target="_blank"><i>%(journal)s</i> %(volume)s:%(pages)s</a>
    '''

    journal_no_url = '''\
        %(author)s (%(year)s)
        %(title)s.
        <i>%(journal)s</i> %(volume)s:%(pages)s
    '''

    book_with_url = '''\
        %(author)s (%(year)s)
        <a href="%(url)s" target="_blank">%(booktitle)s</a> (%(publisher)s).
    '''

    book_no_url = '''\
        %(author)s (%(year)s)
        %(booktitle)s  (%(publisher)s).
    '''

    misc_with_url = '''\
        %(author)s (%(year)s)
        <a href="%(url)s" target="_blank">%(title)s</a>.
        %(reftype)s.
    '''

    misc_no_url = '''\
        %(author)s (%(year)s)
        %(title)s.
        %(reftype)s.
    '''

    other_stuff = 'something else: %(reftype)s (%(bibtexkey)s)'

    url_prefixes = dict(
        url = "",
        doi = "https://doi.org/",
        pmid = "https://www.ncbi.nlm.nih.gov/pubmed/?term="
    )

    latex2html = Latex2Html()

    def format_authors(self, ref):
        '''
        we format the authors in place
        '''
        raw_authors = ref.get('author', '')

        authors = raw_authors.split(' and ')

        if len(authors) == 1:
            rv = authors[0]
        elif len(authors) == 2:
            rv = '%s and %s' % tuple(authors)
        else:
            rv = '%s et al.' % authors[0]

        frags = rv.split()

        for i, f in enumerate(frags):
            if len(f) == 1:
                frags[i] = f + '.'

        ref['author'] = ' '.join(frags)


    def format_url(self, ref):
        '''
        find url if possible
        '''
        if 'url' in ref:
            return

        for key in "doi pmid".split():
            value = ref.get(key)
            if value is not None:
                ref['url'] = self.url_prefixes[key] + value


    def format_entries(self, ref):
        '''
        do fix-ups to some entriesbefore filling html templates
        '''
        self.format_authors(ref) # authors are modified in place
        self.format_url(ref)

        for key in "title abstract author".split():
            if key in ref:
                ref[key] = self.latex2html(ref[key])


    def __call__(self, ref):
        self.format_entries(ref)

        reftype = ref['reftype']

        if reftype == 'article': # most common case
            if 'url' in ref:
                fs = self.journal_with_url
            else:
                fs = self.journal_no_url

            ref.setdefault('volume', '-')

        elif reftype == 'book':
            if not 'booktitle' in ref:
                ref['booktitle'] = ref['title']

            if 'url' in ref:
                fs = self.book_with_url
            else:
                fs = self.book_no_url

        elif reftype == 'misc':
            if 'url' in ref:
                fs = self.misc_with_url
            else:
                fs = self.misc_no_url

        else:
            fs = self.other_stuff

        ref.setdefault('volume', '-')
        ref.setdefault('pages', 'x-x')

        # return fs % ref
        return fs % ref


class OlFormatter(object):
    '''
    stuff the formatted entries into an ordered list.
    '''
    list_wrapper = '<html>\n<ol class="references">\n%s\n</ol>\n</html>'
    entry_wrapper = '<li id="%s%s">%s</li>'
    ws_re = re.compile('\s+')

    text_wrapper = textwrap.TextWrapper(
                                initial_indent = ' ' * 4,
                                subsequent_indent = ' ' * 8,
                                width=100,
                                break_on_hyphens = False
                            ).fill

    def __init__(self, reflist, sort_key="year", reverse_sort=False, id_prefix="ref"):
        '''
        ok, we work on a list of references, not just on a single one. Got it.
        '''
        dflt = 0 if sort_key == "year" else ""
        sort_function = lambda r: r.get(sort_key, dflt)
        self.reflist = sorted(reflist, key=sort_function, reverse=reverse_sort)

        self.id_prefix = id_prefix
        self._formatter = ReferenceFormatter()


    def format_ref(self, ref, index):
        '''
        format an individual reference entry
        '''
        e = self._formatter(ref).strip()
        e = self.ws_re.sub(' ', e)
        e = self.entry_wrapper % (self.id_prefix, index, e)

        return [self.text_wrapper(e)]


    def __call__(self):
        progress_bar = hub.progress_bar(len(self.reflist), title="Formatting references")
        progress_bar.show()

        formatted = []

        for i, r in enumerate(self.reflist):
            progress_bar.update(i+1)
            formatted.extend(self.format_ref(r, i+1))

        return self.list_wrapper % '\n'.join(formatted)


class DlFormatter(OlFormatter):
    '''
    stuff everything into a definition list, with the reference keys
    as the entries. Yeah. That should help with inserting citations.

    need to derive this properly from the declared parent class
    '''
    list_wrapper = '<html>\n<dl>\n%s\n</dl>\n</html>'
    dt_wrapper = '<dt id="%s%s">%s</dt>'
    dd_wrapper = '<dd>%s</dd>\n'

    def format_ref(self, ref, index):
        '''
        format an individual reference entry
        '''
        dt = self.dt_wrapper % (self.id_prefix, index, ref['bibtexkey'])

        e = self._formatter(ref).strip()
        e = self.ws_re.sub(' ', e)
        dd = self.dd_wrapper % e

        return [dt, self.text_wrapper(dd)]


