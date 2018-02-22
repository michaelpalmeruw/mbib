'''
format a set of references to reasonable html. harrrumph.
I guess I want to reuse this after all. However, I will
keep it dumb and subordinate it to imex.
'''
import sys, re, textwrap, pprint
from latex2html import Latex2Html

class HtmlFormatter(object):

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
        %(howpublished)s.
    '''

    misc_no_url = '''\
        %(author)s (%(year)s)
        %(title)s.
        %(howpublished)s.
    '''

    other_stuff = 'something else: %(bibliographictype)s (%(identifier)s)'


    url_prefixes = dict(
        url = "",
        doi = "https://doi.org/",
        pmid = "https://www.ncbi.nlm.nih.gov/pubmed/?term="
    )


    def __init__(self, reflist, sort_key=lambda r: -r['year']):
        '''
        ok, we work on a list of references, not just on a single one. Got it.
        '''
        if sort_key is not None:
            reflist.sort(key=sort_key)
        self.reflist = reflist
        self.latex2html = Latex2Html()


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


    def format_reference(self, ref):
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

        return fs % ref


        #try:
            #return fs % ref
        #except KeyError:
            #ref = pprint.pformat(ref)
            #return '<span class="error" style="color:red">%s</span>' % ref


    def __call__(self):
        return [ self.format_reference(ref) for ref in self.reflist ]


class OlFormatter(HtmlFormatter):
    '''
    stuff the formatted entries into an ordered list.
    '''
    list_wrapper = '<ol class="references">\n%s\n</ol>'
    entry_wrapper = '<li id="%s%s">%s</li>'
    ws_re = re.compile('\s+')

    def __call__(self, id_prefix="ref"):
        entries = HtmlFormatter.__call__(self)
        formatted = []

        for i, e in enumerate(entries):
            e = e.strip()
            e = self.ws_re.sub(' ', e)
            e = self.entry_wrapper % (id_prefix, i+1, e)

            formatted.append(textwrap.fill(e,
                                           initial_indent = ' ' * 4,
                                           subsequent_indent = ' ' * 8,
                                           width=100,
                                           break_on_hyphens = False))

        return self.list_wrapper % '\n'.join(formatted)


class DlFormatter(HtmlFormatter):
    '''
    stuff everything into a definition list, with the reference keys
    as the entries. Yeah. That should help with inserting citations.
    '''
    list_wrapper = '<dl>\n%s\n</dl>'
    dt_wrapper = '<dt id="%s%s">%s</dt>'
    dd_wrapper = '<dd>%s</dd>\n'
    ws_re = re.compile('\s+')

    def __call__(self, id_prefix="ref"):
        formatted = []

        for i, reference in enumerate(self.reflist):
            dt = reference['bibtexkey']
            formatted.append(self.dt_wrapper % (id_prefix, i+1, dt))

            entry = self.format_reference(reference).strip()
            entry = self.ws_re.sub(' ', entry)
            entry = self.dd_wrapper % entry

            formatted.append(textwrap.fill(entry, initial_indent=' ' * 4, subsequent_indent=' ' * 8))

        return self.list_wrapper % '\n'.join(formatted)



if __name__ == '__main__':

    from hub import hub

    refs = hub.get_selected_refs_full()
    formatter = OlFormatter(refs, None)

    print(formatter())

