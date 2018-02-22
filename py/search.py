'''

'''
import textwrap
from hub import hub, RefdbError, IntegrityError
from utils import OrderedSet
from string import ascii_letters
from config import config

class Search(object):

    # these are used for parsing search strings. I guess we could make
    # some of this configurable.

    letters = set(ascii_letters)

    disjunction = config['search']['bool_or']
    if set(disjunction) & letters:
        disjunction = ' %s ' % disjunction

    conjunction = config['search']['bool_and']
    if set(conjunction) & letters:
        conjunction = ' %s ' % conjunction

    bool_precedence = config['search']['bool_precedence']
    lazy_like = config['search']['lazy_like']

    comparators = ">= <= > < =".split()
    placeholder = "_table_field_"

    def __init__(self):
        self._db = hub.sqlite
        self._saved_search = None

        self.search_node = self.special_branch_nodes['Search']
        self.search_id = self.search_node[1]

    def saved_search(self):
        return self._saved_search


    def __getattr__(self, att):
        return getattr(hub.coredb, att)


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
            if not self.lazy_like: # don't add implicit wild cards
                comp = "like" if "%" in term else "="
            else:
                try:
                    int(term)
                    comp = '='
                except ValueError:
                    if not '%' in term:
                        term = '%{}%'.format(term)
                    comp = 'like'
        try:
            term = int(term)
            return '{%s} %s %s' % (self.placeholder, comp, term)
        except ValueError:
            return '{%s} %s "%s"' % (self.placeholder, comp, term.strip())


    def translate_restraints(self, table_field, raw):
        '''
        break up raw restraints across boolean operators and
        translate each of the resulting fragments, then
        glue everything back together again
        '''

        if self.bool_precedence == 'or':
            split_first, split_last, join_first, join_last = \
                self.conjunction, self.disjunction, " or ", " and "
        else:
            split_first, split_last, join_first, join_last = \
                self.disjunction, self.conjunction, " and ", " or "

        cfrags = raw.split(split_first)
        ctrans = []

        for cf in cfrags:
            restraints = cf.split(split_last)
            translated = [ self.translate_restraint(r.strip()) for r in restraints ]

            ctrans.append("(%s)" % (join_first.join(translated) ) )

        template = "(%s)" % join_last.join(ctrans)
        return template.format(**{ self.placeholder : table_field })


    def build_sql(self, data):
        '''
        start with assigning data items to the underlying tables

        it seems sqlite really doesn't give a hoot about data types, and
        I don't see a difference in execution time between "like" and "=" -
        I guess sqlite is smart enough to optimize if there is no wild card.

        actually there IS a difference, so we will use 'like' only if there
        is a '%' in the search value.

        So that will make things a lot more straightforward.
        '''
        from_tables = OrderedSet(["refs"])
        restraints = OrderedSet()
        alias_counter = 0

        for field, value in list(data.items()):
            if not value:
                continue

            if field in ("bibtexkey", "title", "year"):
                key = "refs.%s" % field
                restraints.add(self.translate_restraints(key, value))
                continue

            if field == 'reftype':
                from_tables.add('reftypes')
                restraints.add('(reftypes.reftype_id = refs.reftype_id)')
                restraints.add(self.translate_restraints('reftypes.name', value))
                continue

            table = 'uniqid' if field in ("doi", "pmid") else 'optional'
            alias_counter += 1
            alias = "%s%s" % (table[:3], alias_counter)

            from_tables.add('%s as %s' % (table, alias))

            restraints.add('(%s.ref_id = refs.ref_id)' % alias)
            restraints.add('(%s.field_id = %s)' % (alias, self.field_types[field]))
            restraints.add(self.translate_restraints('%s.content' % alias, value))

        # format the sql
        start_clause = """
                   select
                       refs.ref_id
                   from """

        line = '    %s\n'


        sql = textwrap.dedent(start_clause) + '\n'

        for i, clause in enumerate(from_tables):
            if i+1 < len(from_tables):
                clause += ','
            sql += line % clause

        sql += 'where\n'

        for i, r in enumerate(restraints):
            if i > 0:
                r = 'and ' + r
            sql += line % r

        # open('/home/mpalmer/sql.log','w').write(sql)

        return sql.lstrip()


    def search_references(self, data):
        '''
        receive data from dialog, build sql and carry out a search.
        we also save the input for later editing.
        '''
        self._saved_search = data.copy()
        sql = self.build_sql(data)
        results = self._db.execute(sql).fetchvalues()

        # clear out previous search results
        self._db.execute('delete from reflink where branch_id=(?)', [self.search_id])

        for ref_id in results:
            self._db.insert('reflink', dict(ref_id=ref_id, branch_id=self.search_id))

        self._db.commit()
        hub.refresh_tree_item(self.search_node)
        hub.goto_search()


    def reset_search(self):
        '''
        clear out previous results. strangely, the tree
        '''
        self._db.execute('delete from reflink where branch_id=(?)', [self.search_id])
        self._db.commit()

        hub.clear_cache()   # needed to flush out the zombies
        hub.tree.refresh()  # it is possible that stuff was ONLY in search, so we need
                            # to make sure Trash is updated


_export = '''
          search_references
          saved_search
          reset_search
'''

hub.register_many(_export.split(), Search())



