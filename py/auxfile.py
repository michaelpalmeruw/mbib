# Copyright (c) 2006-2017  Andrey Golovigin
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
parse LaTeX aux file

modifications from original:
- removed dependencies on other pybtex modules
- removed parsing of bibstyle
- removed case checking of citation keys
"""
import re

class AuxDataError(ValueError):
    def __init__(self, message, context=None):
        super(AuxDataError, self).__init__(message)


class AuxDataContext(object):
    lineno = None
    line = None
    filename = None

    def __init__(self, filename):
        self.filename = filename


class AuxFileParser(object):
    command_re = re.compile(r'\\(citation|bibdata|@input){(.*)}')
    context = None
    bibfile = None
    citations = None

    def __init__(self):
        self.citations = set()

    def handle_citation(self, keys):
        self.citations.update(keys.split(','))

    def handle_bibdata(self, bibdata):
        if self.bibfile is None:
            data = bibdata.split(',')
            data = [d for d in data if not d.endswith('-blx')] # exclude biblatex nonsense
            assert len(data) == 1
            self.bibfile = data[0]

    def handle_input(self, filename):
        self.parse_file(filename, toplevel=False)

    def handle_command(self, command, value):
        action = getattr(self, 'handle_%s' % command.lstrip('@'))
        action(value)

    def parse_line(self, line, lineno):
        self.context.lineno = lineno
        self.context.line = line.strip()
        match = self.command_re.match(line)
        if match:
            command, value = match.groups()
            self.handle_command(command, value)

    def parse_file(self, filename, toplevel=True):
        previous_context = self.context
        self.context = AuxDataContext(filename)

        with open(filename) as aux_file:
            for lineno, line in enumerate(aux_file, 1):
                self.parse_line(line, lineno)

        if previous_context:
            self.context = previous_context
        else:
            self.context.line = None
            self.context.lineno = None

        # these errors are fatal - always raise an exception
        if toplevel and self.bibfile is None:
            raise AuxDataError(r'found no \bibdata command', self.context)

    def __call__(self, filename):
        '''
        invoke the parser and return the results
        '''
        self.parse_file(filename)
        return self.bibfile, list(self.citations)


if __name__ == '__main__':
    import sys, pprint
    parser = AuxFileParser()
    bibfile, citations = parser(sys.argv[1])
    pprint.pprint(citations)
    print(bibfile, len(citations))
