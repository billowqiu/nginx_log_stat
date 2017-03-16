#########################################################################
# File Name: restart.sh
# Author: billowqiu
# mail: billowqiu@163.com
# Created Time: 2016-10-06 13:21:57
# Last Changed: 2017-03-16 16:50:11
#########################################################################
#!/bin/bash
basepath=$(cd `dirname $0`; pwd)
cd $basepath
logfile=ngx_tail.log

echo "$basepath" >> ${logfile}
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
nohup python ${basepath}/ngx_tail.py config --access-log=/data/wwwlogs/wechat.51ekt.com_nginx.log --vhost-prefix=wechat --statsd-port=8125 &
nohup python ${basepath}/ngx_tail.py config --access-log=/data/wwwlogs/www.51ekt.com_nginx.log --vhost-prefix=www --statsd-port=8125 &
nohup python ${basepath}/ngx_tail.py config --access-log=/data/wwwlogs/api.51ekt.com_nginx.log --vhost-prefix=api --statsd-port=8125 &
echo "`date` restarted ngx_tail" >> ${logfile}

