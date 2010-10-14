#!/usr/bin/env python
"""
Aerostat_Server Unitests.
"""

__author__ = 'Gavin McQuillan (gavin@urbanairship.com)'

import os
import StringIO
import sys
import urllib2
import unittest

import boto
import git
import mox
import pymongo

from aerostat import aerostat
from aerostat import aerostat_server
from boto.ec2.connection import EC2Connection

class AerostatServerTest(mox.MoxTestBase):

    def test_read_creds(self):
        """Test _read_creds function."""
        expected_results = ('test-id', 'test-sec', 'test-name')
        fake_creds_file = StringIO.StringIO('test-id\ntest-sec\ntest-name\n')
        self.mox.StubOutWithMock(sys.modules['__builtin__'], 'open')
        sys.modules['__builtin__'].open('/root/installer/.ec2', 'r').AndReturn(
                fake_creds_file)

        self.mox.ReplayAll()

        self.assertEqual(aerostat_server._read_creds(), expected_results)

    def test_get_mongo_instance_ids(self):

        expected_output = ['i-d23lk3kjl']

        fake_row = {'hostname': 'mongodb-master', 'ip': '12.123.234.3',
                'server_type': 'mongodb', 'instance_id': 'i-d23lk3kjl'}

        fake_db = self.mox.CreateMockAnything()
        fake_db.servers = self.mox.CreateMockAnything()

        fake_db.servers.find().AndReturn([fake_row])

        self.mox.ReplayAll()

        test_output = aerostat_server.get_mongo_instance_ids(fake_db)
        self.assertEqual(test_output, expected_output)

    def test_get_aws_instance_ids(self):

        expected_output = ['i-test1']

        fake_req1 = self.mox.CreateMockAnything()
        fake_inst1 = self.mox.CreateMockAnything()
        fake_inst1.id = 'i-test1'
        fake_inst1.state = 'running'
        fake_req1.instances = [fake_inst1]
        fake_req2 = self.mox.CreateMockAnything()
        fake_inst2 = self.mox.CreateMockAnything()
        fake_inst2.id = 'i-test2'
        fake_inst2.state = 'terminated'
        fake_req2.instances = [fake_inst2]

        fake_connection = self.mox.CreateMockAnything()
        fake_connection.get_all_instances().AndReturn(
                [fake_req1, fake_req2])

        self.mox.ReplayAll()

        test_output = aerostat_server.get_aws_instance_ids(fake_connection)

        self.assertEqual(test_output, expected_output)

    def test_get_mongo_aws_diff(self):

        expected_output = set(['test1'])

        fake_mongo_ids = ['test1', 'test2', 'test3']
        fake_aws_ids = ['test2', 'test3']

        self.mox.ReplayAll()

        test_output = aerostat_server.get_mongo_aws_diff(
                fake_mongo_ids, fake_aws_ids)

        self.assertEqual(test_output, expected_output)

    def test_update_mongo(self):

        fake_db = self.mox.CreateMockAnything()
        fake_db.servers = self.mox.CreateMockAnything()
        fake_ids = ['i-test1', 'i-test2']

        fake_db.servers.update(
                {'instance_id': 'i-test1'},
                        {'$set': {'instance_id': '', 'ip': ''}}).AndReturn(None)
        fake_db.servers.update(
                {'instance_id': 'i-test2'},
                        {'$set': {'instance_id': '', 'ip': ''}}).AndReturn(None)

        self.mox.ReplayAll()

        self.assertEqual(aerostat_server.update_mongo(
                fake_db, fake_ids), None)

    def test_update_or_clone_repo(self):
        """Test update_or_clone_repo function: update."""

        fake_repo_path = '/tmp/repo'
        fake_repo_url = 'ssh://server/repo'

        fake_git_module = self.mox.CreateMockAnything()
        aerostat_server.git = fake_git_module

        fake_repo = self.mox.CreateMockAnything()
        fake_git = self.mox.CreateMockAnything()

        self.mox.StubOutWithMock(os.path, 'exists')
        os.path.exists(fake_repo_path).AndReturn(True)

        fake_git_module.Repo(fake_repo_path).AndReturn(fake_repo)
        fake_repo.git = fake_git
        fake_git.reset('--hard').AndReturn(None)
        fake_git.pull().AndReturn(None)

        self.mox.ReplayAll()

        test_repo1 = aerostat_server.update_or_clone_repo(fake_repo_path, fake_repo_url)
        self.assertNotEqual(test_repo1, None)

    def test_update_or_clone_repo_new(self):
        """Test update_or_clone_repo function: new clone."""

        fake_repo_path = '/tmp/repo'
        fake_repo_url = 'ssh://server/repo'

        fake_git_module = self.mox.CreateMockAnything()
        aerostat_server.git = fake_git_module

        fake_repo = self.mox.CreateMockAnything()
        fake_git = self.mox.CreateMockAnything()

        self.mox.StubOutWithMock(os.path, 'exists')
        os.path.exists(fake_repo_path).AndReturn(False)
        fake_git_module.Repo = fake_repo

        fake_repo.clone_from(fake_repo_url, fake_repo_path).AndReturn(fake_repo)

        self.mox.ReplayAll()

        test_repo1 = aerostat_server.update_or_clone_repo(fake_repo_path, fake_repo_url)
        self.assertNotEqual(test_repo1, None)

    def test_get_config_meta_data(self):
        """Test get_config_meta_data function."""

        expected_meta_data = {
                'path': '/etc/fake_service.config',
                'owner': 'fake_user',
                'group': 'fake_group',
                'mode': '0777'}

        aerostat_server.CONFIG_REPO_PATH = fake_global = '/path/to/repo/'
        fake_repo_path = 'example_service/config.conf'
        fake_meta_path = fake_global + fake_repo_path + '.meta'


        self.mox.StubOutWithMock(os.path, 'exists')
        os.path.exists(fake_global + fake_repo_path).AndReturn(True)
        os.path.exists(fake_meta_path).AndReturn(True)

        fake_meta_file = StringIO.StringIO(
                ("path: /etc/fake_service.config\nowner: fake_user\n"
                 "group: fake_group\nmode: '0777'\n"))

        self.mox.StubOutWithMock(sys.modules['__builtin__'], 'open')
        sys.modules['__builtin__'].open(fake_meta_path).AndReturn(
                fake_meta_file)

        self.mox.ReplayAll()

        test_meta_data = aerostat_server.get_config_meta_data(fake_repo_path)
        self.assertEqual(test_meta_data, expected_meta_data)

    def test_get_config_meta_data_no_file(self):
        """Test get_config_meta_data function when there is no meta file."""

        expected_meta_data = {
                'path': '/etc/config.conf',
                'owner': 'root',
                'group': 'root',
                'mode': '0644'}

        aerostat_server.CONFIG_REPO_PATH = fake_global = '/path/to/repo/'
        fake_repo_path = 'example_service/config.conf'
        fake_meta_path = fake_global + fake_repo_path + '.meta'


        self.mox.StubOutWithMock(os.path, 'exists')
        os.path.exists(fake_global + fake_repo_path).AndReturn(True)
        # Now suppose .meta file doesn't exist.
        os.path.exists(fake_meta_path).AndReturn(False)
        # Now suppose there's no config at all.
        os.path.exists(fake_global + fake_repo_path).AndReturn(None)

        self.mox.ReplayAll()

        test_meta_data = aerostat_server.get_config_meta_data(fake_repo_path)
        self.assertEqual(test_meta_data, expected_meta_data)
        self.assertEqual({},
                aerostat_server.get_config_meta_data(fake_repo_path))

    def test_save_mongo_configs(self):
        """Test save_mongo_configs function."""

        fake_mongo_data = {
                'name': 'config.conf',
                'path': '/path/to/config.conf',
                'owner': 'somebody',
                'group': 'somepeople',
                'mode': '0664'}
        fake_config_name = 'config.conf'
        fake_meta_data = {
                'path': '/path/to/config.conf',
                'owner': 'somebody',
                'group': 'somepeople',
                'mode': '0664'}
        fake_db = self.mox.CreateMockAnything()
        fake_col = self.mox.CreateMockAnything()
        fake_col.find_one({'name': fake_config_name}).AndReturn(
                fake_mongo_data)
        # Just update with the same information.
        fake_col.update({'name': fake_config_name}, {
            '$set':{'contents': '',
                    'path': '/path/to/config.conf',
                    'owner': 'somebody',
                    'group': 'somepeople',
                    'mode': '0664'}}).AndReturn(12)
        fake_db.test = fake_col

        self.mox.ReplayAll()

        self.assertEqual(12, aerostat_server.save_mongo_configs(
            fake_db, 'test', fake_config_name, '', fake_meta_data))

    def test_parse_config_data(self):
        """Test parse_config_data function."""

        aerostat_server.CONFIG_REPO_PATH = fake_global = '/path/to/repo/'
        fake_config = 'test/config.conf'
        fake_file_contents = 'config data!'
        fake_meta_data = {
                'path': '/path/to/config.conf',
                'owner': 'somebody',
                'group': 'somepeople',
                'mode': '0664'}
        self.mox.StubOutWithMock(aerostat_server, 'get_config_meta_data')
        aerostat_server.get_config_meta_data(fake_config).AndReturn(fake_meta_data)
        fake_file = StringIO.StringIO(fake_file_contents)

        self.mox.StubOutWithMock(sys.modules['__builtin__'], 'open')
        sys.modules['__builtin__'].open(fake_global + fake_config).AndReturn(
                fake_file)

        expected_output = (
                'test', 'config.conf', fake_file_contents, fake_meta_data)

        self.mox.ReplayAll()

        self.assertEqual(aerostat_server.parse_config_data(fake_config),
               expected_output)

    def test_do_config_update(self):
        """Test do_config_update function."""

        aerostat_server.CONFIG_REPO_PATH = fake_global = '/path/to/repo/'
        fake_db = self.mox.CreateMockAnything()
        fake_repo_path = 'test/config.conf'
        fake_repo_url = 'ssh://server/repo'
        fake_repo = self.mox.CreateMockAnything()
        fake_repo_files = 'test/config.conf'
        fake_git = self.mox.CreateMockAnything()
        fake_repo.git = fake_git
        fake_git.ls_files().AndReturn(fake_repo_files)
        fake_meta_data = {
                'path': '/path/to/config.conf',
                'owner': 'somebody',
                'group': 'somepeople',
                'mode': '0664'}
        fake_col_name = 'test'
        fake_file_name = 'config.conf'

        self.mox.StubOutWithMock(aerostat_server, 'update_or_clone_repo')
        aerostat_server.update_or_clone_repo(
                fake_global, fake_repo_url).AndReturn(fake_repo)

        self.mox.StubOutWithMock(aerostat_server, 'parse_config_data')
        aerostat_server.parse_config_data('test/config.conf').AndReturn((
                fake_col_name, fake_file_name, '', fake_meta_data))

        self.mox.StubOutWithMock(aerostat_server, 'save_mongo_configs')
        aerostat_server.save_mongo_configs(fake_db, fake_col_name,
                fake_file_name, '', fake_meta_data).AndReturn(12)

        self.mox.ReplayAll()

        self.assertTrue(aerostat_server.do_config_update(
            fake_db, fake_global, fake_repo_url))


if __name__ == '__main__':
    unittest.main()

