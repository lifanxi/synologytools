#! /bin/bash
while [ -e /var/spool/flv_create.queue.tmp -o -e /var/spool/flv_create.queue ] ; do
    echo wait flv
    sleep 10
done 
while [ -e /var/spool/thumb_create.queue -o -e /var/spool/thumb_create.queue.tmp ] ; do
    echo wait thumb
    sleep 10
done 
while [ -e /var/spool/syno_indexing_queue -o -e /var/spool/syno_indexing_queue.tmp ] ; do
    echo wait indexing
    sleep 10
done 
python arrange_photo.py $*
