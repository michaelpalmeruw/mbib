#!/bin/bash

# this is the main mbib controller script.

# python /data/code/mbib/bib.py "$@"
bashtitle "bib.sh"
if [ -z `pgrep -f bib.py` ]; then
    python3 /data/code/mbib3/bib.py "$@"
else
    echo "bib.sh already open - exiting"
    sleep 1
fi
bashtitle ""
