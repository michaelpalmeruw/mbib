#!/bin/bash

export script_name="${BASH_SOURCE[0]}"
usage() { echo "Usage: $script_name [-d <database file>] [-i <ini file>] [-b <batch operation>] [-f <folder>] [-t <target file>] [-c (clobber target files)]" 1>&2; exit 1; }

# default ini file - can be overridden using -b option
export mbib_ini="$HOME/.mbib.ini"

while getopts ":d:i:b:t:f:hc" opt; do
    case $opt in
        b)
            export mbib_batch=${OPTARG}
            ;;
        c)
            export mbib_clobber=true
            ;;
        d)
            export mbib_db=`readlink -f ${OPTARG}`
            ;;
        f)
            export mbib_folder=${OPTARG}
            ;;
        h)
            usage
            ;;
        i)
            export mbib_ini=`readlink -f ${OPTARG}`
            ;;
        t)
            export mbib_target=`readlink -f ${OPTARG}`
            ;;
        *)
            usage
            ;;
    esac
done
shift $((OPTIND-1))

# if there remain unprocessed arguments, exit
if [ ! -z "$@" ]; then
    echo "error parsing arguments"
    usage
fi

# allow only one interactive instance to run
if [ -z "$mbib_batch" ] && [ ! -z `pgrep -f mbib.py`  ]; then
    echo "An interactive mbib.sh session is already open -- exiting"
    sleep 2
    exit 1
fi

# determine directory to that of this script and make available to python
export mbib_dir="$( cd "$( dirname "$script_name" )" && pwd )"

default_ini="$mbib_dir/resources/default.ini"

# check if ini file exists, offer to create one if it doesn't
if [ ! -f ${mbib_ini} ]; then
    echo "Config file $mbib_ini not found!"
    echo "Create default configuration file and proceed (1) or exit (2)?"
    select yn in "proceed" "exit"; do
        case $yn in
            "proceed" )
                echo "OK"
                cp $default_ini $mbib_ini
                break ;;
            "exit" )  echo "Bye"; exit;;
        esac
    done
fi

# start the program
python3 "$mbib_dir/py/mbib.py"
