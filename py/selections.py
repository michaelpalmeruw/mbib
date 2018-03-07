'''
implement selecting references and moving them around.
'''
import os
from hub import hub, RefdbError, IntegrityError
from config import config
from utils import xclip


class Selections(object):

    def __init__(self):
        self._db = hub.sqlite


    def __getattr__(self, att):
        return getattr(hub.coredb, att)


    def toggle_select(self, node=None):
        '''
        toggle selection status of reference or folder.

        - first, check if the current node is inside a folder that is currently selected.
          if it is, tell them that and exit.

        - if no parent is selected, then toggle selection status.

          When a folder is selected, we also reset the selections of all items below.

        Hm. How do we deal with stuff in the trash? With references, we have no reflink
        entries, so we have no place to store the 'selected' attribute.

        Darn. Why did I feel the need again to change this around? What exactly was wrong
        with having the selected attribute on the reference?
        '''
        if node is None:    # invocation from menu will trigger this case
            node = hub.tree.focus_element()

        node_type, node_id, parent_id = node
        is_branch = node_type == hub.BRANCH

        parents = self.get_branches_above(parent_id, include_start_branch=True)

        selected = sum([p['selected'] for p in parents])

        if selected:
            hub.show_errors('This item is inside a selected folder and cannot be individually selected or deselected.')
            return

        if is_branch:
            if node_id in self.special_branch_ids:
                hub.show_errors('This folder is protected and cannot be moved or copied')
                return

            this_branch = self._db.execute('select * from branches where branch_id=(?)', [node_id]).fetchone()
            currently_selected = this_branch['selected']

            if currently_selected == 0:   # going to be 1 - deselect all individually selected
                                          # descendants. Is that sensible? Let's try it out.
                # deselect references.
                stmt = '''
                with recursive branch_set( i )
                    as ( select branch_id from branches where parent_id = (?)
                         union select branch_id from branches, branch_set
                                where branches.parent_id = branch_set.i
                        )
                    update reflink
                    set selected = 0
                    where selected = 1
                    and branch_id in branch_set or branch_id = (?);
                '''
                self._db.execute(stmt, [node_id, node_id])

                # deselect branches
                stmt = '''
                with recursive branch_set( i )
                    as ( select branch_id from branches where parent_id = (?)
                         union select branch_id from branches, branch_set
                                where branches.parent_id = branch_set.i
                        )
                    update branches
                    set selected = 0
                    where selected = 1
                    and branch_id in branch_set;
                '''
                self._db.execute(stmt, [node_id])

            # update branch itself
            stmt = 'update branches set selected=(?) where branch_id=(?)'
            self._db.execute(stmt, [1-currently_selected, node_id])

        else:
            stmt =  '''
                    update reflink
                    set selected = case selected when 1 then 0 else 1 end
                    where ref_id = (?)
                    and branch_id = (?)
                    '''
            self._db.execute(stmt, [node_id, parent_id])

        self._db.commit()

        hub.clear_cache()
        hub.tree.refresh()


    def add_folder(self, parent, new_name):
        '''
        not really a clipboard operation itself, but related.

        Should we guard against duplicated names in same folder? I guess so.
        '''
        if not new_name:
            hub.show_errors("Folder name cannot be empty")
            return

        if not hub.is_branch(parent):
            hub.show_errors("Cannot create folder inside a reference")
            return

        parent_id = parent[1]

        if self.exists_folder(parent, new_name):
            hub.show_errors("Subfolder '%s' already exists - aborting" % new_name)
            return

        c = self._db.insert('branches', dict(name=new_name, parent_id=parent_id))
        new_id = c.lastrowid
        self._db.commit()

        # clearing the cache shouldn't be needed, but it is - deleted folder nodes
        # somehow linger, and if an id gets reused, the zombies reappear
        hub.clear_cache()
        hub.tree.refresh()

        # now, we should be able to construct the new node signature without going
        # back to the database
        new_node = (hub.BRANCH, new_id, parent_id)
        hub.tree.set_focus(new_node)
        hub.tree.add_to_history(new_node)


    def move_selected(self, node=None):
        '''
        move selected items into current folder. Reset selected to 0.
        '''
        if node is None:    # invocation from menu will trigger this case
            node = hub.tree.focus_element()

        assert hub.is_branch(node)
        node_id = node[1]

        # get hold of all selected folders
        stmt = 'update branches set parent_id=(?), selected=0 where selected=1'
        c = self._db.execute(stmt, [node_id])
        moved_items = c.rowcount

        errors = 0

        stmt = '''
               update reflink set branch_id=(?), selected = 0
               where selected=1
               and not ref_id in
                   (select ref_id from reflink where branch_id=(?))
               '''
        try:
            c = self._db.execute(stmt, [node_id, node_id])
            moved_items += c.rowcount
        except IntegrityError:
            hub.show_errors('Oopsie - something bad just happened')

        if not moved_items:
            hub.show_errors('Nothing was moved')
        else:
            self._db.commit()
            hub.clear_cache()
            hub.tree.refresh()

    def count_selected_items(self):
        b = self._db.execute('select count(*) from branches where selected=1').fetchvalue()
        r = self._db.execute('select count(*) from reflink where selected=1').fetchvalue()
        return b + r

    def copy_selected(self, node=None):
        '''
        copy selected references and folders into current folder. Should we also
        deselect? Because if we don't, it's less work, but might be annoying.

        Let's wait and see. Actually, we need a 'deselect all' anyway, so we
        might just call that at the end.
        '''
        if node is None:    # invocation from menu will trigger this case
            node = hub.tree.focus_element()

        assert hub.is_branch(node)
        node_id = node[1]

        # get hold of all selected folders
        stmt = 'select * from branches where selected=1'
        branches = self._db.execute(stmt).fetchall()

        errors = []
        success = 0

        for branch in branches:
            b = (hub.BRANCH, branch['branch_id'], branch['parent_id'])
            try:
                new_id = self.clone_branch(b, node_id)
                success += 1
            except RefdbError as e:
                errors.append(e.message)


        # now on to the references
        stmt = 'select ref_id from reflink where selected=1'
        ref_ids = self._db.execute(stmt).fetchvalues()

        failed_refs = 0

        for ref_id in ref_ids:
            try:
                self._db.insert('reflink', dict(ref_id=ref_id, branch_id=node_id))
                success += 1
            except IntegrityError:
                failed_refs += 1

        if success:
            self._db.commit()
            hub.clear_cache()
            hub.tree.refresh()

        if failed_refs:
            suffix = '' if failed_refs==1 else 's'
            errors.append("%s duplicate reference%s not copied" % (failed_refs, suffix))

        if errors:
            hub.show_errors(errors)

        if success == len(errors) == 0:
            hub.show_errors('Nothing was selected')


    def clone_branch(self, branch, new_parent_id):
        '''
        clone branch identified by branch_id and append it to new_parent_id

        I guess we must make sure that the branch is not already in
        or below the new parent id.

        Also, we should check that the new parent does not already contain a folder
        of the same name.
        '''
        branches_above = self.get_branches_above(new_parent_id, include_start_branch=True)
        above_ids = [b['branch_id'] for b in branches_above]

        branch_id = branch[1]

        if branch_id in above_ids:
            raise RefdbError("can't insert folder underneath itself")

        item_name = self.get_branch_title(branch)

        if self.exists_folder(new_parent_id, item_name):
            raise RefdbError("target folder already contains folder with the same name")

        stmt = "select name,branch_id from branches where branch_id = (?)"
        old_data = self._db.execute(stmt, [branch_id]).fetchone()

        return self._clone_branch(old_data, new_parent_id)


    def _clone_branch(self, old_data, new_parent_id):
        '''
        - create a new branch with old name and new parent_id
        - for all references within orig, create copies in reflink
          that point to new branch
        - collect cloned_ids for all directories within orig by invoking
          _clone_branch recursively
        - append each of these to new branch
        - return new branch id

        we probably shouldn't call .commit(); doing it only once at the end
        of the whole operation should speed things up.
        '''
        d = dict(name=old_data['name'], parent_id=new_parent_id)
        new_branch_id = self._db.insert('branches', d).lastrowid
        old_branch_id = old_data['branch_id']

        stmt = 'select ref_id from reflink where branch_id=(?)'
        ref_ids = self._db.execute(stmt, [old_branch_id]).fetchvalues()

        for ref_id in ref_ids:
            self._db.insert('reflink', dict(ref_id=ref_id, branch_id=new_branch_id))

        stmt = "select name, branch_id from branches where parent_id=(?)"
        folders = self._db.execute(stmt, [old_branch_id]).fetchall()

        for folder in folders:
            self._clone_branch(folder, new_branch_id)

        return new_branch_id


    def select_refs(self, node=None):
        '''
        select references immediately in this folder, but not sub-folders
        '''
        if node is None:    # invocation from menu will trigger this case
            node = hub.tree.focus_element()

        assert hub.is_branch(node)
        node_id = node[1]

        stmt = 'update reflink set selected = 1 where branch_id=(?) and selected = 0'
        c = self._db.execute(stmt, [node_id])

        if c.rowcount != 0:
            self._db.commit()
            hub.clear_cache()
            hub.tree.refresh()


    """
    def select_recursively(self, node=None):
        '''
        select references recursively in folder and subfolders. Is this actually useful?
        We can simply select the entire folder, and I think the result is pretty much the same.
        Well, no, if we copy or move folders, the structure will be preserved.

        We could of course implement a "flattening" function to be invoked on a folder.
        That might make more sense, might it not? Could be applied to both clones
        and originals.

        Flattening is now implemented in core_db, and this method has been retired.
        '''
        if node is None:    # invocation from menu will trigger this case
            node = hub.tree.focus_element()

        assert hub.is_branch(node)
        node_id = node[1]

        stmt = '''
        with recursive branch_set(i)
        as ( select branch_id from branches where parent_id = (?)
                union select branch_id from branches, branch_set
                    where branches.parent_id = branch_set.i
            )
        update reflink
        set selected=1
        where selected=0
        and (branch_id in branch_set or branch_id=(?))
        '''
        c = self._db.execute(stmt, [node_id, node_id])

        if c.rowcount != 0: # why the hell does rowcount not respond? It is -1 - go figure. Is that because of recursion?
            self._db.commit()
            hub.clear_cache()
            hub.tree.refresh()

    """

    def _update_or_delete_selected(self, stmt):
        '''
        shared backend for simple operations on all selected items
        '''
        affected = 0

        for table in ("reflink", "branches"):
            c = self._db.execute(stmt % table)
            affected += c.rowcount

        if affected:
            self._db.commit()
            hub.clear_cache()
            hub.tree.refresh()


    def deselect_all(self):
        '''
        like the man says
        '''
        self._update_or_delete_selected("update %s set selected = 0 where selected = 1")


    def delete_selected(self):
        '''
        delete all selected folders and references
        '''
        self._update_or_delete_selected('delete from %s where selected=1')


    def get_selected_refs(self):
        '''
        get a list of all references that are either selected themselves or
        reside underneath a selected folder.

        We keep the branch_ids around, too, we might need them sometime.
        This does mean, however, that ref_ids might be duplicates.
        '''
        stmt =  '''
                with recursive branch_set( i )
                    as (
                        select branch_id from branches where selected = 1
                        union select branch_id from branches, branch_set
                                where branches.parent_id = branch_set.i
                    )
                    select ref_id, branch_id from reflink
                    where branch_id in branch_set or selected=1
                '''
        return self._db.execute(stmt, row_dicts=False).fetchall()


    def get_selected_with_keys(self):
        '''
        get refids and bibtexkeys both, return them in a dict
        '''
        raw = self.get_selected_refs()

        if len(raw) == 0:
            return []

        ref_ids = [r[0] for r in raw]

        stmt = "select * from refs where ref_id in (%s)"
        records = self._db.execute_qmarks(stmt, [list(ref_ids)]).fetchall()

        for r in records:
            r['reftype'] = self.ref_ids[r.pop('reftype_id')]

        return records


    def get_selected_refs_full(self):
        '''
        get the full monty for each selected reference.
        '''
        stubs = self.get_selected_with_keys()
        return hub.extend_refs(stubs)


    def get_selected_bibtexkeys(self):
        '''
        needed by latex push operations and xclip
        '''
        data = self.get_selected_with_keys()

        if len(data) == 0:
            hub.show_errors('Nothing was selected')
            return data

        keys = [ d['bibtexkey'] for d in data ]
        return sorted(keys)


    def ref_xclip(self):
        '''
        copy key of reference in current node to clipboard
        '''
        key = self.bibtexkey_for_node()
        xclip(key)


    def xclip_selected(self):
        '''
        copy bibtexkeys to clip board. Maybe one day we can generalize this to
        copy other parts also.
        '''
        data = self.get_selected_bibtexkeys()
        if len(data):
            xclip(','.join(data))


    def mail_selected(self):
        '''
        send pdf files for all selected references, as far as available
        '''
        # hub.app.set_status('locating PDF files for email')

        ref_ids = [s[0] for s in self.get_selected_refs()]
        stmt = "select bibtexkey from refs where ref_id in (%s)"
        keys = self._db.execute_qmarks(stmt, [list(ref_ids)]).fetchvalues()

        # I guess we want to keep track of which PDF files were actually found.
        # so, we don't just filter
        paths = [(key, self.pdf_filepath(key)) for key in keys]
        # print(list(paths)) that looks good.

        attach_list = []
        missing_list = []

        for key, path in paths:
            if path is None:
                missing_list.append(key)
            else:
                attach_list.append(path)

        if not len(attach_list):
            hub.show_errors("No PDF files found for selected reference(s)")
            return

        # hub.app.set_status('composing email') does not show. Need to understand this some time.

        cmd = ["xdg-email"]
        cmd.append('--subject "%s"' % config['email'].get('subject', 'PDF files'))

        body = config['email'].get('body', 'Please see attached')
        if len(missing_list):
            body += '. PDFs not found for: %s' % ", ".join(missing_list)

        cmd.append('--body "%s"' % body)

        for fn in attach_list:
            cmd.append('--attach "%s"' % str(fn))

        cmd = ' '.join(cmd)
        os.system("%s > /dev/null 2> /dev/null" % cmd)


_export = '''
          add_folder
          copy_selected
          count_selected_items
          delete_selected
          deselect_all
          get_selected_bibtexkeys
          get_selected_refs
          get_selected_refs_full
          mail_selected
          move_selected
          ref_xclip
          select_refs
          toggle_select
          xclip_selected
          '''

hub.register_many(_export.split(), Selections())

if __name__ == '__main__':
    import pprint
    sel = Selections()
    s = sel.get_selected_with_keys()
    pprint.pprint(s)
    print()

    s = sel.get_selected_refs_full()
    pprint.pprint(s)

