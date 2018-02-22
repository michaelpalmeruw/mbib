
class RestraintParser(object):
    '''
    Full-fledged SQL it ain't, because that is just not possible.
    Multiple fields will always be joined by conjunction. So, we
    only deal with multiple clauses in single fields.

    It seems that && and || are good operators to use; anyone with
    a bit of programming experience likely has seen them. Then, we
    need to establish hierarcy. Conventionally, conjunction binds
    more tightly than disjunction, but is that useful here? Are we
    not more likely to look for A and (B or C) than for (A and B) or C?
    I think so; thus, I will make disjunction bind tighter.

    Next, operators. Let there be

    >, >=, <, <=

    or nothing. The default in that case will be '=' or 'like', depending
    on whether or not there is a percent sign in the string.

    Parsing groups from brackets anyone? Not now.
    '''

    disjunction = "||"
    conjunction = "&&"
    comparators = ">= <= > < =".split()
    placeholder = "table_field"

    def __init__(self, raw):
        self.raw = raw


    def translate_restraint(self, clause):
        '''
        translate a single clause, unencumbered by conjunctions and disjunctions
        '''
        for comp in self.comparators:
            if clause.startswith(comp):
                term = clause[len(comp):].strip()
                break
        else:
            term = clause
            comp = "like" if "%" in term else "="

        try:
            term = int(term)
            return '{%s} %s %s' % (self.placeholder, comp, term)
        except ValueError:
            return '{%s} %s "%s"' % (self.placeholder, comp, term.strip())


    def __call__(self):

        cfrags = self.raw.split(self.conjunction)
        ctrans = []

        for cf in cfrags:
            restraints = cf.split(self.disjunction)
            translated = [ self.translate_restraint(r.strip()) for r in restraints ]

            ctrans.append("(%s)" % (" or ".join(translated) ) )

        return " and ".join(ctrans)


if __name__ == '__main__':

    for s in [
        ">= 2007 && < 2012",
        "%Taylor% || %Palmer% && Muraih",
        "2007 ||  2008",
        ]:

        r = RestraintParser(s)()
        print(r)
        print(r.format(table_field="optional2"))
        print("")




