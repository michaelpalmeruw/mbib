import pprint, subprocess, os, glob, shutil
from collections import defaultdict
from utils import locate, validate_bibtex_value, userpath
from config import config

from hub import hub, RefdbError, SqliteDB, IntegrityError

'''
keep the basic stuff here - retrieving references, folders etc. The kind
of thing needed to update the UI. Do clipboard operations, searches, import
etc. elsehwere.
'''

# if dbfile gotten from os.environ, ~ is already expanded
dbfile = os.environ.get("mbib_db", None) or os.path.expanduser(config['paths']['dbfile'])
db_template = "resources/default.sqlite"  # relative path of empty db

class RefDb(object):
    """
    implement the database backend for our wonderful urwid GUI
    """
    root_node = (hub.BRANCH, 1, None)

    uniqids = "pmid doi".split() # special treatment for these guys.

    def __init__(self):
        self.open_db()
        self.branches_only = False
        self.ref_types = dict(self._db.execute('select name,reftype_id from reftypes', \
                                              row_dicts=False).fetchall())
        self.ref_ids = { v:k for k,v in self.ref_types.items() }

        self.field_types = dict(self._db.execute('select name, field_id from fields', \
                                              row_dicts=False).fetchall())

        stmt = "select branch_id, name from branches where parent_id=1"
        rows = self._db.execute(stmt, row_dicts=False).fetchall()

        self.special_branch_nodes = { row[1]:(hub.BRANCH, row[0], 1) for row in rows }
        self.special_branch_ids = dict(rows)
        self.special_branch_ids[1] = 'All'
        self.special_branch_names = { v:k for k, v in list(self.special_branch_ids.items()) }

        # print(self.special_branch_ids)

        # initial display settings
        self.branch_filter_string = ""
        self.sort_by_year = config['preferences'].getboolean("sort_by_year")

        # folder matching follows rule 'lazy like' setting for reference matching
        self.lazy_like = config['search']['lazy_like']

        self.clear_cache()


    def open_db(self):
        '''
        acquire db file, or quit
        '''
        if not os.path.isfile(dbfile):
            mbib_dir = os.environ.get('mbib_dir', '')
            empty_db = os.path.join(mbib_dir, db_template)

            if os.path.isfile(empty_db):
                while True:
                    answer = input("Database file %s not found. Create? (y/n) " % dbfile).lower()[:]
                    if answer in "yn":
                        break
                if answer == 'n':
                    raise SystemExit("No database - exiting")
                # copy empty database file to configured path
                shutil.copy(empty_db, dbfile)
            else:
                raise SystemExit("Can find neither %s nor %s" % (dbfile, empty_db))

        # at this point, the database should be in place
        hub.register('sqlite', SqliteDB(dbfile))
        hub.register('dbfile', dbfile)

        self._db = hub.sqlite


    def item_count(self, table):
        return self._db.execute('select count(*) from %s' % table).fetchvalue()


    def get_named_node(self, node_name):
        '''
        get hold of the special nodes - should be useful for navigation
        '''
        return self.special_branch_nodes.get(node_name, None)


    def _prepopulate_cache(self):
        '''
        prepopulate the parent selection cache to avoid hammering the
        db with too many recursive queries. maybe we can use the same
        approach for some other parts of the cache, too.

        This would seem innocuous even if we filter folders - the cache
        would just contain invisible items.
        '''
        # first we set all nodes to non-selected
        cache = self.cache['parent_selection']
        node_type = hub.REF

        stmt = 'select ref_id from refs'
        refs = self._db.execute(stmt).fetchvalues()

        for ref in refs:
            cache[(node_type, ref)] = 0

        # now we overwrite the selected ones
        stmt =  '''
                with recursive branch_set( i )
                    as (
                        select branch_id from branches where selected = 1
                        union select branch_id from branches, branch_set
                                where branches.parent_id = branch_set.i
                    )
                    select distinct(ref_id) from reflink
                    where branch_id in branch_set
                '''

        refs = self._db.execute(stmt).fetchvalues()

        value = hub.IN_SELECTION

        for ref in refs:
            cache[(node_type, ref)] = value


    def clear_cache(self):
        """
        create or reset cache. There must be a better way of doing this
        than clearing out everything wholesale, but as long as it is
        fast enough, I will leave it alone.
        """
        self.cache = dict(
                        parent={},
                        child_branches={},
                        child_references={},
                        node_text={},
                        node_selection = {},
                        parent_selection = {},
                        ref_index=defaultdict(set))

        self._prepopulate_cache() # this DOES add snappiness.


    def cache_length(self):
        '''
        this seems to be unused
        '''
        1/0
        return sum([len(v) for v in list(self.cache.values())])


    def refresh_tree_item(self, node, refresh_content=True):
        '''
        let's be a bit more considerate with clearing caches - as long as we
        work on an individual folder or reference, it is enough to clear
        the cache selectively. Also, we use .pop(node, None) throughout
        to guard against cache misses.
        '''
        cache = self.cache
        cleared = []

        for stuff in ('node_text', 'node_selection'):
            cleared.append( cache[stuff].pop(node, None) )

        if refresh_content and self.is_branch(node):
            for stuff in ('child_references', 'child_branches'):
                cleared.append( cache[stuff].pop(node, None) )

        if [i for i in cleared if i is not None]:
            hub.tree.refresh()


    def _reflinked_parents(self, ref_id):
        '''
        helper for selection status - we need to check parent
        selection status of cross-listed instances as well.

        do we actually want that? what is the point of highlighting
        cross-listed copies?

        amazing what Sqlite can do.

        BUT, this is a dawg of a query - the database gets hammered with
        it once for every reference, each time the cache is cleared.
        Can we do better than that? Is there a way to pre-populate
        the cache in one fell swoop?
        '''
        # 1/0 - this is still used after pubmed import for example
        # either leave it in, or make sure to update cache everywhere.
        stmt =  '''
                with recursive parent_set(i)
                    as (
                        select parent_id
                        from branches
                        where branch_id in ( select branch_id from reflink where ref_id=(?) )
                        union
                            select parent_id
                            from branches, parent_set
                            where branches.branch_id = parent_set.i
                        )
                    select * from branches
                    where branch_id in parent_set
                    or branch_id in ( select branch_id from reflink where ref_id=(?) )
                '''
        parents = self._db.execute(stmt, [ref_id, ref_id]).fetchall()

        return parents


    def _selection_status(self, node_dict):
        '''
        determine if a node is selected itself, underneath a selected folder,
        or neither.

        Hm. We don't capture cross-listed references. For folders, it is enough
        to just capture the parent folders above this one, but with references
        it isn't.
        '''
        if node_dict['selected'] == hub.SELECTED:
            return hub.SELECTED

        # node is not selected itself. work out whether one of its
        # parents is selected.

        node_id = node_dict.get('ref_id', None)

        if node_id is not None:
            node_type = hub.REF
        else:
            node_type = hub.BRANCH
            node_id = node_dict['branch_id']

        cache_key = (node_type, node_id)  # branch_ids may be the same numbers as ref_ids,
                                          # so we use is_ref in they key to distinguish them

        parent_status = self.cache['parent_selection'].get(cache_key, None)

        if parent_status is not None:
            return parent_status

        # recursive query to determine parent status

        if node_type == hub.REF:
            parents = self._reflinked_parents(node_id)
            #if node_dict['bibtexkey'] == 'Alborn1991':
                #print
                #print parents
                #raw_input()
        else:
            parents = self.get_branches_above(node_id)

        for p in parents:
            if p['selected']:
                status = hub.IN_SELECTION
                break
        else:
            status = 0

        self.cache['parent_selection'][cache_key] = status
        return status


    def store(self, node_dict):
        '''
        store text for each node under a key (class, id, parent) and simply return
        the key. The text is actually a tuple - short and long part. The long part
        is unused with branches.
        '''
        # if node_dict is None
        parent_id = node_dict['parent_id']
        branch_id = node_dict.get('branch_id', None)

        if branch_id is not None:  # this is a folder
            key = (hub.BRANCH, branch_id, parent_id)
            self.cache['node_text'][key] = (node_dict['name'], None)
            self.cache['node_selection'][key] = self._selection_status(node_dict)
            return key

        ref_id = node_dict['ref_id']
        key = (hub.REF, ref_id, parent_id)

        self.cache['ref_index'][ref_id].add(key)
        self.cache['node_text'][key] = (node_dict['bibtexkey'], node_dict['title'])
        self.cache['node_selection'][key] = self._selection_status(node_dict)

        return key


    def toggle_branches_only(self):
        '''
        we no longer need to clean the cache here, I guess -
        refreshing the tree should now be enough.
        '''
        self.branches_only = not self.branches_only


    def get_child_nodes(self, branch):
        '''
        return branches and references contained in a single branch.

        This is the key entry method that bib.py calls for building
        the tree.
        '''
        if self.is_ref(branch):
            return None

        if not self.is_node(branch):
            branch = self.root_node

        branches = self.get_child_branches(branch)

        if self.branches_only:
            return branches

        child_references = self.get_child_references(branch)
        return branches + child_references


    def is_node(self, node):
        return isinstance(node, tuple) and len(node) == 3 and node[0] in (hub.BRANCH, hub.REF)


    def is_ref(self, node):
        return self.is_node(node) and node[0] == hub.REF


    def is_branch(self, node):
        return self.is_node(node) and node[0] == hub.BRANCH


    def get_menu_keys(self, node):
        '''
        items in different locations have different menu options. These
        are defined in a two-layered dict in ui.BibMenu. Here, we work
        out the pair of keys to use for each item.
        '''
        try:
            node_type, node_id, parent_id = node
        except ValueError:
            # this happens if we try to open the menu on 'All' right at the start
            node_type, node_id, parent_id = self.root_node

        if self.is_ref(node):
            return 'ref', self.get_ref_menu_key(parent_id)
        else:
            return 'branch', self.get_branch_menu_key(node_id)


    def get_ref_menu_key(self, branch_id):
        '''
        hm. How do we
        '''
        parents = self.get_branches_above(branch_id, include_start_branch=True)
        folder_ids = [p['branch_id'] for p in parents]

        sbn = self.special_branch_names

        for key in 'Trash Recycled Search'.split():
            if sbn[key] in folder_ids:
                return 'in_' + key.lower()

        return 'default'


    def get_branch_menu_key(self, branch_id):
        '''
        here, we distinguish between trash itself and descendant folders
        analogously for clipboard
        '''
        sbn = self.special_branch_names

        specials = 'All Recycled References Search Trash'.split() + ['Recently added']
        for special in specials:
            if sbn[special] == branch_id:
                return special.lower()

        parents = self.get_branches_above(branch_id)
        parent_ids = [p['branch_id'] for p in parents]

        for special in 'Trash Recycled'.split():
            if sbn[special] in parent_ids:
                return 'in_' + special.lower()

        return 'default'


    def get_branches_above(self, branch_id, include_start_branch=False):
        '''
        is there a point in returning the complete info? Well, let's
        do it anyway, it is always easy to trim it down.
        '''
        stmt = '''
        with recursive parent_set(i)
        as ( select parent_id from branches where branch_id = (?)
                union select parent_id from branches, parent_set
                    where branches.branch_id = parent_set.i
            )
        select * from branches where branch_id in parent_set
        '''

        args = [branch_id]

        if include_start_branch:
            stmt += "or branch_id = (?)"
            args.append(branch_id)

        return self._db.execute(stmt, args).fetchall()


    def get_nodes_above(self, node):
        '''
        get all branches above a node, in our tuple format. node itself is
        also a tuple
        '''
        node_type, node_id, parent_id = node

        branches = self.get_branches_above(node_id, include_start_branch=True)
        branches = [(hub.BRANCH, b['branch_id'], b['parent_id']) for b in branches]

        return branches


    def get_branches_below(self, parent_id):
        '''
        recursively find all branches below a parent.
        '''
        stmt = '''
        with recursive branch_set(i)
        as ( select branch_id from branches where parent_id = (?)
                union select branch_id from branches, branch_set
                    where branches.parent_id = branch_set.i
            )
        select * from branches where branch_id in branch_set;
        '''

        return self._db.execute(stmt, [parent_id]).fetchall()


    def get_nodes_below(self, parent_id, ids_only=False):
        '''
        Har. Now the real fun starts.

        I guess I really will do one preliminary query to obtain the ref_ids though;
        joining each and every of those messy queries below would be too much.

        That would also do away with the need for 'distinct'.

        We will return both branches and references below, so therefore 'nodes_below',
        no longer just 'references_below'.
        '''

        branches_below = self.get_branches_below(parent_id)
        branch_ids = [bb['branch_id'] for bb in branches_below]

        stmt = """
               select distinct refs.*, reftypes.name as reftype
                      from refs, reftypes, reflink
                      where refs.ref_id=reflink.ref_id
                      and reflink.branch_id in (%s)
                      and refs.reftype_id = reftypes.reftype_id
               """

        refs = self._db.execute_qmarks(stmt, [branch_ids+[parent_id]]).fetchall()

        if ids_only:
            ref_ids = [r['ref_id'] for  r in refs]
            return branch_ids, ref_ids

        # full data requested
        return branches_below, self.extend_refs(refs)


    def filter_folders(self, search_string):
        '''
        set a filter and refresh everything.
        '''
        if search_string == self.branch_filter_string:
            return

        self.branch_filter_string = search_string
        hub.clear_cache()
        hub.tree.refresh()

        if search_string != '':
            hub.tree.set_focus(self.special_branch_nodes['References'])


    def reset_filter_folders(self):
        '''
        shortcut for erasing the last active filter
        '''
        self.filter_folders('')


    def _match_folder_name(self, folder_name):
        '''
        check an individual folder name if it matches the currently
        set search string. We emulate SQLite's search patterns - if
        something starts or ends with '%', it is case-insensitve and
        the border doesn't need to align with the haystack. Well,
        do we really want to match case otherwise? I guess so, for
        consistency.

        update - we now also obey the lazy_like setting.
        '''
        bfs = self.branch_filter_string

        if bfs.startswith('%'):
            if bfs.endswith('%'):
                return bfs[1:-1].lower() in folder_name.lower()
            else:
                return folder_name.lower().endswith( bfs[1:].lower() )

        elif bfs.endswith('%'):
            return folder_name.lower().startswith( bfs[:-1].lower() )

        elif self.lazy_like:
            return bfs.lower() in folder_name.lower()

        return folder_name == bfs


    def _folder_gen(self, root_node, include_children):
        '''
        arrange for lazy recursive fetching of ancestor or
        descendant folders
        '''
        yield root_node

        for branch in self.get_branches_above(root_node['branch_id']):
            yield branch

        if include_children:
            for branch in self.get_branches_below(root_node['branch_id']):
                yield branch


    def _belongs_to_matching_folder(self, root_node, include_children=True):
        '''
        match all folders recursively against filter string.
        if the folder itself, any of its parents, or any of
        its descendants match, then we list it.

        we could do some caching here but it seems fast enough;
        db access is already cached.

        we also always include special folders; don't want to hide
        trash or recycle bin.
        '''
        if self.branch_filter_string == '' or root_node['branch_id'] in self.special_branch_ids:
            return True

        for folder in self._folder_gen(root_node, include_children):
            if self._match_folder_name(folder['name']):
                return True
        return False




    def get_child_branches(self, branch):
        '''
        retrieve the child branches of another. In the process, update the cache.

        I guess this is the place to hook a filtering setup into. We would have to
        make the query recursive, which would probably slow things down a wee bit ...

        We would also have to filter separately. Hm. Need to think about how
        we can do this with reasonable efficiency.
        '''
        children = self.cache['child_branches'].get(branch, None)

        if children is not None:
            return children

        weg, branch_id, parent_id = branch

        stmt = "select * from branches where parent_id = (?)"
        branches = self._db.execute(stmt, [branch_id]).fetchall()

        # this is where we must implement the filtering.
        branches = [b for b in branches if self._belongs_to_matching_folder(b)]

        if parent_id is not None:  # Prevent sorting at the top level
            branches.sort(key=lambda b: b['name'].lower())

        branchtuples = self.cache['child_branches'][branch] = [self.store(b) for b in branches]

        return branchtuples


    def toggle_sort(self):
        '''
        switch sorting and refresh display
        '''
        self.sort_by_year = not self.sort_by_year

        hub.clear_cache()
        hub.tree.refresh()


    def get_child_references(self, branch):
        '''
        retrieve child references for branch, updating the cache.

        Let's exclude references that occur along the parents of
        a string-matching sub-folder. Well now - this is really going
        to get tricky.
        '''
        children = self.cache['child_references'].get(branch, None)

        if children is not None:
            return children

        weg, branch_id, parent_id = branch
        special_name = self.special_branch_ids.get(branch_id, None)

        if special_name == "Trash":
            stmt = "select * from refs where ref_id not in (select distinct(ref_id) from reflink)"
            refs = self._db.execute(stmt, []).fetchall()

            for ref in refs:
                ref['parent_id'] = branch_id
                ref['selected'] = 0

        else:
            branch_record = self.get_branch_record(branch_id)
            if self._belongs_to_matching_folder(branch_record, include_children=False):
            # A-Hah. We don't query the year. We really should, though. That would be easier
            # if the year were in the refs table though, not in optional ...

                stmt = """
                select
                    refs.*,
                    reflink.branch_id as parent_id,
                    reflink.selected
                from
                    refs,
                    reflink
                where refs.ref_id = reflink.ref_id
                and reflink.branch_id = (?)
                    """
                refs = self._db.execute(stmt, [branch_id]).fetchall()

            else:
                return []

        # sort according to user settings
        if not self.sort_by_year:
            sort_key=lambda ref: ref['bibtexkey'].lower()
        else:
            sort_key = lambda ref: ( -int(ref['year']), ref['bibtexkey'].lower() )

        refs.sort(key=sort_key)
        reftuples = self.cache['child_references'][branch] = [self.store(r) for r in refs]

        return reftuples


    def get_branch_record(self, branch_id):
        '''
        get the full record for a branch by its id
        '''
        stmt = "select * from branches where branch_id = (?)"
        return self._db.execute(stmt, [branch_id]).fetchone()


    def get_parent_node(self, node):
        '''
        return a branch representing the parent, or none.
        '''
        if not self.is_node(node):
            branch = self.root_node

        parent = self.cache['parent'].get(node)

        if parent is not None:
            return parent

        parent = self.get_branch_record(node[2])

        if parent is None:
            return None

        parent_tuple = self.cache['parent'][node] = self.store(parent)
        return parent_tuple


    def get_branch_title(self, node):
        '''
        key can either represent a branch or a reference. If it is a branch,
        we just invoke get_node_text on it. if it is a reference, we first
        need to invoke get_parent on it.
        '''
        if node[0] == hub.REF:
            node = self.get_parent_node(node)
        return self.get_node_text(node)[0]


    def get_node_display_info(self, key):
        '''
        get both text and selection status.
        backend service for tree display.
        '''
        text = self.get_node_text(key)
        selected = self.cache['node_selection'].get(key, None)
        return text, selected


    def get_node_text(self, key):
        '''
        Load text for key from cache or from database. I guess it is here
        that we need to also retrieve the parental selection info.
        '''
        text_tuple = self.cache['node_text'].get(key, None)

        if text_tuple is not None:
            return text_tuple

        try:
            node_type, node_id, parent_id = key
        except ValueError:
            key = self.root_node
            node_type, node_id, parent_id = key

        if node_type == hub.REF:
            record = self.get_short_ref(key)
            if record is None:
                return ("!!","<reference no longer available>") # "foobared on " + str(key)
            record['parent_id'] = parent_id

        else: # branch
            stmt = "select * from branches where branch_id = (?)"
            record = self._db.execute(stmt, [node_id]).fetchone()

        if record is not None:
            new_key = self.store(record)

            if key != new_key: # how could this be?
                self.cache['node_text'].pop(key, None)
                return ("XXX","XXX")
            else:
                return self.cache['node_text'][key]
        else:
            return ("XXX","XXX")


    def node_short_info(self, key):
        '''
        used by various confirmation dialogs
        '''
        key, title = self.get_node_text(key)

        if title is not None:
            short = "reference '%s'" % key
        else:
            short = "folder '%s'" % key

        return short


    def node_for_bibtexkey(self, bibtexkey):
        '''
        create a node object for a bibtexkey to keep
        those methods happy that expect one.
        '''
        stmt = '''
               select reflink.ref_id, reflink.branch_id
                      from refs, reflink
                      where refs.ref_id = reflink.ref_id
                      and refs.bibtexkey like (?)
                      limit 1
               '''

        result = self._db.execute(stmt, [bibtexkey], row_dicts=False).fetchone()

        if result is None:
            return None

        return (hub.REF, result[0], result[1])


    def bibtexkey_for_node(self, node=None):
        '''
        return the bibtexkey for given node
        '''
        d = self.get_short_ref(node)
        return d['bibtexkey']


    def pdf_filepath(self, bibtexkey):
        '''
        find a pdf filename that matches bibtexkey.
        '''
        path = userpath(config['paths'].get('pdf'))

        if path is not None:
            found = glob.glob(path % bibtexkey)
        else:
            found = []

        if not len(found) and config['paths'].getboolean('pdf_locate'):
            fname = bibtexkey + '.pdf'
            found = locate(r'\/' + fname + '$', case_sensitive=False, as_regex=True)

        if len(found):
            return found[0]
        else:
            return None


    def show_pdf(self, node=None):
        '''
        try to show a pdf file. If not there, show error; if multiple files, show first one.
        if we get annoyed with this, we can always bolt on a menu later
        '''
        bibtexkey = self.bibtexkey_for_node(node)
        path = self.pdf_filepath(bibtexkey)

        if path is None:
            hub.show_errors('PDF file not found')
            return

        # prevent subprocess from messing up the screen ...
        hub.app.set_status('Opening PDF ...')
        fnull = open(os.devnull, 'w')
        subprocess.Popen(["xdg-open", path], stdout=fnull, stderr=fnull)


    def show_pdf_bibtexkey(self, bibtexkey):
        '''
        find and display a pdf file for a bibtexkey
        '''
        fake_node = self.node_for_bibtexkey(bibtexkey)

        if fake_node is None:
            hub.show_errors("reference '%s' not found" % bibtexkey)
            return

        self.show_pdf(fake_node)


    def extend_refs(self, base_records):
        '''
        take a list of base_record that each contain a ref_id (typically a row from
        table refs) and extend it with all matching entries optional and uniquid

        hm. what is missing here is the ref type.
        '''
        lookup = { rr['ref_id'] : dict(rr) for rr in base_records }

        ref_ids = list(lookup.keys())

        for table_name in "optional uniqid".split():
            d = dict(table_name = table_name)

            stmt = """select %(table_name)s.ref_id, fields.name, %(table_name)s.content from fields, %(table_name)s
                            where %(table_name)s.ref_id in (%%s)
                            and %(table_name)s.field_id=fields.field_id""" % d

            vals = self._db.execute_qmarks(stmt, [ref_ids], row_dicts=False).fetchall()

            for ref_id, key, value in vals:
                lookup[ref_id][key] = value

        return list(lookup.values())


    def get_ref_dict(self, ref, history=True):
        '''
        return a complete reference record in a dict. That should not be so hard.

        Can we adapt this to the simultaneous query of multiple records? Because
        I am loath to fire off 3 queries for each reference to be dumped.
        '''
        if history:
            hub.tree.add_to_history(ref)  # ok, so this works.

        base_record = self.get_short_ref(ref)
        extended = self.extend_refs([base_record])[0]

        ref_id, branch_id = ref[1:]

        # now, fish out all folders that contain this reference. Does it make
        # sense to
        stmt = '''
               select branches.*, reflink.ref_id from branches, reflink
                      where reflink.ref_id = (?)
                      and branches.branch_id = reflink.branch_id
                      and branches.branch_id != (?)
               '''
        _branches = self._db.execute(stmt, [ref_id, branch_id]).fetchall()

        # remove entries in special folders - search, clipboard, potentially others
        branches = []
        special_set = set(self.special_branch_ids.keys())

        for branch in _branches:
            parents = self.get_branches_above(branch['branch_id'])
            parents = [ p['branch_id'] for p in parents ]

            intersection = set(parents) & special_set

            if len(intersection) < 3:  # 1 and 3 should normally be there
                branches.append(branch)

        extended['branches'] = branches

        return extended


    def get_short_ref(self, ref=None):
        '''
        ref_id, bibtexkey, title - that's all we need for list display. Actually,
        no, we also need the selected status.
        '''
        if ref is None:
            ref = hub.tree.focus_element()

        node_type, ref_id, branch_id = ref
        assert node_type == hub.REF

        # special treatment only for references that are _immediately_ under
        # trash, not within folders that are in the trash.
        in_trash = branch_id == self.special_branch_names['Trash']

        if in_trash:
            stmt = """
                select
                    refs.*,
                    reftypes.name as reftype
                from
                    refs,
                    reftypes
                where
                    refs.ref_id = (?)
                    and refs.reftype_id = reftypes.reftype_id
                """
            record = self._db.execute(stmt, [ref_id]).fetchone()
            record['selected'] = 0

        else:
            stmt = """
                select
                    refs.*,
                    reflink.selected,
                    reftypes.name as reftype
                from
                    refs,
                    reftypes,
                    reflink
                where
                    refs.ref_id = (?)
                    and reflink.ref_id = refs.ref_id
                    and reflink.branch_id = (?)
                    and refs.reftype_id = reftypes.reftype_id
                """

            record = self._db.execute(stmt, [ref_id, branch_id]).fetchone()

        return record


    def update_field(self, ref_id, field_name, old_value, new_value):
        '''
        We have a whole bunch of different cases to deal with here,
        yet I hope I can keep this together in one method.

        First, some fields are store in the 'refs' main table, whereas
        the rest is stored in 'optional'.

        Next, combinations of new and old values:

            old         new         action
            ------------------------------
            not empty   not empty   update
            not empty       empty   delete
            empty       not empty   insert
            empty           enpty   nothing (doesn't even get here)

        OK, and now we still have to make this work with the new
        caching scheme. I guess this is something for a fresh,
        bright morning.
        '''
        # print ref_id, field_name, old_value, new_value
        if not validate_bibtex_value(new_value):
            return "unbalanced braces in field %s" % field_name

        table_name = 'uniqid' if field_name in self.uniqids else "optional"
        d = dict(table_name=table_name)

        if field_name == 'reftype':
            if new_value is not None:
                new_id = self.ref_types.get(new_value.lower(), None)

            if new_value is None or new_id is None:
                msg = "invalid reference type '%s'\n\n" % new_value
                msg += 'valid types are: %s' % ', '.join(sorted(self.ref_types.keys()))
                return msg

            self._db.execute('update refs set reftype_id=(?) where ref_id=(?)', [new_id, ref_id])

        elif field_name in ('bibtexkey', 'title', 'year'):
            # let's see what chchappens if we violate constraints.
            if not new_value:
                return "%s cannot be empty" % field_name
            stmt = 'update refs set %s=(?) where ref_id=(?)' % field_name
            try:
                self._db.execute(stmt, [new_value, ref_id])
            except IntegrityError as e:
                return "update of %s to '%s' failed with IntegrityError" % (field_name, new_value)

        elif field_name not in self.field_types:
            return

        elif new_value is None:     # old_value is not None - delete it.
            # cargo cult programming - I really have forgotten how this works.

            stmt = '''
                    delete from %(table_name)s where exists
                        (
                            select null from fields
                            where fields.name=(?)
                            and fields.field_id=%(table_name)s.field_id
                            and %(table_name)s.ref_id=(?)
                        )
                   ''' % d

            self._db.execute(stmt, [field_name, ref_id])

        elif old_value is None:
            stmt = 'insert into %(table_name)s values (?,?,?)' % d
            self._db.execute(stmt, [ref_id, self.field_types[field_name], new_value])

        else: # update
            stmt = 'update %(table_name)s set content=(?) where ref_id=(?) and field_id=(?)' % d
            self._db.execute(stmt, [new_value, ref_id, self.field_types[field_name]])


    def update_reference(self, old_data, new_data, add_reference=False):
        '''
        invoked by RefEdit dialog, but also indirectly by the add reference
        dialog.

        If we do have errors, do we commit the non-erroneous changes
        anyway? I would say yes.
        '''
        ref_id = old_data['ref_id']
        errors = []
        updates = False

        for key, value in list(new_data.items()):
            new_value = value.strip() or None
            old_value = old_data.get(key, None)

            if new_value != old_value:
                error = self.update_field(ref_id, key, old_value, new_value)
                if error is None:
                    updates = True
                else:
                    errors.append(error)

        if updates:
            self._db.commit()
            # also update store.
            # Ha, ha, ha. Turns out that is not so easy -
            # references can occur in multiple places, and there
            # is no unique parent_id associated with it.
            s = self.cache['ref_index'][ref_id]

            while s:
                key = s.pop()
                self.cache['node_text'].pop(key, None)

            hub.tree.refresh()

        if not add_reference:
            if errors:
                hub.show_errors(errors)  # show errors right here
        else: # return any errors.
            return errors


    def update_branch(self, branch, old_name, new_name):
        '''
        change name of a folder
        '''
        _type, branch_id, parent_id = branch
        assert _type == hub.BRANCH

        error = None

        if parent_id in (1, None):
            error = "Folder '%s' is protected and can't be renamed" % old_name
        elif new_name == "":
            error = "Folder name can't be empty"

        if error is not None:
            hub.show_errors(error, height=10)
            return

        stmt = "update branches set name=(?) where branch_id=(?)"
        self._db.execute(stmt, [new_name, branch[1]])
        self._db.commit()

        # also flush out the old stored text
        self.refresh_tree_item(branch, False)
        hub.tree.add_to_history(branch)


    def exists_folder(self, parent, subfolder_name):
        '''
        check if a folder name is already present inside a target parent folder.
        parent may be a node or just a branch_id.
        '''
        try:
            parent_id = int(parent)
            stmt = "select parent_id from branches where branch_id = (?)"
            ppid = self._db.execute(stmt, [parent_id]).fetchvalue()
            parent = (hub.BRANCH, parent_id, ppid)
        except TypeError:
            pass # assume it's already a tuple

        assert hub.is_branch(parent)

        branch_names = [hub.get_branch_title(b) for b in self.get_child_branches(parent)]
        return subfolder_name in branch_names


    def flatten_folder(self, node=None):
        '''
        - recursively collect all references below this folder
        - empty out this folder
        - insert the collect the references back into it.
        '''
        if node is None:    # invocation from menu will trigger this case
            node = hub.tree.focus_element()

        assert hub.is_branch(node)
        node_id = node[1]

        # collect all references from nested folders
        stmt = '''
        with recursive branch_set(i)
        as ( select branch_id from branches where parent_id = (?)
                union select branch_id from branches, branch_set
                    where branches.parent_id = branch_set.i
            )
        select distinct(ref_id) from reflink
        where branch_id in branch_set
        '''
        nested_references = self._db.execute(stmt, [node_id]).fetchvalues()

        # now, delete all nested folders
        stmt = '''delete from branches where parent_id=(?)'''
        self._db.execute(stmt, [node_id])

        # collect any remaining references
        stmt = "select ref_id from reflink where branch_id=(?)"
        direct_references = self._db.execute(stmt, [node_id]).fetchvalues()

        # finally, insert all references directly into parent, omitting duplicates
        remaining = set(nested_references) -  set(direct_references)
        for ref in remaining:
            self._db.insert('reflink', dict(ref_id=ref, branch_id=node_id, selected=0))

        # finish up
        self._db.commit()
        hub.clear_cache()
        hub.tree.refresh()



# we should expose some methods globally, to make menu responses easier.
_db = RefDb()

hub.register('coredb', _db)

_export = '''
          clear_cache
          extend_refs
          filter_folders
          flatten_folder
          get_branch_title
          get_child_nodes
          get_menu_keys
          get_named_node
          get_node_display_info
          get_node_text
          get_nodes_above
          get_parent_node
          get_ref_dict
          node_for_bibtexkey
          is_branch
          is_ref
          item_count
          node_short_info
          refresh_tree_item
          reset_filter_folders
          show_pdf
          show_pdf_bibtexkey
          toggle_branches_only
          toggle_sort
          update_branch
          update_reference
'''

hub.register_many(_export.split(), _db)




