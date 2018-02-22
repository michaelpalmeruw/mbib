'''
well, it seems that crossref no longer limits the requests. Very good.
'''
from __future__ import print_function

import urllib, time, pprint
from SqliteDB import SqliteDB, IntegrityError

dbfile = "/data/code/mbib3/db/newbib.sqlite"
DB = SqliteDB(dbfile)


def pmid_producer():
    '''
    look up the pmids and return them one by one, together with the associated ref id.

    4699                  17                    68
    4699                  8                     Department of Chemis
    4699                  12                    2469-73
    4699                  2                     Meuwis, K and Boens,
    4699                  15                    research
    4699                  18                    1995
    4699                  16                    https://www.ncbi.nlm
    4699                  1                     The fluorescent indi
    4699                  9                     Biophys. J.
    '''


    stmt = '''
           select ref_id, content from uniqid where field_id=13
           and ref_id not in (select ref_id from uniqid where field_id=5)
           '''

    records = DB.execute(stmt, row_dicts=False).fetchall()

    for record in records:
        yield record


def pubmed_lookup(pmid):
    '''
    use the existing pubmed lookup; it works well.
    '''
    ncbi_url = "http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=%s&retmode=json"

    request_url = ncbi_url % pmid

    try:
        u = urllib.urlopen(request_url)
    except IOError:
        raise SystemExit("Pubmed web service unreachable")

    return_code = int(u.getcode())

    if return_code != 200:
        print("unexpected HTTP status: %s" % return_code)
        return None

    json = u.read()


    if 'error' in json and "cannot get document summary" in json:
        print('invalid PubMed identifier %s' % pmid)
        return None

    dct = eval(json, {})

    result = dct['result']
    result.pop('uids')

    # pprint.pprint(result)

    try:
        result = list(result.values())[0]
    except IndexError:
        print('invalid PubMed identifier %s' % pmid)
        return None


    data = {}

    try:
        data['aulast'] = result['sortfirstauthor']
        data['title'] = result['source']
        data['volume'] = result['volume']
        data['spage'] = result['pages'].split('-')[0]
        data['date'] = result['pubdate'].split()[0]
        data['redirect'] = 'false'

        urlargs = urllib.urlencode(data)

        return urlargs

    except KeyError:
        print("received incomplete information from PubMed")
        return None


def get_doi(urlargs):
    '''
    use the pubmed return values to look up at crossref
    '''
    xref_url = "https://www.crossref.org/openurl?pid=mpalmer@uwaterloo.ca&"
    url = xref_url + urlargs

    print(url)
    # return

    try:
        u = urllib.urlopen(xref_url)
    except IOError:
        raise SystemExit("Crossref web service unreachable")

    print(u.read())


if __name__ == '__main__':

    records = pmid_producer()
    for i in range(1):
        ref_id, pmid = next(records)
        data = pubmed_lookup(pmid)
        print(data)

        if data is not None:
            get_doi(data)

        time.sleep(1)


