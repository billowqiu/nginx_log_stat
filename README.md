# nginx_log_stat
实时统计nginx日志，并将指标发送到statsd
使用方式：
    python ngx_tail.py config --access-log=/data/wwwlogs/xxx.log --vhost-prefix=wechat --statsd-port=8225
    vhost-prefix是为了区分一个机器上面有多个nginx日志
