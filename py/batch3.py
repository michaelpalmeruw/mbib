'''
well, it seems that crossref no longer limits the requests. Very good.
'''
import time, pprint
from SqliteDB import SqliteDB, IntegrityError

dbfile = "/data/code/mbib3/db/newbib.sqlite"
DB = SqliteDB(dbfile)

from metapub import CrossRef, PubMedFetcher


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


def doi_fetcher(pmid):
    '''
    well, Naomi Most Wonderful just saved my bum.
    '''
    try:
        pma = PubMedFetcher().article_by_pmid(pmid)

        CR = CrossRef()       # starts the query cache engine

        results = CR.query_from_PubMedArticle(pma)
        top_result = CR.get_top_result(results, CR.last_params, use_best_guess=True)
        return top_result['doi']
    except:
        return None


def insert_doi(ref_id, doi):
    '''
    like the man says.
    '''
    value_dict = dict(
        ref_id = ref_id,
        field_id = 5,
        content = doi
    )
    try:
        DB.insert('uniqid', value_dict)
        DB.commit()
    except IntegrityError: # ok. so this seems to be a case of no DOI being returned? but seems very rare ...
        print("IntegrityError happened")


if __name__ == '__main__':

    records = pmid_producer()

    for ref_id, pmid in list(records):
        doi = doi_fetcher(pmid)

        #if doi is not None:
            #print("retrieved DOI %s for pmid %s" % (doi, pmid))
            #insert_doi(ref_id, doi)
        #else:
            #print("didn't get a doi for pmid", pmid)

        time.sleep(1)


