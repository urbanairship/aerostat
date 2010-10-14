#!/usr/bin/env python

"""
Aerostat - Do lookups and configure hostname (locally) inside EC2.

This is the client code which Registers new hosts into the aerostat naming
service when run in --register mode. Otherwise, it's assumed that the host
is seeking an update to its name resolution (/etc/hosts).
"""

import logging
import os
import pymongo
import time
import urllib2

from optparse import OptionParser

import configurer
import registrar
import updater

LEVELS = {'debug': logging.DEBUG,
          'info': logging.INFO,
          'warning': logging.WARNING,
          'error': logging.ERROR,
          'critical': logging.CRITICAL}

INFO_URL = 'http://169.254.169.254/latest/meta-data/%s'


def get_mongo_info():
    """Get mongodb connection information (if any) from ENV."""

    server = os.environ.get('AEROSTAT_SERVER', 'admin-master')
    port = os.environ.get('AEROSTAT_PORT', 27017)
    return (server, port)


def db_connect(host, port):
    """Connect to MongoDB.

    Args:
        host: str, hostname of mongodb server.
        port: int, port number for mongodb; defaults to 27017.
    Returns:
        returns pymongo.Connection instance.
    """
    logging.debug('Connecting to mongo on host %s and port %s.' % (host, port))
    return pymongo.Connection(host, port)


def db_disconnect(conn):
    """Disconnect Mongodb Connection."""
    logging.debug('Disconnecting from mongodb.')
    conn.disconnect()


def get_aws_data(offline=False):
    """Retrieve information from metadata server in EC2."""
    instance_id = None
    local_ip = None

    # For testing, or for environments outside of AWS.
    if offline:
        return ('test-instance', 'test_local_ip')

    while instance_id is None or local_ip is None:
        instance_id = urllib2.urlopen(INFO_URL % 'instance-id').read()
        logging.debug('Recieved instance id from AWS: %s.' % instance_id)
        local_ip = urllib2.urlopen(INFO_URL % 'local-ipv4').read()
        logging.debug('Recieved local_ip from AWS: %s.' % local_ip)

    return (instance_id, local_ip)


def hostname_exists(db, hostname):
    """Check if a hostname exists."""
    results = db.servers.find({'hostname': hostname}).count()
    if results > 0:
        logging.info('Hostname %s exists' % hostname)
        return True
    else:
        logging.info('Hostname %s doesn\'t exist' % hostname)
        return False


def get_hostname(db, inst_id):
    """Get the hostname for an instnace."""

    result = db.servers.find_one({'instance_id': inst_id})
    if result:
        return result['hostname']
    else:
        return None

def get_master(db, service):
    """Get the master instance_id for a service.

    Args:
        db: mongodb db reference.
        service: str, service name of master whose instance id we need.
    Returns:
        str, master instance_id for service.
    """

    master_id = None
    res = list(db.servers.find(
            {'hostname': '%s-master' % service}))
    if len(res) > 1:
        logging.error('Multiple masters listed for %s service. Aborting' % service)
        return None
    if res:
        master_id = res[0]['instance_id']

    return master_id

def check_master(db, service, inst_id):
    """Check to see if current host is master.

    Args:
        db: mongodb db reference.
        service: str, name of service to check mastership for
        current host.
        inst_id: str, the instance id for the current host.
    Returns:
        bool, True if master.
    """
    cur_master = get_master(db, service)

    return cur_master == inst_id


def main():
    usage = 'usage: %prog [options] arg1 arg2'
    parser = OptionParser(usage=usage)
    parser.add_option(
            '--register', action='store_true', dest='register',
            help='Register server as a new Aerostat Client.')
    parser.add_option(
            '--change-master', action='store_true', dest='change_master',
            help='Make current host the master for its service.')
    parser.add_option(
            '--update', action='store_true', dest='update',
            help='Update /etc/hosts.')
    parser.add_option(
            '--server', action='store', dest='server',
            help='hostname of aerostat/mongo server to connect to.')
    parser.add_option(
            '--daemon', action='store_true', dest='daemon',
            help='Whether or not to run service (update) as a daemon.')
    parser.add_option(
            '--loglevel', action='store', dest='loglevel',
            help='Which severity of log to display.')
    parser.add_option(
            '--legacy-updater', action='store', dest='legacy',
            help='Specify path. Run legacy naming service prior to aerostat.')
    parser.add_option(
            '--dryrun', action='store_true', dest='dry_run', default=False,
            help='Whether or not to actually carry our registration and updates.')
    parser.add_option(
            '--offline', action='store_true', dest='offline', default=False,
            help='Whether or not we should connect to AWS for information.')
    parser.add_option(
            '--update-configs', action='store_true', dest='update_configs',
            default=False, help='Update configuration files?')
    parser.add_option(
            '--configs', action='store', dest='configs', default=None,
            help='specific configs to update (space sep in quotes)')


    (options, args) = parser.parse_args()

    if len(args) > 1:
        parser.error('Please supply some arguments')

    level = LEVELS.get(options.loglevel, logging.NOTSET)
    logging.basicConfig(level=level)

    mserver, mport = get_mongo_info()

    if options.server:
        mserver = options.server

    conn = db_connect(mserver, mport)
    db = conn.aerostat

    if options.register or options.change_master:
        reg= registrar.Registrar()
        reg.do_registrar(db, options.dry_run,
                options.change_master, options.offline)
    elif options.update_configs:
        conf_db = conn.configs
        config = configurer.Configurer()
        config.do_update(conf_db, config_names=options.configs.split())
    else:
        update = updater.Updater()

        if not options.daemon:
            update.do_update(db, options.dry_run, options.legacy)
        else:
            while 1:
                try:
                    update.do_update(db, options.dry_run, options.legacy)
                except pymongo.errors.AutoReconnect:
                    logging.error('Unable to connect to database %s:%s. '
                        'Sleeping.' % (mserver, str(mport)))

                time.sleep(60)

    db_disconnect(conn)

if __name__ == '__main__':
    main()
