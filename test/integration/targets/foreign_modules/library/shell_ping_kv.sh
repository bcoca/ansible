#!/bin/sh

set -ue

# read k=v file as it is first arg
argfile=$@
args=`cat $argfile`
echo $args

# prep results
result='"failed": false, "changed": false, "msg": "pong"'

# parse arguments pairs (need to fix handling spaces in value)
for pair in $args; do

	# parse k=v
	set -- echo $pair| tr '=' ' '
	key=$1
	value=$2

	# skip internal values, put rest back into result
	if [ $key != _ansible* ]; then
		result="$result, \"$key\": \"$value\""
	fi
done

# send results
echo "{ $result }"
