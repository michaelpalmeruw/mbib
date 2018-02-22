'''
implement batch processing tasks.
'''

from hub import hub, RefdbError, IntegrityError
from imex import Imex
from config import config
import zipfile, os, sys, re, tempfile, shutil, glob
from collections import Counter

# turns out we can't just replace a single item
# well, it seems text:span elements that refer to non-existing styles, or to none at all, are cut out?
# is that it? let's insert a custom style then and see how that goes.
# <style:style style:name="T1" style:family="text"><style:text-properties fo:language="zxx" fo:country="none"/></style:style></office:automatic-styles>


class BatchMode(object):

    citation_match_re = re.compile(r'\<text:bibliography-mark [^\>]*text:identifier=\"(\w+)\"[^\<]*\<\/text:bibliography-mark\>', re.MULTILINE)
    citation_split_re = re.compile(r'(\<text:bibliography-mark [^\>]+\>[^\<]+\<\/text:bibliography-mark\>)', re.MULTILINE)

    empty_span_tags_re = re.compile(r'^\w*</text:span><text:span text:style-name="\w+">\w*$')
    existing_jr_keys_re = re.compile(r'(JR_cite\d*_\d*_([\w\_\-\:\,]+))')

    #replace_template = """<text:reference-mark-start text:name="{jrk}"/><text:span text:style-name="T1">[{ds}]</text:span><text:reference-mark-end text:name="{jrk}"/>"""

    # we simply do not apply any style name - that seems to work and should cause minimal
    # interference. We can always rig it up later if we feel the need.
    #replace_template = """<text:reference-mark-start text:name="{jrk}"/><text:span>[{ds}]</text:span><text:reference-mark-end text:name="{jrk}"/>"""

    # can we drop the inner text:span tag entirely? Does Jabref still work in that case?
    # apparently so. The simpler the better.
    replace_template = """<text:reference-mark-start text:name="{jrk}"/>[{ds}]<text:reference-mark-end text:name="{jrk}"/>"""

    # well, we can't just use T1 - it may be defined in ways that we don't want. So, we need to create our own style definition that is not otherwise used.
    # that means capturing all defined styles with a regex and then adding a new one. I guess we need to do this before we actually start replacing
    # the citation tags. Roger - nice project for an evening.
    #style_end_tag = "</office:automatic-styles>"
    #style_test_tag = """<style:style style:name="T1" style:family="text">"""  # we first test if it's there already.
    #extra_style_tag = """<style:style style:name="T1" style:family="text"><style:text-properties fo:language="zxx" fo:country="none"/></style:style>"""

    def __init__(self, arguments):
        self._db = hub.sqlite
        self.arguments = arguments
        self.bibtexkeys = set()     # collect keys found in mbib or existing JabRef citations
        self.jr_keys = set()        # collect JabRef-style citation keys - both existing and generated

    def __getattr__(self, att):
        return getattr(hub.coredb, att)

    def __call__(self):
        func_name = self.arguments[0]

        if func_name == 'mogrify':
            self.mogrify()

        elif func_name == 'sync':
            self.sync_bibtex()

        else:
            sys.exit("don't know how command '%s'" % func_name)


    def get_cited_records(self):
        '''
        obtain full records for the collected bibtexkeys.
        '''
        stmt = '''
               select refs.*, reftypes.name as reftype
                      from refs, reftypes
                      where refs.reftype_id = reftypes.reftype_id
                      and refs.bibtexkey in (%s)
               '''
        base_records = self._db.execute_qmarks(stmt, [list(self.bibtexkeys)]).fetchall()
        full_records = hub.extend_refs(base_records)

        found = set([fr['bibtexkey'] for fr in full_records])
        missing = [k for k in self.bibtexkeys if not k in found]

        return missing, full_records


    def get_citation(self, fragment):
        '''
        test if a text fragment represents a citation, and if so, return the bibtexkey it contains
        '''
        mo = self.citation_match_re.match(fragment)

        if mo is None:
            return None

        bibtexkey = mo.group(1)
        self.bibtexkeys.add(bibtexkey)

        return bibtexkey


    def format_group(self, group):
        '''
        format a group of citations as a JabRef citation group.

        we should strip out repetitions that might have snuck in,
        and I guess print a warning if that happens. We don't
        just use a set because we want to keep the sequence.
        '''
        filtered = Counter()

        for key in group:
            filtered[key] += 1

        keys = sorted(filtered.keys())

        repeated = [key for key, value in filtered.items() if value > 1]
        if repeated:
            print("dropping repetition of key(s) '%s' in same cite group" % ", ".join(repeated))

        tag_string = ','.join(keys)
        display_string = ", ".join(keys)

        template = "JR_cite{ctr}_1_{ts}"
        num = 0

        jr_key = template.format(ctr="", ts=tag_string)

        while jr_key in self.jr_keys:
            jr_key = template.format(ctr=num, ts=tag_string)
            num += 1

        self.jr_keys.add(jr_key)

        return self.replace_template.format(ts=tag_string, ds=display_string, jrk=jr_key)


    def process_content(self, content):
        '''
        separate this from the unpacking and repacking. Return the modified string.
        '''
        # first, fish out any jabref citation keys that might already have been inserted manually.
        fragments = self.citation_split_re.split(content)

        jr_keys = self.existing_jr_keys_re.finditer(content)

        for key in jr_keys:
            self.jr_keys.add(key.group())
            btkeys = key.group(2).split(',')
            self.bibtexkeys.update(btkeys)

        fragments = self.citation_split_re.split(content)

        # remove empties and empty pairs of closing and reopening text spans.
        # whitespace would have to be enclosed by citations and thus be spurious.
        filtered = [frag for frag in fragments if frag.strip() \
                         and not self.empty_span_tags_re.match(frag)]

        # insert an extra style tag into the preamble
        header = filtered[0]
        assert header.startswith('<?xml')

        # we no longer reference any style definition, so don't add one either
        #if not self.style_test_tag in header:
            #header = header.replace(self.style_end_tag, self.extra_style_tag + self.style_end_tag)
        rebuilt = [header]

        current_group = []

        for frag in filtered[1:]:
            citation = self.get_citation(frag)

            if citation is None:
                if current_group:
                    formatted = self.format_group(current_group)
                    rebuilt.append(formatted)
                current_group = []
                rebuilt.append(frag)
            else:
                current_group.append(citation)

        # the last fragment can never be a citation, so we don't need any explicit termination cleanup
        return len(fragments) - 1, "".join(rebuilt)


    def sync_bibtex(self):
        '''
        synchronize database with default bibtex file. Come to think of it, we should
        probably check the file date on the core database and the bibtexfile.
        '''
        refnode = self.special_branch_nodes['References']
        bt = config['paths']['bibtex_export']
        db = hub.dbfile  # config['paths']['dbfile'] may be overridden from command line

        if os.path.exists(bt) and \
            (os.stat(db).st_mtime <= os.stat(bt).st_mtime):
            return

        hub.export_bibtex(refnode, bt, batch=True)


    def mogrify(self):
        '''
        convert bibliography items in an odt file from native
        to jabref format
        '''
        file_names = self.arguments[1:]

        if len(file_names) == 0:
            sys.exit('must specify input file name')

        infile_name = file_names[0]

        try:
            infile = zipfile.ZipFile(infile_name)
            content = infile.open('content.xml').read()
        except FileNotFoundError:
            sys.exit("file '%s' not found" % infile_name)
        except (KeyError, zipfile.BadZipFile):
            sys.exit("file '%s' has wrong type or is corrupt" % infile_name)

        # OK, at this stage, we have a valid input file.
        try:
            outfile_name = file_names[1]
        except IndexError:
            trunk, ext = os.path.splitext(infile_name)
            outfile_name = "%s_jr%s" % (trunk, ext)

        if infile_name == outfile_name:
            sys.exit("names of infile and outfile must be different")

        # curdir = os.path.realpath(os.getcwd())
        full_outfile_name = outfile_name # os.path.join(curdir, outfile_name)

        try:
            os.remove(full_outfile_name)
        except FileNotFoundError:
            pass

        mydir = tempfile.TemporaryDirectory()

        infile.extractall(mydir.name)
        os.chdir(mydir.name)

        content = open('content.xml').read()
        num_cites, processed = self.process_content(content)

        if num_cites > 0:
            open('content.xml','w').write(processed)
            os.system('zip -r %s * > /dev/null' % outfile_name)
            shutil.move(outfile_name, full_outfile_name)
            print("wrote mogrified file '%s'" % outfile_name)

        else:
            print("No mbib citations found, therefore not writing modified .odt file")

        os.chdir(curdir)
        missing, records = self.get_cited_records()

        if missing:
            print("Record(s) %s not found in database" % ", ".join(missing))

        if len(records) > 0:
            bibfile_name = os.path.splitext(outfile_name)[0] + '.bib'
            bibfile = open(bibfile_name, 'w')

            formatter = Imex().format_bibtex

            for record in records:
                bibfile.write(formatter(record) + "\n\n")

            bibfile.close()
            print("wrote bibtex file '%s'" % bibfile_name)
        else:
            print("No citations found in database, therefore not writing bibtex file")


    def retitle(self):
        '''
        retitle all pdfs in the import folder, and distribute them to the
        alphabetical ones. Let's use exiftool - it's simple.

        exiftool -P -overwrite_original -title="$newtitle" $filename # &> /dev/null
        '''



