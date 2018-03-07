import subprocess, urllib.parse, collections, re, os, time
from weakref import proxy
from config import config

_brace_re = re.compile(r'(?<=[^\\])[\{\}]')

def validate_bibtex_value(txt):
    '''
    we only perform rudimentary validation - just check whether braces are
    balanced. Otherwise, we assume the user knows what they are doing.

    Since the regex doesn't find leading braces, we add a leading space
    before running it.
    '''
    txt = txt or ''
    braces = _brace_re.findall(' ' + txt)

    counter = 0

    for brace in braces:
        counter += 1 if brace == '{' else -1
        if counter < 0:
            return False

    return counter == 0


class Link(object):
    '''
    auxiliary class for OrderedSet
    '''
    __slots__ = 'prev', 'next', 'key', '__weakref__'


class OrderedSet(collections.MutableSet):
    '''
    from https://raw.githubusercontent.com/ActiveState/code/3b27230f418b714bc9a0f897cb8ea189c3515e99/recipes/Python/576696_OrderedSet_with_Weakrefs/recipe-576696.py
    '''
    def __init__(self, iterable=None):
        self.__root = root = Link()         # sentinel node for doubly linked list
        root.prev = root.next = root
        self.__map = {}                     # key --> link
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.__map)

    def __contains__(self, key):
        return key in self.__map

    def add(self, key):
        # Store new key in a new link at the end of the linked list
        if key not in self.__map:
            self.__map[key] = link = Link()
            root = self.__root
            last = root.prev
            link.prev, link.next, link.key = last, root, key
            last.next = root.prev = proxy(link)

    def discard(self, key):
        # Remove an existing item using self.__map to find the link which is
        # then removed by updating the links in the predecessor and successors.
        if key in self.__map:
            link = self.__map.pop(key)
            link.prev.next = link.next
            link.next.prev = link.prev

    def __iter__(self):
        # Traverse the linked list in order.
        root = self.__root
        curr = root.next
        while curr is not root:
            yield curr.key
            curr = curr.next

    def __reversed__(self):
        # Traverse the linked list in reverse order.
        root = self.__root
        curr = root.prev
        while curr is not root:
            yield curr.key
            curr = curr.prev

    def pop(self, last=True):
        if not self:
            raise KeyError('set is empty')
        key = next(reversed(self)) if last else next(iter(self))
        self.discard(key)
        return key

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return not self.isdisjoint(other)


def locate(fn, case_sensitive=False, as_regex=True):
    '''
    use 'locate' to find a file
    '''
    args = ['locate']

    if not case_sensitive:
        args.append('-i')

    if as_regex:
        args.append('--regex')

    args.append(fn)

    try:
        p = subprocess.Popen(args, \
                                stdout=subprocess.PIPE, \
                                stderr=subprocess.STDOUT)
        blurb = p.communicate()[0].decode("utf-8")
        return blurb.strip().split()

    except FileNotFoundError: # expected if locate is not installed
        return []


def pubmed_search_url(data):
    '''
    create url from existing data fields to search for missing pmid
    '''
    fields = dict(
               author = 'au',
               journal = 'so',
               year = 'dp',
               volume = 'vol',
               pages = 'pg'
             )

    formatted = []

    for field, abbrev in fields.items():
        value = data.get(field)

        if value is not None:
            if field == 'author':
                first = value.split('and')[0]
                value = first.replace(',','')

            elif field == 'pages':
                value = value.split('-')[0]

            formatted.append("%s[%s]" % (value, abbrev))

    base_url = "https://www.ncbi.nlm.nih.gov/pubmed/?term="
    encoded = urllib.parse.quote(" ".join(formatted))

    return base_url + encoded


def xclip(text, isfile=False, timeout=2):
    """
    Copy text or file contents into X clipboard. Requires xclip to be installed.
    """
    if isfile:
        text = open(text, 'r').read().strip()

    p = subprocess.Popen("xclip -l 1 -quiet",
                         shell=True,
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE
                        )
    weg, error = p.communicate(str.encode(text), timeout=timeout)

    if len(error) > 1:
        print(error)
        raise IOError("Copying to clipboard failed - content too large?")


def userpath(raw_path):
    '''
    append rawpath to user home directory
    '''
    home_dir = os.path.expanduser('~')
    full_path = os.path.join(home_dir,raw_path)
    return os.path.normpath(full_path)


def writefile(file_name, text):
    '''
    'xclip' is used as a magic filename set sends the output to the clipboard
    instead of a file.

    All other file names and paths are interpreted relative to the user's
    home directory. Howabout using makedirs?
    '''
    xclip_name = config['paths']['xclip']

    if not file_name or file_name == xclip_name:
        rv = 'clipboard'
        xclip(text)
    else:
        full_name = userpath(file_name)
        open(full_name,'w').write(text)
        rv = full_name.replace(os.path.expanduser('~'), '~')

    return rv




if __name__ == '__main__':

    data = dict(
             author = "Muraih, JK and Wurst, Hans",
             year = "2012",
             journal = "Biochimica et Biophysica Acta",
             volume = "1818",
             pages = "1642-1647"
           )

    # print(pubmed_search_url(data))



