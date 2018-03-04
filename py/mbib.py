#!/usr/bin/env python3
import os

batch_arg = os.getenv('mbib_batch')

# print("batch_arg", batch_arg)

if batch_arg is None:
    from bibapp import BibApp
    from hub import hub
    _app = BibApp()
    hub.register('app', _app)
    hub.register('tree', _app.tree)
    hub.register('exit', _app.exit)
    hub.app()
else:
    from batchmode import BatchMode
    BatchMode(batch_arg)()


