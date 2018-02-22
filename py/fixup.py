'''
well, it seems that crossref no longer limits the requests. Very good.
'''
import time, pprint
from SqliteDB import SqliteDB, IntegrityError

dbfile = "/data/code/mbib3/db/newbib.sqlite"
DB = SqliteDB(dbfile)

refs = DB.execute('select * from refs').fetchall()

print(refs[0])

for ref in refs:
    year = DB.execute('select content from optional where field_id=18 and ref_id=(?)', [ref['ref_id']]).fetchvalue()
    # print(ref['ref_id'], year)
    DB.execute('update refs set year=(?) where ref_id=(?)', [year, ref['ref_id']])

DB.commit()
