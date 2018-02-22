'''
We start with a mapping in the opposite direction, but in the end we invert it.
'''

entity2latex = {
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

import re

latex_keys = [re.escape(k) for k in latex2entity.keys()]
latex_keys = '|'.join(latex_keys).replace('$', '$?')  # we may have several consecutive macros in math mode,
                                                      # so $ characters may be missing on either end.
l2e_regex = re.compile(latex_keys)

# now, extend the dict so that the entries with missing dollars are found, too
for k,v in list(latex2entity.items()):
    if k.startswith('$'):
        latex2entity[k.lstrip('$')] = latex2entity[k.rstrip('$')] = latex2entity[k.strip('$')] = v

def l2e_sub(mo):
    lx = mo.group()
    # the missing dollars strike again.
    return r"&%s;" % latex2entity[lx]


def translate(s):
    return l2e_regex.sub(l2e_sub, s)


if __name__ == '__main__':
    test = r'Staphylococcal {$\alpha$}- to {$\Omega$}-toxin, $\chi$-squared, and W\"urstchen, but also $\alpha\beta\gamma$-toxin'
    print(translate(test))



