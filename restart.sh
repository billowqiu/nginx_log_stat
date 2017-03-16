#########################################################################
# File Name: restart.sh
# Author: billowqiu
# mail: billowqiu@163.com
# Created Time: 2016-10-06 13:21:57
# Last Changed: 2016-10-27 17:33:16
#########################################################################
#!/bin/bash
cd /home/work/tmp/ngx_tail/
logfile=ngx_tail.log
pids=`ps -ef | grep python | grep ngx_tail | grep -v grep | awk '{print $2}'`
echo "`date` ${pids}" >> ${logfile}
status=`echo ${pids} | wc -l`
if [ ${status} -ne 0 ]
then
    for pid in $pids
    do
        echo "`date` kill it first: ${pid}" >> ${logfile}
        kill -9 $pid
    done
fi

#then start it
source /home/work/.bash_profile
nohup python ngx_tail.py -l /data/wwwlogs/wechat.51ekt.com_nginx.log &
nohup python ngx_tail_pc.py -l /data/wwwlogs/www.51ekt.com_nginx.log &
echo "`date` restarted ngx_tail" >> ${logfile}

