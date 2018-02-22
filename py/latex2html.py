'''
Not a complete translation engine, of course; just a few regex-based
helpers for translating simple formatting macros, just so that we can
use super- and subscript and italics, just like JabRef.

Can Jabref deal with nested format tags? Is it important? Probably not.
'''

# We first map entities to latex, but later invert it.
import re

class EntityTranslator(object):

    entity2latex = {
        r'nbsp'      : r'~',
        r'ndash'     : r'--',
        r'mdash'     : r'---',
        r'reg'       : r'\textregistered',
        #
        r'auml'      : r'\"a',
        r'euml'      : r'\"e',
        r'iuml'      : r'\"i',
        r'ouml'      : r'\"o',
        r'uuml'      : r'\"u',
        r'Auml'      : r'\"A',
        r'Euml'      : r'\"E',
        r'Iuml'      : r'\"I',
        r'Ouml'      : r'\"O',
        r'Uuml'      : r'\"U',
        #
        r'aacute'    : r'\'a',
        r'eacute'    : r'\'e',
        r'iacute'    : r'\'i',
        r'oacute'    : r'\'o',
        r'uacute'    : r'\'u',
        r'Aacute'    : r'\'A',
        r'Eacute'    : r'\'E',
        r'Iacute'    : r'\'I',
        r'Oacute'    : r'\'O',
        r'Uacute'    : r'\'U',
        #
        r'agrave'    : r'\`a',
        r'egrave'    : r'\`e',
        r'igrave'    : r'\`i',
        r'ograve'    : r'\`o',
        r'ugrave'    : r'\`u',
        r'Agrave'    : r'\`A',
        r'Egrave'    : r'\`E',
        r'Igrave'    : r'\`I',
        r'Ograve'    : r'\`O',
        r'Ugrave'    : r'\`U',
        #
        r'acirc'     : r'\^a',
        r'ecirc'     : r'\^e',
        r'icirc'     : r'\^i',
        r'ocirc'     : r'\^o',
        r'ucirc'     : r'\^u',
        r'Acirc'     : r'\^A',
        r'Ecirc'     : r'\^E',
        r'Icirc'     : r'\^I',
        r'Ocirc'     : r'\^O',
        r'Ucirc'     : r'\^U',
        #
        r'alpha'     : r'$\alpha$',
        r'beta'      : r'$\beta$',
        r'gamma'     : r'$\gamma$',
        r'delta'     : r'$\delta$',
        r'epsilon'   : r'$\epsilon$',
        r'zeta'      : r'$\zeta$',
        r'eta'       : r'$\eta$',
        r'theta'     : r'$\theta$',
        r'iota'      : r'$\iota$',
        r'kappa'     : r'$\kappa$',
        r'lambda'    : r'$\lambda$',
        r'mu'        : r'$\mu$',
        r'nu'        : r'$\nu$',
        r'xi'        : r'$\xi$',
        r'pi'        : r'$\pi$',
        r'rho'       : r'$\rho$',
        r'sigma'     : r'$\sigma$',
        r'tau'       : r'$\tau$',
        r'upsilon'   : r'$\upsilon$',
        r'phi'       : r'$\phi$',
        r'chi'       : r'$\chi$',
        r'psi'       : r'$\psi$',
        r'omega'     : r'$\omega$',
        #
        r'Gamma'     : r'$\Gamma$',
        r'Delta'     : r'$\Delta$',
        r'Lambda'    : r'$\Lambda$',
        r'Theta'     : r'$\Theta$',
        r'Pi'        : r'$\Pi$',
        r'Sigma'     : r'$\Sigma$',
        r'Phi'       : r'$\Phi$',
        r'Psi'       : r'$\Psi$',
        r'Omega'     : r'$\Omega$',
        #
        r'rarr'      : r'$\rightarrow$',
    }

    latex2entity = { v:k for k,v in entity2latex.items() }


    latex_keys = [re.escape(k) for k in latex2entity.keys()]
    latex_keys = '|'.join(latex_keys).replace('$', '$?')  # we may have several consecutive macros in math mode,
                                                        # so $ characters may be missing on either end.
    l2e_regex = re.compile(latex_keys)

    # now, extend the dict so that the entries with missing dollars are found, too
    for k,v in list(latex2entity.items()):
        if k.startswith('$'):
            latex2entity[k.lstrip('$')] = latex2entity[k.rstrip('$')] = latex2entity[k.strip('$')] = v

    def l2e_sub(self, mo):
        lx = mo.group()
        # the missing dollars strike again.
        return r"&%s;" % self.latex2entity[lx]


    def __call__(self, s):
        return self.l2e_regex.sub(self.l2e_sub, s)


