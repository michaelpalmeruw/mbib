'''
implement trash operations.

this must be simplified. allowing whole folders to survive in the
trash creates no end of headaches. what we will do instead is
to trash the folders instantly. Any orphaned references will then
show up in the trash, but without any hierarchy. They can then
be recovered into the Recycled folder, which gives them a new home,
and then moved about from there as usual.
'''

from hub import hub, RefdbError, IntegrityError

class Trashcan(object):

    def __init__(self):
        self._db = hub.sqlite
        self.trash_node = self.special_branch_nodes['Trash']
        self.recycled_node = self.special_branch_nodes['Recycled']

    def __getattr__(self, att):
        return getattr(hub.coredb, att)

    def empty_trash(self):
        '''
        like the man sez. How do we proceed? No more folders, so therefore
        all we have to do is delete references no longer represented in
        reflink.
        '''
        refs_before = self.item_count('refs')

        stmt = "delete from refs where ref_id not in (select distinct(ref_id) from reflink)"
        self._db.execute(stmt)
        self._db.commit()

        self.refresh_tree_item(self.trash_node)

        refs_deleted = refs_before - self.item_count('refs')
        refs_suffix = '' if refs_deleted == 1 else 's'

        hub.app.set_status('Deleted %s reference%s' % (refs_deleted, refs_suffix))


    def delete_node(self, node=None):
        '''
        delete either a folder or a reference. In the case of folders,
        we rely on SQLite cascading to delete nested content.
        '''
        refs_before = self.item_count('reflink')
        folders_before = self.item_count('branches')

        if node is None:    # invocation from menu will trigger this case
            node = hub.tree.focus_element()

        parent = self.get_parent_node(node)

        node_type, node_id, parent_id = node

        if node_type == hub.BRANCH:
            if node_id in self.special_branch_ids:
                hub.show_errors('This folder is protected')
                return

            stmt = "delete from branches where branch_id=(?)"
            values = [node_id]
        else:
            stmt = "delete from reflink where ref_id=(?) and branch_id=(?)"
            values = [node_id, parent_id]

        self._db.execute(stmt, values)
        self._db.commit()

        hub.tree.set_focus(parent)
        hub.tree.add_to_history(parent) # does this make sense? I suppose so.

        hub.coredb.clear_cache()
        hub.tree.refresh()

        rdel = refs_before - self.item_count('reflink')
        fdel = folders_before - self.item_count('branches')


        joiner = " and " if fdel > 0 and rdel > 0 else ""

        if fdel > 0:
            if fdel == 1:
                fs = "1 folder"
            else:
                fs = "%s folders" % fdel
        else:
            fs = ""

        if rdel > 0:
            if rdel == 1:
                rs = "1 reference"
            else:
                rs = "%s references" % rdel
        else:
            rs = ""

        hub.app.set_status('Deleted %s%s%s' % (fs, joiner, rs))


    def _delete_other_instances(self, ref_ids, branch_ids):
        '''
        delete any duplicates of a reference. This should be the common
        backend for single references, folders, and selections.
        '''
        stmt = 'delete from reflink where ref_id in (%s) and branch_id not in (%s)'

        c = self._db.execute_qmarks(stmt, [ref_ids, branch_ids])

        if c.rowcount > 0:
            self._db.commit()
            self.clear_cache()
            hub.tree.refresh()


    def delete_other_instances(self, node):
        '''
        here, we figure out what references exactly should be
        deleted from the node that was passed.

        A-hah. We need to be careful here - we cannot do this
        recursively with folders, because we might have multiple
        instances within the folder, and then all would get killed.

        Or, we would have to use some recursive query first to
        figure out exactly what would be preserved.
        '''
        if hub.is_ref(node):
            ref_id, branch_id = node[1:]
            self._delete_other_instances([ref_id], [branch_id])
            return

        # so it's a folder ...
        branch_id = node[1]
        subfolder_ids, ref_ids = self.get_nodes_below([branch_id], ids_only=True)
        self._delete_other_instances(ref_ids, subfolder_ids + [branch_id])


    def erase_node(self, node=None):
        '''
        completely erase a reference. In this case, we just delete from the refs table
        and let it propagate to reflink etc. Yes, it works from the command line.
        '''
        if node is None:    # invocation from menu will trigger this case
            node = hub.tree.focus_element()

        node_type, node_id, parent_id = node
        parent = self.get_parent_node(node)

        if node_type == hub.BRANCH:
            hub.show_errors('Cannot erase folders')
            return

        #stmt = "delete from refs where ref_id=(?)"
        #Well, why take this aggressive approach? Why not just leave it in the trashcan?
        #Let's do that instead.

        stmt = "delete from reflink where ref_id=(?)"

        self._db.execute(stmt, [node_id])
        self._db.commit()

        hub.tree.set_focus(parent)
        hub.tree.add_to_history(parent) # does this make sense? I suppose so.

        hub.coredb.clear_cache()
        hub.tree.refresh()

        hub.app.set_status('Moved one reference to trash')


    def recycle_trash(self):
        '''
        recover all items from the trash and stuff it into the Recycled folder.
        '''
        refs_before = self.item_count('reflink')

        recycled_id = self.recycled_node[1]
        stmt = "select ref_id from refs where ref_id not in (select distinct(ref_id) from reflink)"
        ref_ids = self._db.execute(stmt).fetchvalues()

        if not len(ref_ids):
            return

        for ref_id in ref_ids:
            self._db.insert('reflink', dict(ref_id=ref_id, branch_id=recycled_id))

        self._db.commit()
        hub.clear_cache()
        hub.tree.refresh()

        refs_recycled = self.item_count('reflink') - refs_before
        refs_suffix = '' if refs_recycled == 1 else 's'

        hub.app.set_status('Recycled %s reference%s' % (refs_recycled, refs_suffix))


    def _empty_folder(self, folder_id):
        '''
        used with at least two folders (recycled and recently added)
        '''
        refs_before = self.item_count('reflink')

        stmt = "delete from reflink where branch_id = (?)"
        c = self._db.execute(stmt, [folder_id])
        deleted = c.rowcount

        if deleted == 0:
            return

        self._db.commit()

        hub.clear_cache()
        hub.tree.refresh()

        refs_deleted = refs_before - self.item_count('reflink')

        if refs_deleted > 0:
            refs_suffix = '' if refs_deleted == 1 else 's'
            hub.app.set_status('Deleted %s reference%s' % (refs_deleted, refs_suffix))


    def empty_recycled(self):
        '''
        delete stuff from recycle bin again
        '''
        self._empty_folder(self.recycled_node[1])


_export = '''
          delete_node
          delete_other_instances
          erase_node
          empty_recycled
          _empty_folder
          empty_trash
          recycle_trash
'''

hub.register_many(_export.split(), Trashcan())



