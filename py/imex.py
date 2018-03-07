'''
import export

I guess it would be good to export the tree structure to JabRef as well. This would
help with navigation inside JabRef. IIRC we already had this working.
'''
import re, string, pprint, os, traceback, textwrap
#from unidecode import unidecode

from pubmed_retrieval import PubmedImporter, PubmedError
from tigkas_bibtexparser import Parser as BibtexParser
from hub import hub, RefdbError, IntegrityError
from html_formatter import OlFormatter
from urwidtools import dialog
from AsciiDammit3 import asciiDammit
from urllib.request import Request, urlopen

from config import config
from utils import writefile

class Imex(object):

    name_re = re.compile('[A-Za-z\.]+')

    key_width = 12
    field_template = "    %s = {%s},"
    value_indent = " " * 20 # match position of first brace

    debracketize = re.compile(r"[\{\}\(\)\[\]]")

    bibtex_wrapper = textwrap.TextWrapper(
                                width=100,
                                initial_indent=value_indent, # gets stripped later
                                subsequent_indent=value_indent,
                                drop_whitespace=True,
                                break_long_words=False,
                                replace_whitespace=True,
                                break_on_hyphens=False)

    def __init__(self):
        self._db = hub.sqlite
        self.recently_added_id = self.special_branch_names['Recently added']
        self.export_wrapped = config['bibtex'].getboolean('export_wrapped')
        self.standardize_key = config['bibtex'].getboolean('standardize_key')
        self.ascii_key = config['bibtex'].getboolean('ascii_key')


    def __getattr__(self, att):
        return getattr(hub.coredb, att)


    def clear_recent(self):
        '''
        we reuse code defined in trashcan
        '''
        hub._empty_folder(self.recently_added_id)


    def _import_records(self, node, records, progress_bar, base_level=0):
        '''
        shared backend for insertion of references retrieved from
        pubmed or parsed from bibtex
        '''
        errors = []

        progress_bar.set_title("Adding references to database")
        rest_scale = 90 - base_level

        for i, record in enumerate(records):
            more_errors = self.add_reference(record, node, single_mode=False)
            errors.extend(more_errors)
            progress = base_level + rest_scale * (i+1) / len(records)
            progress_bar.set_completion(progress)

        progress_bar.set_title("Committing database changes")

        self._db.commit()
        progress_bar.set_completion(100)

        # hub.refresh_tree_item(node)
        # we need to refresh the tree in order to update the Imported pseudo-folder
        hub.clear_cache()
        hub.tree.refresh()

        if len(errors):
            hub.show_errors(errors)

        refs_imported = self.item_count('refs') - self.ref_count_before
        suffix = '' if refs_imported == 1 else 's'

        hub.app.set_status('Imported %s reference%s' % (refs_imported, suffix))


    def _file_or_text(self, raw_info):
        '''
        try to open as file, if it fails, return text
        '''
        try:
            text = open(raw_info).read()
        except FileNotFoundError:
            text = raw_info
        return text


    def import_pubmed(self, node, raw_info):
        '''
        node is the current folder. we leave the validation
        of raw_ids to the importer

        How much of this code can we reuse for importing BibTex?
        The tail end.
        '''
        raw_ids = self._file_or_text(raw_info)

        progress_bar = dialog.ProgressBar()
        progress_bar.set_title("importing from Pubmed")
        progress_bar.show()

        self.ref_count_before = self.item_count('refs')

        try:
            importer = PubmedImporter(raw_ids, progress_bar)
            records, failed_pmids = importer()
        except PubmedError as e:
            hub.show_errors(e.message)
            progress_bar.dismiss()
            return

        if len(failed_pmids):
            msg = 'nothing retrieved for the following identifiers: %s' % ', '.join(failed_pmids)
            hub.show_errors(msg)

        self._import_records(node, records, progress_bar, base_level=20)


    def import_bibtex(self, node, raw_info):
        '''
        parse inputted bibtex and create references from it.

        raw_info could be a file name or bibtex text
        '''
        raw_bibtex = self._file_or_text(raw_info)

        try:
            p = BibtexParser(raw_bibtex)
            records = p()
        except Exception as e:
            raise
            hub.show_errors(getattr(e, 'message', 'bibtexparser foobared'))
            return

        if len(records) == 0:
            msg = 'No records recognized in input'
            hub.show_errors(msg)
            return

        # OK doke, we have at least one valid record. Now what? Just construct
        # a new progress bar and invoke the common backend.
        progress_bar = dialog.ProgressBar()
        progress_bar.show()
        self.ref_count_before = self.item_count('refs')
        self._import_records(node, records, progress_bar)


    def random_string(self, length=8):
        '''
        uuid uses lowercase and digits - 36 characters per position
        '''
        from uuid import uuid4
        return str(uuid4()).replace('-','')[:length]


    def make_bibtex_key(self, data):
        '''
        if bibtexkey is faulty, missing, or discarded according to
        ini-file preference, concoct a new one.
        '''
        if not self.standardize_key:
            btk = data.get('bibtexkey', None)
        else:
            btk = None

        if btk is None:
            # firstlast is an auxiliary field constructed during Pubmed import
            firstlast = data.get('firstlast', None)

            if firstlast is None:  # for example bibtex import
                author = data.get('author')
                if not author:  # no key, no author - we give up
                    return self.random_string()

                author = self.debracketize.sub("", author)

                first_author = author.split(' and ')[0].strip()

                if ',' in first_author:  # last names are clearly indicated
                    firstlast = first_author.split(',')[0]

                else: # we have to guess at the last name
                    firstlast = self.name_re.findall(first_author)[-1]

            btk = firstlast.strip().replace(' ','_') + str(data.get('year', ''))

        if self.ascii_key:
            btk = asciiDammit(btk)  # remove accented characters - hard to type on English keyboards

        stmt = 'select bibtexkey from refs where bibtexkey like (?)'
        existing_keys = self._db.execute(stmt, [btk + '%']).fetchvalues()

        suffixes = [''] + list(string.ascii_lowercase)

        for suffix in suffixes:
            test_key = btk + suffix

            if not test_key in existing_keys:
                return test_key

        # if we get here, we have a REALLY common name ... more Chin's than a Singapore phone book ...
        return '%s-%s' % (btk, self.random_string(4))


    def add_reference(self, new_data, node=None, single_mode=True):
        '''
        What do we do here if constraints are violated? I think in the case of
        missing or reduplicated bibtex keys we just concatenate a random string
        and try again. For title, we can just supply a dummy title.

        single_mode: we also use this as a backend for importers, so we
        don't commit and display errors right here in that case.
        '''
        if node is None:
            node = hub.tree.focus_element()
        assert hub.is_branch(node)

        values = [_f for _f in list(new_data.values()) if _f]

        if not values:
            hub.show_errors("No data provided - aborting.")
            return

        # I guess from here we will insert something, even if it is crap.
        # we just keep track of the errors and show them at the end.
        errors = []

        orig_bibtexkey = new_data.get('bibtexkey')
        new_bibtexkey = new_data['bibtexkey'] = self.make_bibtex_key(new_data)

        #if orig_bibtexkey and orig_bibtexkey != new_bibtexkey: don't nag the user
            #hub.show_message("bibtexkey '%s' changed to '%s'" % (orig_bibtexkey, new_bibtexkey))

        new_data['title'] = new_data['title'].rstrip('.')

        if not new_data['title']:
            new_data['title'] = "Title can't be empty -- please fix"
            errors.append(new_data['title'])

        if new_data['reftype'] not in self.ref_types:
            errors.append("reftype was empty or faulty - set to 'article'")
            new_data['reftype'] = 'article'

        # at this point, we should have everything in place. Now, we can still fail to
        # insert a reference if we have a duplicate bibtexkey, in which case we need to fix.
        # I suppose I will fix it up with appending a short random string.

        ref_data = dict(
            reftype_id = self.ref_types[new_data['reftype']],
            title = new_data['title'],
            bibtexkey = new_bibtexkey
        )

        c = self._db.insert('refs', ref_data)
        ref_id = c.lastrowid

        try:
            errors += self.update_reference(dict(ref_id=ref_id), new_data, add_reference=True)
        except IntegrityError:
            errors.append("Record '%s...' not imported (likely duplicate)" % new_data['title'][:50])
            # also need to revert partial import
            self._db.execute('delete from refs where ref_id=(?)', [ref_id])
            return errors

        # Associate the new reference with the current branch
        branch_id = node[1]

        for branch_id in (node[1], self.recently_added_id):
            self._db.insert('reflink', dict(ref_id=ref_id,branch_id=branch_id))

        if single_mode:
            self._db.commit()
            hub.refresh_tree_item(node)

            if errors:
                hub.show_errors(errors)

        else: # collect errors for display later on.
            return errors


    def format_bibtex_value(self, key, value):
        '''
        use textwrap to break long lines
        '''
        value = str(value)
        if self.export_wrapped:
            value = self.bibtex_wrapper.fill(str(value)).lstrip()
        return self.field_template % (key.ljust(self.key_width), value)


    def format_bibtex(self, data):
        '''
        take a data dict and spit it out as formatted bibtex.

        let's give doi preference over pmid. No, let's not, pmid is more
        reliable. Let's keep the pmids around.
        '''
        fields = config['bibtex']['export_fields'].strip().split()

        reftype = data.pop('reftype')
        bibtexkey = data.pop('bibtexkey')
        header = '@%s{%s,' % (reftype, bibtexkey)

        lines = [header]
        fval = self.format_bibtex_value

        for field in fields:
            value = data.get(field)

            if value is not None:

                if field == 'doi' and not 'pmid' in data:
                    lines.append(fval('eprinttype', 'doi'))
                    lines.append(fval('eprint', value))
                    # append doi under its own name as well, for JabRef's benefit.
                    lines.append(fval(field, value))
                elif field == 'pmid':
                    lines.append(fval('eprinttype', 'pubmed'))
                    lines.append(fval('eprint', value))
                else:
                    lines.append(fval(field, value))

        lines[-1] = lines[-1].rstrip(',')
        lines.append('}')
        return '\n'.join(lines)


    def get_export_records(self, node=None, folder_ids=None, ref_keys=None):
        '''
        determine what records to export. backend for html and bibtex export
        - if node is not None, we export the reference or folder it refers to.
        - elif folder_ids is not None, we collect all references in those folders
        - elif ref_keys is not None, we export just those references
        - else, we export the current selection.
        '''
        if node is not None:
            records = [self.get_ref_dict(node)]

        elif folder_ids is not None:
            branches, records = self.get_nodes_below(folder_ids)

        elif ref_keys is not None:
            records = self.get_refs_by_key(ref_keys)
            # print('records', len(records))

        else:  # get current selection
            records = hub.get_selected_refs_full()

        return sorted(records, key=lambda r: r['bibtexkey']) # sorting could be made configurable


    def write_export_records(self, output, file_name, batch):
        '''
        write formatted records to file. backend for both bibtex and html
        '''
        try:
            rv = writefile(file_name, output)
        except Exception as error:
            if not batch:
                hub.show_errors(str(error))
            else:
                traceback.print_exc()
        else:
            # hub.show_info("File %s written" % file_name)
            if not batch:
                hub.app.set_status("Output sent to %s" % rv)


    def export_bibtex(self, node=None, folder_ids=None, ref_keys=None, file_name=None, batch=False):
        '''
        export records in bibtex format. Since this is a little slow
        with large numbers of records, we show a progress bar.
        '''
        records = self.get_export_records(node=node, folder_ids=folder_ids, ref_keys=ref_keys)
        output = []

        if not batch:
            progress_bar = dialog.ProgressBar()
            progress_bar.set_title("exporting to BibTex")
            progress_bar.show()
            progress_bar.set_completion(0)

        l = len(records)
        completion = 0

        for i, record in enumerate(records):
            output.append(self.format_bibtex(record))
            p = round(100.0 * i / l)
            if p - completion > 10:
                completion += 10
                if not batch:
                    progress_bar.set_completion(completion)

        output = '\n\n'.join(output)

        self.write_export_records(output, file_name, batch)
        if not batch:
            progress_bar.set_completion(100)


    def export_html(self, node=None, file_name=None, batch=False):
        '''
        export records as html. Maybe we should update this to
        accepting nodelist rather than a single node also.
        '''
        records = self.get_export_records(node=node)
        output = OlFormatter(records)()
        self.write_export_records(output, file_name, batch)


    def _fetch_bibtex_for_doi(self, doi):
        '''
        fetch bibtex for a single doi. Error handling goes above.
        '''
        q = Request('http://dx.doi.org/' + doi)
        q.add_header('Accept', 'text/bibliography; style=bibtex')
        a = urlopen(q).read().strip()
        return a.decode('UTF-8','ignore').replace('–','-')


    def import_doi(self, node, raw_info):
        '''
        convert a doi to bibtex first, and then import that. should we allow multiple dois?
        why not - let's just split across whitespace.
        '''
        doi = self._file_or_text(raw_info)

        progress_bar = dialog.ProgressBar()
        progress_bar.set_title("fetching bibtex from doi.org")
        progress_bar.show()

        dois = doi.split()
        records = []
        failed_dois = []

        for i, doi in enumerate(dois):
            progress = (i+0.5) / len(dois)
            progress_bar.set_completion(progress)

            try:
                bibtex = self._fetch_bibtex_for_doi(doi)
                records.append(bibtex)
            except:
                failed_dois.append(doi)

        progress_bar.dismiss()

        if len(failed_dois):
            msg = 'retrieval failed for the following identifiers: %s' % ', '.join(failed_dois)
            hub.show_errors(msg)

        if len(records):
            bibtex = '\n\n'.join(records)
            self.import_bibtex(node, bibtex)


    def export_mine(self):
        '''
        will have to implement this some time ...
        '''
        pass


_export = '''
          add_reference
          clear_recent
          export_bibtex
          export_html
          import_pubmed
          import_bibtex
          import_doi
'''

hub.register_many(_export.split(), Imex())


