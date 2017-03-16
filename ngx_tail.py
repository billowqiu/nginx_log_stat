#!/bin/env python
# -*- coding: utf-8 -*-
"""nginx_log_stat - realtime parse nginx log, send stat metric to statsd
   modify from ngx_top https://github.com/lebinh/ngxtop

Usage:
    nginx_log_stat [options]  config --access-log=<access-log> --vhost-prefix=<vhost-prefix> --statsd-port=<statsd-port>
    nginx_log_stat info

Options:
    -f <format>, --log-format <format>  log format as specify in log_format directive. [default: combined]
    --no-follow  ngxtop default behavior is to ignore current lines in log
                     and only watch for new lines as they are written to the access log.
                     Use this flag to tell ngxtop to process the current content of the access log instead.
    -v, --verbose  more verbose output
    -d, --debug  print every line and parsed record
    -h, --help  print this help message.
    --version  print version information.

    Advanced / experimental options:
    -c <file>, --config <file>  allow ngxtop to parse nginx config file for log format and location.
    -i <filter-expression>, --filter <filter-expression>  filter in, records satisfied given expression are processed.
    -p <filter-expression>, --pre-filter <filter-expression> in-filter expression to check in pre-parsing phase.

"""

from __future__ import print_function
import atexit
from contextlib import closing
import curses
import logging
import os
import sqlite3
import time
import sys
import signal
import socket
import statsd_cli

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

import sys
sys.path.append('.')
from config_parser import detect_log_config, detect_config_path, extract_variables, build_pattern
from utils import error_exit

# ======================
# generator utilities
# ======================
def follow(the_file):
    """
    Follow a given file and yield new lines when they are available, like `tail -f`.
    """
    with open(the_file) as f:
        f.seek(0, 2)  # seek to eof
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)  # sleep briefly before trying again
                continue
            yield line


def map_field(field, func, dict_sequence):
    """
    Apply given function to value of given key in every dictionary in sequence and
    set the result as new value for that key.
    """
    for item in dict_sequence:
        try:
            item[field] = func(item.get(field, None))
            yield item
        except ValueError:
            pass


def add_field(field, func, dict_sequence):
    """
    Apply given function to the record and store result in given field of current record.
    Do nothing if record already contains given field.
    """
    for item in dict_sequence:
        if field not in item:
            item[field] = func(item)
        yield item


def trace(sequence, phase=''):
    for item in sequence:
        logging.debug('%s:\n%s', phase, item)
        yield item


# ======================
# Access log parsing
# ======================
def parse_request_path(record):
    if 'request_uri' in record:
        uri = record['request_uri']
    elif 'request' in record:
        uri = ' '.join(record['request'].split(' ')[1:-1])
    else:
        uri = None
    return urlparse.urlparse(uri).path if uri else None


def parse_status_type(record):
    return record['status'] // 100 if 'status' in record else None


def to_int(value):
    return int(value) if value and value != '-' else 0


def to_float(value):
    return float(value) if value and value != '-' else 0.0


def parse_log(lines, pattern):
    matches = (pattern.match(l) for l in lines)
    records = (m.groupdict() for m in matches if m is not None)
    records = map_field('status', to_int, records)
    records = add_field('status_type', parse_status_type, records)
    records = add_field('bytes_sent', lambda r: r['body_bytes_sent'], records)
    records = map_field('bytes_sent', to_int, records)
    records = map_field('request_time', to_float, records)
    records = add_field('request_path', parse_request_path, records)
    return records



def process_log(lines, pattern, processor, arguments):
    print(lines)
    pre_filer_exp = arguments['--pre-filter']
    #下面的for循环会导致lines这个生成器的yield返回数据
    if pre_filer_exp:
        lines = (line for line in lines if eval(pre_filer_exp, {}, dict(line=line)))

    #下面的for循环会导致records这个生成器的yield返回数据
    records = parse_log(lines, pattern)
    print(records)
    filter_exp = arguments['--filter']
    if filter_exp:
        records = (r for r in records if eval(filter_exp, {}, r))

    vhost_prefix = arguments['--vhost-prefix']
    statsd_port = arguments['--statsd-port']
    statsd = statsd_cli.StatsdClient(port=int(statsd_port))
    #send to statsd
    for record in records:
        #这里兼容一下微官网的，如果是wechat则特殊处理一下
        if vhost_prefix == 'wechat':
            metric_qps = socket.gethostname() + '.nginx.qps'
        else:
            metric_qps = socket.gethostname() + '.' + vhost_prefix + '_nginx.qps'
        print(metric_qps)

        statsd.increment(metric_qps)
        if record.has_key('status'):
            if vhost_prefix == 'wechat':
                metric_status = socket.gethostname() + '.' + 'nginx.' + 'status_code.' + str(record['status'])
            else:
                metric_status = socket.gethostname() + '.' + vhost_prefix + '_nginx.status_code.' + str(record['status'])
            statsd.increment(metric_status)

def build_source(access_log, arguments):
    # constructing log source
    if access_log == 'stdin':
        lines = sys.stdin
    elif arguments['--no-follow']:
        lines = open(access_log)
    else:
        lines = follow(access_log)
    return lines

def process(arguments):
    access_log = arguments['--access-log']
    log_format = arguments['--log-format']
    if access_log is None and not sys.stdin.isatty():
        # assume logs can be fetched directly from stdin when piped
        access_log = 'stdin'
    if access_log is None:
        access_log, log_format = detect_log_config(arguments)

    logging.info('access_log: %s', access_log)
    logging.info('log_format: %s', log_format)
    if access_log != 'stdin' and not os.path.exists(access_log):
        error_exit('access log file "%s" does not exist' % access_log)

    if arguments['info']:
        print('nginx configuration file:\n ', detect_config_path())
        print('access log file:\n ', access_log)
        print('access log format:\n ', log_format)
        print('available variables:\n ', ', '.join(sorted(extract_variables(log_format))))
        return

    source = build_source(access_log, arguments)
    pattern = build_pattern(log_format)
    #processor = build_processor(arguments) 
    processor = None
    process_log(source, pattern, processor, arguments)

def main():
    from docopt import docopt
    args = docopt(__doc__, version='nginx_log_stat 0.02')
    print(args)

    log_level = logging.WARNING
    if args['--verbose']:
        log_level = logging.INFO
    if args['--debug']:
        log_level = logging.DEBUG
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')
    logging.debug('arguments:\n%s', args)

    try:
        process(args)
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == '__main__':
    logging.basicConfig(filename='nginx_log_stat.log', level=logging.DEBUG)
    main()