class GroupSplitter(object):
    '''
    find groups by matching braces
    '''
    def _strip_braces(self, atom, braces):
        '''
        strip braces from string
        '''
        if len(atom) > 1 and ''.join((atom[0], atom[-1])) == braces:
            atom = atom[1:-1]
        return atom


    def __call__(self, rawarg, limit=None, start_pos=0, braces='{}'):
        '''
        tailor this to finding arguments for latex commands.
        '''
        group_start, group_end = braces
        assert group_start != group_end, "opening and closing brace must be different"

        rawarg = rawarg[start_pos:] #.lstrip()  # latex commands usually gobble white space
                                                # preceding their arguments, so we allow that here
                                                # no, we don't, it's going to make bookkeeping messy.
        nesting = 0
        atoms = []
        atom = []

        for i, char in enumerate(rawarg):

            atom.append(char)

            if char == group_start:
                nesting += 1

            elif char == group_end:
                nesting -= 1

            if nesting == 0:
                atoms.append(''.join(atom))
                atom = []

            if limit and len(atoms) == limit:
                break

        if len(atom):
            atoms.append(''.join(atom))

        atoms = [self._strip_braces(atom, braces) for atom in atoms]

        return i+1, atoms


class Latex2Html(object):
    '''
    translate both entities and commands, using the above classes as helpers

    we _could_ make the commands configurable, I suppose, but for now I won't.
    '''
    commands = {
        r'\emph' : (1, '<i>%s</i>'),
        r'\textsuperscript' : (1, '<sup>%s</sup>'),
        r'\textsubscript' : (1, '<sub>%s</sub>'),
        r'\hyp' : (0, '-')
    }


    latex_keys = [re.escape(k) for k in commands.keys()]
    command_regex = re.compile('|'.join(latex_keys))

    group_splitter = GroupSplitter()
    entity_translator = EntityTranslator()

    def command_translate(self, s):
        '''
        replace all latex command occurrences using the commands dict
        '''
        matches = self.command_regex.finditer(s)

        new_string = []
        string_pointer = 0

        for m in matches:
            cmd, cmd_start, cmd_end = m.group(), m.start(), m.end()

            # print cmd, cmd_end
            nargs, fmt = self.commands[cmd]

            if nargs > 0:
                sub_length, args = self.group_splitter(s, start_pos=cmd_end, limit=nargs)
                replacement = fmt % tuple(args)
            else:
                sub_length, args = 0, ''
                replacement = fmt

            # OK, now, how do we cobble together the new string? That seems a little icky.
            new_string.append(s[string_pointer:cmd_start])
            new_string.append(replacement)
            string_pointer = cmd_end + sub_length

        new_string.append(s[string_pointer:])

        return ''.join(new_string)


    def __call__(self, s):
        '''
        - translate entities
        - translate latex commands
        - strip superfluous braces
        '''
        s = self.entity_translator(s)
        s = self.command_translate(s)
        length, groups = self.group_splitter(s)
        return ''.join(groups)



if __name__ == '__main__':
    l2h = Latex2Html()

    tests = [
              r"First, just a plain string without anything special",
              r"Next, some entities and stuff: Staphylococcal {$\alpha$}- to {$\Omega$}-toxin, $\chi$-squared, and W\"urstchen, but also $\alpha\beta\gamma$-toxin",
              r"Now, some silly groups: This really {stinks}}{to high} heaven",
              r"Now, the works: Staphylococcal {$\alpha$}-toxin, \textsuperscript{streptolysin-O,} and {\emph{Escherichia coli}} hemolysin\textregistered: prototypes of pore\hyp{}forming bacterial cytolysins. Also, CO\textsubscript{2}!"
            ]

    import sys

    try:
        times = int(sys.argv[1])
    except IndexError:
        times = 1

    for test in tests:
        print(test)

        for time in range(times):
            translated = l2h(test)

        print(translated)
        print()

