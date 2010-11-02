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
import git
import yaml

from boto.ec2.connection import EC2Connection
from optparse import OptionParser


class Aerostatd(object):

    def __init__(self, offline=False):
        self.offline = offline
        if not self.offline:
            self.aws_conn = self.aws_connect()

        self.mongo_conn = aerostat.db_connect('localhost', 27017)
        self.aerostat_db= self.mongo_conn.aerostat
        self.config_db = self.mongo_conn.configs
        self.repo_path = '/root/.aerostat/'
        self.config_repo_path = self.repo_path + 'configs/'
        self.git_cert = '/root/.aerostat/dev-id'
        self.remote_repo_url = 'git@dev:configs' # This is using as ssh alias
        self.config_update_freq = 10
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

        if conf:
            if 'remote_repo_url' in conf:
                self.remote_repo_url = conf['remote_repo_url']
            if 'git_cert' in conf:
                self.git_cert = conf['git_cert']
            if 'repo_path' in conf:
                self.repo_path = conf['repo_path']
                self.config_repo_path = conf['repo_path'] + '/configs'
            if 'config_update_freq' in conf:
                self.config_update_feq = conf['config_update_freq']

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

    def update_or_clone_repo(self):
        """Either update or clone new clone repo.

        Returns:
            git.Repo object
        """
        repo = None
        if not os.path.exists(self.config_repo_path):
            repo = git.Repo.clone_from(self.remote_repo_url,
                    self.config_repo_path)
        else:
            repo = git.Repo(self.config_repo_path)
            repo.git.reset('--hard')
            repo.git.pull()

        return repo

    def get_config_meta_data(self, sub_repo_path):
        """Get the meta data information for a config file.

        Args:
            sub_repo_path: str, this is the relative path within the repo to
                a configuration file we're interested in.
        Returns:
            a dict storing the desired file meata data. We set a default
            if there isn't a .meta file for the config or if sections are blank.
        """
        meta_file_pattern = sub_repo_path + '.meta'
        meta_data = {}
        conf_name = sub_repo_path.split('/')[-1]
        if os.path.exists(self.config_repo_path + sub_repo_path):
            if os.path.exists(self.config_repo_path + meta_file_pattern):
                meta_file = open(self.config_repo_path + meta_file_pattern)
                data = yaml.load(meta_file.read())
                if data: # In case the .meta file exists, but is empty
                    meta_data = data
                meta_file.close()

            if 'path' not in meta_data:
                meta_data['path'] = '/etc/%s' % (conf_name,)
            if 'owner' not in meta_data:
                meta_data['owner'] = 'root'
            if 'group' not in meta_data:
                meta_data['group'] = 'root'
            if 'mode' not in  meta_data:
                meta_data['mode'] = '0644'

        return meta_data

    def save_mongo_configs(self, col_name, file_name, file_contents, meta_data):
        """Save pre-parsed git repo data into mongo."""

        col = getattr(self.config_db, col_name, None)
        doc = col.find_one({'name': file_name})
        id = None
        if doc: # Our config already exists, just update its data.
            id = col.update(
                    {'name': file_name}, {
                        '$set':{'contents': file_contents,
                                'path': meta_data['path'],
                                'owner': meta_data['owner'],
                                'group': meta_data['group'],
                                'mode': meta_data['mode']}})

        else: # This is a new config. Save it.
            id = col.save({
                'name': file_name,
                'contents': file_contents,
                'path': meta_data['path'],
                'owner': meta_data['owner'],
                'group': meta_data['group'],
                'mode': meta_data['mode']})

        return id

    def parse_config_data(self, config):
        """Actually extact file contents and upload to mongodb.

        Args:
            config: str, path to config inside repo.
        """
        if (len(config.split('/')) < 2):
            # This is a malformed configuration, just pass.
            col_name = file_name = file_contents = meta_data = None
        else:
            col_name, file_name = config.split('/')
            if file_name.split('.')[-1] == 'meta':
                # We don't enter .meta files directly into mongo.
                col_name = file_name = file_contents = meta_data = None
            else:
                meta_data = self.get_config_meta_data(config)
                file_contents = ''
                file = open(self.config_repo_path + config)
                file_contents = file.read()
                file.close()

        return (col_name, file_name, file_contents, meta_data)

    def do_config_update(self):
        """Do the configuration update."""
        if self.offline:
            return False

        repo = self.update_or_clone_repo()
        repo_configs = repo.git.ls_files().split('\n')

        for config in repo_configs:
            (col_name, file_name, file_contents,
                    meta_data) = self.parse_config_data(config)
            if col_name and file_name and meta_data:
                self.save_mongo_configs(col_name, file_name,
                        file_contents, meta_data)

        return True


def main():
    """Main."""

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
        now = datetime.datetime.now()
        if not run_time:
            aerostatd.do_config_update()
            run_time = datetime.timedelta(minutes=15) + now
        if now > run_time:
            aerostat.do_config_update()
            run_time = datetime.timedelta(
                    minutes=aerostatd.config_update_freq) + now # reset

        mongo_ids = aerostatd.get_mongo_instance_ids()
        if not options.offline:
            aws_ids = aerostatd.get_aws_instance_ids()
            diffs = aerostatd.get_mongo_aws_diff(mongo_ids, aws_ids)
            aerostatd.update_mongo(diffs)
        time.sleep(60)


if __name__ == '__main__':

    main()
