'''
OK doke, we are going to redo this using efetch and lxml:
- no limit on ids per request
- unicode, not ascii
- more straightforward parsing. The old medline-text based version
  is in folder 'old'.
'''
import re, pprint
from io import BytesIO

class PubmedError(Exception):
    pass


class PubmedImporter(object):
    '''
    take a pubmed ID and return a record as a dict ready for insertion
    into the database. I guess we separate the insertion from the parsing,
    since we will likely want to write other importers in the future.
    '''
    pmid_split = re.compile(r'\D+', re.MULTILINE)

    efetch_base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    # not used for fetching, just for constructing the url in the record. Hm. It's redundant;
    # we should construct the full url only when clicked.
    # record_base_url = 'https://www.ncbi.nlm.nih.gov/pubmed/'

    # escape latex special characters
    bibtex_conv = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}',
        '<': r'\textless',
        '>': r'\textgreater',
    }

    bibtex_re = re.compile('|'.join(re.escape(str(key)) for key in sorted(list(bibtex_conv.keys()), \
                                                                             key = lambda item: -len(item))))

    def __init__(self, raw_pmids, progress_bar):
        self.pmid_list = [_f for _f in self.pmid_split.split(raw_pmids) if _f]
        self.progress_bar = progress_bar
        self.progress = 0

        if not self.pmid_list:
            raise PubmedError('no valid pmid identifiers (pmids are just numbers)')

        self.failed_pmids = set(self.pmid_list)     #   we strike off every pmid that we do retrieve

        self.records = []


    def fetch(self):
        '''
        get the raw stuff from pubmed
        '''
        import requests         # a heavy import

        parameters = dict(db="pubmed", retmode="xml", id=','.join(self.pmid_list))

        try:
            r = requests.post(url=self.efetch_base_url, data=parameters, allow_redirects=True)
            webfile = BytesIO(r.content)
        except:
            raise PubmedError('Nothing retrieved for given identifiers')

        return webfile


    def bibtex_escape(self, text):
        '''
        ah. what is this?
        '''
        text = str(text) # We had a failure with None, so we just make sure.
        return self.bibtex_re.sub(lambda match: "{%s}" % self.bibtex_conv[match.group()], text)


    def set_key(self, tag, dct, key, path):
        '''
        simply wrap the retrieval of a tag attribute,
        silently ignoring its absence.
        '''
        value = tag.find(path)

        if value is not None:
            dct[key] = self.bibtex_escape(value.text)
        return value


    def parse_article(self, article):

        d = {'reftype':'article'} # what else...

        inner = article.find("MedlineCitation/Article")

        self.set_key(inner, d, 'title', 'ArticleTitle')
        self.set_key(inner, d, 'abstract', 'Abstract/AbstractText')

        journal = inner.find("Journal")

        if journal is not None:
            d['journal'] = journal.find("Title").text
            title = self.set_key(journal, d, "journal", "ISOAbbreviation")

            if title is None:
                self.set_key(journal, d, "journal", "Title")

            self.set_key(journal, d, 'volume', "JournalIssue/Volume")
            self.set_key(inner, d, 'pages', "Pagination/MedlinePgn")
            self.set_key(journal, d, 'year', "JournalIssue/PubDate/Year")

        pubtypes = inner.findall("PublicationTypeList/PublicationType")
        for pubtype in pubtypes:
            if pubtype.text.lower() == 'review':
                d['purpose'] = 'review'
                break
        else:
            d['purpose'] = 'research'

        authors = inner.findall("AuthorList/Author")

        if bool(authors): # is it None or an empty list?
            author_list = []

            for i, author in enumerate(authors):
                lastname = author.find("LastName")
                try:
                    lastname = lastname.text
                except AttributeError:
                    lastname = "NN"

                if i == 0:
                    d['firstlast'] = lastname

                firstname = author.find("ForeName")

                if firstname is None:
                    firstname = author.find('Initials')
                try:
                    firstname = firstname.text
                except AttributeError:
                    firstname = "NN"

                author_list.append("%s, %s" % (lastname, firstname))

            d['author'] = ' and '.join(author_list)
            self.set_key(authors[0], d, 'institution', "AffiliationInfo/Affiliation")
        else:
            d['author'] = "Anonymous"

        self.set_key(article, d, 'doi', "PubmedData/ArticleIdList/ArticleId[@IdType='doi']")
        self.set_key(article, d, 'pmid', "PubmedData/ArticleIdList/ArticleId[@IdType='pubmed']")

        # d['url'] = self.record_base_url + d['pmid'] Nope. This is redundant.

        return d


    def __call__(self):
        '''
        fetch, parse, return. update progress bar if present.
        '''
        from lxml import etree      # a heavy import

        self.progress_bar.set_title("Fetching %s records" % len(self.pmid_list))

        webfile = self.fetch()

        self.progress_bar.set_title('Parsing records')
        self.progress_bar.set_completion(20)

        root = etree.parse(webfile)
        articles = root.findall('PubmedArticle')

        for i, article in enumerate(articles):
            parsed = self.parse_article(article)
            self.records.append(parsed)
            self.failed_pmids.discard(parsed['pmid'])

        return self.records, sorted(list(self.failed_pmids))


if __name__ == '__main__':

    import pprint

    pmids = '''
    24119568
    28363811
    28604177
    28597466
    28595462
    '''

    importer = PubmedImporter(pmids)
    #test = r'those #$%~$^{& bastards'
    #print importer.bibtex_escape(test)

    records, failed = importer()
    pprint.pprint(records)

