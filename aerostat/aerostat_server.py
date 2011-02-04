#!/usr/bin/env python

"""
Aerostat_server - Ensure that Aerostat Mongodb data stays current.

This is meant to be run on the same server (though it doesn't have to be) that
is acting as the mongodb server for the name data. Its job is to make sure
that the data on this server are up-to-date with EC2 running instances.

This module is meant to be run as a daemon -- most likely controlled through
supervisord.
"""
import os
import datetime
import logging
import time

import aerostat
from _version import __version__
import git
import yaml

from boto.ec2.connection import EC2Connection
from optparse import OptionParser


logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )


class Aerostatd(object):

    def __init__(self, offline=False):
        self.offline = offline
        if not self.offline:
            self.aws_conn = self.aws_connect()

        self.mongo_conn = aerostat.db_connect('localhost', 27017)
        self.aerostat_db = self.mongo_conn.aerostat
        self.read_aerostatd_conf()

    def read_aerostatd_conf(self):
        """Read data in from aerostat.conf, if it exists, and update values.

        Args:
            None, but it pulls information from the environment.
        Returns:
            Bool, if the conf file is read from or not.
        """
        conf_path = os.environ.get('AEROSTATD_CONF', '/etc/aerostatd.conf')
        conf = None
        if not os.path.exists(conf_path):
            logging.warn('No aerostatd.conf to read, using defaults.')
            return False

        try:
            conf_file = open(conf_path, 'r')
            conf = yaml.load(conf_file.read())
            conf_file.close()
        except IOError, e:
            print('Error attempting to read config: %s' % e)
            return False

        #TODO(gavin): read out mongo connection, port information.

        return True

    def _read_creds(self, path=None):
        """Read AWS credentials for provisioning through boto.

        This is designed to be run as a priveledged user. The cred_data
        file should be inaccessible from non-priveledged users.

        Returns:
            tuple of the aws_key_id and aws_key_sec.
        """
        if not path:
            path = '/root/installer/.ec2'
        cred_data = open(path, 'r')
        key_id, key_sec, keypair_name = cred_data.read().strip().split()
        cred_data.close()

        return key_id, key_sec, keypair_name

    def aws_connect(self):
        """Return connection cursor from EC2."""

        key_id, key_sec, keypair_name = self._read_creds()
        return EC2Connection(key_id, key_sec)

    def get_mongo_instance_ids(self):
        """Return a list of instance_ids that mongo knows about."""

        return [result['instance_id'] for result in self.aerostat_db.servers.find()]

    def get_aws_instance_ids(self):
        """Return a list of instance_ids that EC2 knows about, and are running."""
        aws_reqs = self.aws_conn.get_all_instances()
        instances = []
        [instances.extend(req.instances) for req in aws_reqs]
        instance_ids = []
        for instance in instances:
            if instance.state == 'running':
                instance_ids.append(instance.id)

        return instance_ids

    def get_mongo_aws_diff(self, mongo_ids, aws_ids):
        """Calculate the difference between Amazon and Aerostat's instances."""
        mongo_ids = set(mongo_ids)
        aws_ids = set(aws_ids)

        return mongo_ids - aws_ids

    def update_mongo(self, diff_ids):
        """Remove diff_ids from mongodb.

        Args:
            diff_ids: list of str, ids which differ between aerostat and aws.
        """
        for diff_id in diff_ids:
            # Just remove the instance_id field. We'll save the hostname for later.
            self.aerostat_db.servers.update(
                    {'instance_id': diff_id}, {
                        '$set':{'instance_id': '', 'ip': ''}})

def main():
    """Main."""
    logging.info('Starting aerostatd %s' % __version__)

    usage = 'usage: %prog [options] arg1 arg2'
    parser = OptionParser(usage=usage)
    parser.add_option(
            '--offline', action='store_true', dest='offline', default=False,
            help='Run in offline mode (No AWS).')

    (options, args) = parser.parse_args()

    now = None
    run_time = None
    aerostatd = Aerostatd(options.offline)
    while 1:
        mongo_ids = aerostatd.get_mongo_instance_ids()
        if not options.offline:
            aws_ids = aerostatd.get_aws_instance_ids()
            diffs = aerostatd.get_mongo_aws_diff(mongo_ids, aws_ids)
            aerostatd.update_mongo(diffs)
        time.sleep(60)


if __name__ == '__main__':

    main()
