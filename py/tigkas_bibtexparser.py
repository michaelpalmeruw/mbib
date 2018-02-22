"""
Copyright (C) 2011 by Panagiotis Tigkas <ptigas@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

---

obtained from https://github.com/ptigas/bibpy

Changes by M.P.:
- removed json, pprint, fileinput imports (pprint and fileinput were unused)
- let Parser inherit from object
- converted iterator to Python3
- forced field names to lowercase
- removed parse_authors (done in imex), title mangling, and pages->page renaming
- changed 'id' key to 'bibtexkey'
- changed 'type' key to 'reftype'
- added __call__ method
- hacked around the spurious white space insertion using temporary substitution
- prevent removal of round brackets ()
"""

import re

def clear_comments(data):
    """Return the bibtex content without comments"""
    res = re.sub(r"(%.*\n)", '', data)
    res = re.sub(r"(comment [^\n]*\n)", '', res)
    return res

class Parser(object) :
    """Main class for Bibtex parsing"""

    cookie = 'z_z_z'  # temporary white space substitution

    # compile some regexes
    white = re.compile(r"[\n|\s]+")
    nl = re.compile(r"[\n]")
    # self.token_re = re.compile(r"([^\s\"#%'(){}@,=]+|\n|@|\"|{|}|=|,)")
    token_re = re.compile(r"([^\s\"#%'{}@,=]+|\n|@|\"|{|}|=|,)")

    def tokenize(self):
        """
        Returns a token iterator
        """
        for item in self.token_re.finditer(self.data):
            i = item.group(0)
            if self.white.match(i):
                if self.nl.match(i):
                    self.line += 1
                continue
            else:
                yield i

    def __init__(self, data):

        # carry out some temporary substitutions. This parser adds plenty of
        # spurious white space, and we need to get rid of it.
        data = re.sub('\s+', self.cookie, data)

        self.data = data
        self.token = None
        self.token_type = None
        self.hashtable = {}
        self.mode = None
        self.records = {}
        self.line = 1

        self.tokenizer = self.tokenize() # instantiate tokenizer iterator


    def parse(self) :
        """Parses self.data and stores the parsed bibtex to self.rec"""
        while True :
            try :
                self.next_token()
                while self.database() :
                    pass
            except StopIteration :
                break

    def next_token(self):
        """Returns next token """
        self.token = next(self.tokenizer)
        #print self.line, self.token

    def database(self) :
        """Database"""
        if self.token == '@' :
            self.next_token()
            self.entry()

    def entry(self) :
        """Entry"""
        if self.token.lower() == 'string' :
            self.mode = 'string'
            self.string()
            self.mode = None
        else :
            self.mode = 'record'
            self.record()
            self.mode = None

    def string(self) :
        """String"""
        if self.token.lower() == "string" :
            self.next_token()
            if self.token == "{" :
                self.next_token()
                self.field()
                if self.token == "}" :
                    pass
                else :
                    raise NameError("} missing")

    def field(self) :
        """Field"""
        name = self.name()
        if self.token == '=' :
            self.next_token()
            value = self.value()
            if self.mode == 'string' :
                self.hashtable[name] = value
            return (name, value)

    def value(self) :
        """Value"""
        value = ""
        val = []

        while True :
            if self.token == '"' :
                while True:
                    self.next_token()
                    if self.token == '"' :
                        break
                    else :
                        val.append(self.token)
                if self.token == '"' :
                    self.next_token()
                else :
                    raise NameError("\" missing")
            elif self.token == '{' :
                brac_counter = 0
                while True:
                    self.next_token()
                    if self.token == '{' :
                        brac_counter += 1
                    if self.token == '}' :
                        brac_counter -= 1
                    if brac_counter < 0 :
                        break
                    else:
                        val.append(self.token)
                if self.token == '}' :
                    self.next_token()
                else :
                    raise NameError("} missing")
            elif self.token != "=" and re.match(r"\w|#|,", self.token) :
                value = self.query_hashtable(self.token)
                val.append(value)
                while True:
                    self.next_token()
                    # if token is in hashtable then replace
                    value = self.query_hashtable(self.token)
                    if re.match(r"[^\w#]|,|}|{", self.token) : #self.token == '' :
                        break
                    else :
                        val.append(value)

            elif self.token.isdigit() :
                value = self.token
                self.next_token()
            else :
                if self.token in self.hashtable :
                    value = self.hashtable[ self.token ]
                else :
                    value = self.token
                self.next_token()

            if re.match(r"}|,",self.token ) :
                break

        value = ' '.join(val)
        return value

    def query_hashtable( self, s ) :
        if s in self.hashtable :
            return self.hashtable[ self.token ]
        else :
            return s

    def name(self) :
        """Returns parsed Name"""
        name = self.token
        self.next_token()
        return name

    def key(self) :
        """Returns parsed Key. OK, so this is the identifier. """
        key = self.token
        self.next_token()
        return key

    def record(self) :
        """Record"""
        if self.token not in ['comment', 'string', 'preamble'] :
            record_type = self.token
            self.next_token()

            if self.token == '{' :
                self.next_token()
                key = self.key()

                record = self.records[ key ] = dict(
                    reftype = record_type,
                    bibtexkey = key
                )

                if self.token == ',' :
                    while True:
                        self.next_token()
                        field = self.field()
                        if field :
                            k, val = field

                            if k == 'pages' :
                                val = val.replace('--', '-')
                                val = val.replace('–', '-')

                            record[self.sanitize(k.lower())] = self.sanitize(val)

                        if self.token != ',' :
                            break
                    if self.token == '}' :
                        pass
                    else :
                        # assume entity ended
                        if self.token == '@' :
                            pass
                        else :
                            raise NameError("@ missing")

    def sanitize(self, s):
        '''
        strip out spaces, all of which are spurious
        back-substitute original spaces
        strip outer spaces
        '''
        s = s.replace(' ', '')
        s = s.replace(self.cookie, ' ')
        return s.strip()


    def __call__(self):
        self.parse()
        l = list(self.records.values())
        return l



if __name__ == '__main__':

    from pprint import pprint
    raw = r'''
    @article{doi:10.1021/ja00533a029,
    author = {Nanni, Edward J. and Stallings, Martin D. and Sawyer, Donald T.},
    title = {Sigmund {Freud} (1856-1939), {Karl} {K\"o}ller (1857-1944) and the
                    discovery of [local] anesthesia},
    journal = {Journal of the American Chemical Society},
    volume = {102},
    number = {13},
    pages = {4481-4485},
    year = {1980},
    doi = {10.1021/ja00533a029},

    URL = {
            http://dx.doi.org/10.1021/ja00533a029

    },
    eprint = {
            http://dx.doi.org/10.1021/ja00533a029

    }

    }
    '''

    parsed = Parser(raw)()
    pprint(parsed)
