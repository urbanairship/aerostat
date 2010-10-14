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
import time

import aerostat
import git
import yaml

from boto.ec2.connection import EC2Connection

REPO_PATH = '/root/.aerostat/'
CONFIG_REPO_PATH = REPO_PATH + 'configs/'
GIT_CERT = '/root/.aerostat/dev-id'
REPO_URL = 'git@dev:configs'
CONFIG_UPDATE_FREQ = 15


def _read_creds(path=None):
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


def aws_connect():
    """Return connection cursor from EC2."""

    key_id, key_sec, keypair_name = _read_creds()
    return EC2Connection(key_id, key_sec)


def get_mongo_instance_ids(db):
    """Return a list of instance_ids that mongo knows about."""

    return [result['instance_id'] for result in db.servers.find()]


def get_aws_instance_ids(aws_conn):
    """Return a list of instance_ids that EC2 knows about, and are running."""
    aws_reqs = aws_conn.get_all_instances()
    instances = []
    [instances.extend(req.instances) for req in aws_reqs]
    instance_ids = []
    for instance in instances:
        if instance.state == 'running':
            instance_ids.append(instance.id)

    return instance_ids


def get_mongo_aws_diff(mongo_ids, aws_ids):
    """Calculate the difference between Amazon and Aerostat's instances."""
    mongo_ids = set(mongo_ids)
    aws_ids = set(aws_ids)

    return mongo_ids - aws_ids


def update_mongo(db, diff_ids):
    """Remove diff_ids from mongodb.

    Args:
        db: pymongo.Connection.db instance.
        diff_ids: list of str, ids which differ between aerostat and aws.
    """
    for diff_id in diff_ids:
        # Just remove the instance_id field. We'll save the hostname for later.
        db.servers.update(
                {'instance_id': diff_id}, {
                    '$set':{'instance_id': '', 'ip': ''}})


def update_or_clone_repo(repo_path, remote_repo_url):
    """Either update or clone new clone repo.

    Args:
        repo_path: absolute path to repo locally.
        remote_repo_url: url of remote repository.
    Returns:
        git.Repo object
    """
    repo = None
    if not os.path.exists(repo_path):
        repo = git.Repo.clone_from(remote_repo_url, repo_path)
    else:
        repo = git.Repo(repo_path)
        repo.git.reset('--hard')
        repo.git.pull()

    return repo


def get_config_meta_data(sub_repo_path):
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
    if os.path.exists(CONFIG_REPO_PATH + sub_repo_path):
        if os.path.exists(CONFIG_REPO_PATH + meta_file_pattern):
            meta_file = open(CONFIG_REPO_PATH + meta_file_pattern)
            meta_data = yaml.load(meta_file.read())
            meta_file.close()

        if not meta_data:
            meta_data = {'path': '', 'owner': '', 'group': '', 'mode': ''}
        if not meta_data['path']:
            meta_data['path'] = '/etc/%s' % (conf_name,)
        if not meta_data['owner']:
            meta_data['owner'] = 'root'
        if not meta_data['group']:
            meta_data['group'] = 'root'
        if not meta_data['mode']:
            meta_data['mode'] = '0644'

    return meta_data


def save_mongo_configs(db, col_name, file_name, file_contents, meta_data):
    """Save pre-parsed git repo data into mongo."""

    col = getattr(db, col_name, None)
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


def parse_config_data(config):
    """Actually extact file contents and upload to mongodb.

    Args:
        config: str, path to config inside repo.
    """
    if (len(config.split('/')) < 2):
        # This is a malformed configuration, just pass.
        col_name = file_name = file_contents = meta_data = None

    col_name, file_name = config.split('/')
    if file_name.split('.')[-1] == 'meta':
        # We don't enter .meta files directly into mongo.
        col_name = file_name = file_contents = meta_data = None
    else:
        meta_data = get_config_meta_data(config)
        file_contents = ''
        file =  open(CONFIG_REPO_PATH + config)
        file_contents = file.read()
        file.close()

    return (col_name, file_name, file_contents, meta_data)


def do_config_update(db, repo_path, repo_url):
    """Do the configuration update."""

    repo = update_or_clone_repo(repo_path, repo_url)
    repo_configs = repo.git.ls_files().split('\n')

    for config in repo_configs:
        (col_name, file_name, file_contents, meta_data) = parse_config_data(
                config)
        if col_name and file_name and meta_data:
            save_mongo_configs(db, col_name, file_name,
                    file_contents, meta_data)

    return True


def main():
    """Main."""

    mongo_conn = aerostat.db_connect('localhost', 27017)
    db = mongo_conn.aerostat
    aws_conn = aws_connect()
    now = None
    run_time = None
    while 1:
        now = datetime.datetime.now()
        if not run_time:
            do_config_update(
                    mongo_conn.configs, REPO_PATH + 'configs', REPO_URL)
            run_time = datetime.timedelta(minutes=15) + now
        if now > run_time:
            do_config_update(
                    mongo_conn.configs, REPO_PATH + 'configs', REPO_URL)
            run_time = datetime.timedelta(
                    minutes=CONFIG_UPDATE_FREQ) + now # reset

        mongo_ids = get_mongo_instance_ids(db)
        aws_ids = get_aws_instance_ids(aws_conn)
        diffs = get_mongo_aws_diff(mongo_ids, aws_ids)
        update_mongo(db, diffs)
        time.sleep(60)


if __name__ == '__main__':

    main()
