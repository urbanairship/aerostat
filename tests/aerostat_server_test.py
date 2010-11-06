#!/usr/bin/env python
"""
Aerostat_Server Unitests.
"""

__author__ = 'Gavin McQuillan (gavin@urbanairship.com)'

import os
import StringIO
import sys
import unittest

import mox
import pymongo
import yaml

from aerostat import aerostat_server

class AerostatServerTest(mox.MoxTestBase):

    def test_read_aerostatd_conf(self):
        """test read_aerostatd_conf function."""
        default_conf_path = '/etc/aerostatd.conf'
        fake_contents = "'remote_repo_url': 'testserver:configs'"
        fake_yaml_output = {'remote_repo_url': 'testserver:configs'}
        fake_conf_file = StringIO.StringIO(fake_contents)
        self.mox.StubOutWithMock(os.path, 'exists')
        os.path.exists(default_conf_path).AndReturn(False)
        os.path.exists(default_conf_path).AndReturn(False)
        os.path.exists(default_conf_path).AndReturn(True)
        self.mox.StubOutWithMock(sys.modules['__builtin__'], 'open')
        sys.modules['__builtin__'].open(default_conf_path, 'r').AndReturn(
                fake_conf_file)
        self.mox.StubOutWithMock(yaml, 'load')
        yaml.load(fake_contents).AndReturn(fake_yaml_output)

        self.mox.ReplayAll()

        fake_aerostatd = aerostat_server.Aerostatd(offline=True)
        self.assertFalse(fake_aerostatd.read_aerostatd_conf())
        self.assertTrue(fake_aerostatd.read_aerostatd_conf())

    def test_read_creds(self):
        """Test _read_creds function."""
        expected_results = ('test-id', 'test-sec', 'test-name')
        fake_creds_file = StringIO.StringIO('test-id\ntest-sec\ntest-name\n')
        self.mox.StubOutWithMock(sys.modules['__builtin__'], 'open')
        sys.modules['__builtin__'].open('/root/installer/.ec2', 'r').AndReturn(
                fake_creds_file)

        fake_aerostatd = aerostat_server.Aerostatd(offline=True)

        self.mox.ReplayAll()

        self.assertEqual(fake_aerostatd._read_creds(), expected_results)

    def test_get_mongo_instance_ids(self):
        """Test get_mongo_instance_ids function."""
        expected_output = ['i-d23lk3kjl']
        fake_row = {'hostname': 'mongodb-master', 'ip': '12.123.234.3',
                'server_type': 'mongodb', 'instance_id': 'i-d23lk3kjl'}

        fake_conn = self.mox.CreateMockAnything()
        fake_db = self.mox.CreateMockAnything()
        fake_conn.aerostat.AndReturn(fake_db)
        fake_db.servers = self.mox.CreateMockAnything()

        fake_db.servers.find().AndReturn([fake_row])

        fake_aerostatd = aerostat_server.Aerostatd(offline=True)
        fake_aerostatd.mongo_conn = fake_conn
        fake_aerostatd.aerostat_db = fake_db

        self.mox.ReplayAll()

        test_output = fake_aerostatd.get_mongo_instance_ids()
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

        fake_aerostatd = aerostat_server.Aerostatd(offline=True)
        fake_aerostatd.aws_conn = fake_connection

        self.mox.ReplayAll()

        test_output = fake_aerostatd.get_aws_instance_ids()

        self.assertEqual(test_output, expected_output)

    def test_get_mongo_aws_diff(self):

        expected_output = set(['test1'])

        fake_mongo_ids = ['test1', 'test2', 'test3']
        fake_aws_ids = ['test2', 'test3']

        fake_aerostatd = aerostat_server.Aerostatd(offline=True)

        self.mox.ReplayAll()

        test_output = fake_aerostatd.get_mongo_aws_diff(
                fake_mongo_ids, fake_aws_ids)

        self.assertEqual(test_output, expected_output)

    def test_update_mongo(self):

        fake_conn = self.mox.CreateMockAnything()
        fake_db = self.mox.CreateMockAnything()
        fake_conn.aerostat = fake_db
        fake_db.servers = self.mox.CreateMockAnything()
        fake_ids = ['i-test1', 'i-test2']

        fake_db.servers.update(
                {'instance_id': 'i-test1'},
                        {'$set': {'instance_id': '', 'ip': ''}}).AndReturn(None)
        fake_db.servers.update(
                {'instance_id': 'i-test2'},
                        {'$set': {'instance_id': '', 'ip': ''}}).AndReturn(None)

        fake_aerostatd = aerostat_server.Aerostatd(offline=True)
        fake_aerostatd.mongo_conn = fake_conn
        fake_aerostatd.aerostat_db = fake_db

        self.mox.ReplayAll()

        self.assertEqual(fake_aerostatd.update_mongo(
                fake_ids), None)

    def test_update_or_clone_repo(self):
        """Test update_or_clone_repo function: update."""

        fake_repo_path = '/tmp/repo'
        fake_repo_url = 'ssh://server/repo'

        fake_git_module = self.mox.CreateMockAnything()
        aerostat_server.git = fake_git_module

        fake_repo = self.mox.CreateMockAnything()
        fake_git = self.mox.CreateMockAnything()

        self.mox.StubOutWithMock(os.path, 'exists')
        os.path.exists('/etc/aerostatd.conf').AndReturn(False)
        os.path.exists(fake_repo_path).AndReturn(True)

        fake_git_module.Repo(fake_repo_path).AndReturn(fake_repo)
        fake_repo.git = fake_git
        fake_git.reset('--hard').AndReturn(None)
        fake_git.pull().AndReturn(None)

        self.mox.ReplayAll()

        fake_aerostatd = aerostat_server.Aerostatd(offline=True)
        fake_aerostatd.config_repo_path = fake_repo_path
        fake_aerostatd.remote_repo_url = fake_repo_url

        test_repo1 = fake_aerostatd.update_or_clone_repo()
        self.assertNotEqual(test_repo1, None)

    def test_update_or_clone_repo_new(self):
        """Test update_or_clone_repo function: new clone."""

        fake_repo_path = '/tmp/repo'
        fake_repo_url = 'ssh://server/repo'

        fake_git_module = self.mox.CreateMockAnything()
        aerostat_server.git = fake_git_module
        fake_repo = self.mox.CreateMockAnything()

        self.mox.StubOutWithMock(os.path, 'exists')
        os.path.exists('/etc/aerostatd.conf').AndReturn(False)
        os.path.exists(fake_repo_path).AndReturn(False)
        fake_git_module.Repo = fake_repo

        fake_repo.clone_from(fake_repo_url, fake_repo_path).AndReturn(fake_repo)

        self.mox.ReplayAll()

        aerostatd = aerostat_server.Aerostatd(offline=True)
        aerostatd.config_repo_path = fake_repo_path
        aerostatd.remote_repo_url = fake_repo_url


        test_repo1 = aerostatd.update_or_clone_repo()
        self.assertNotEqual(test_repo1, None)

    def test_get_config_meta_data(self):
        """Test get_config_meta_data function."""

        expected_meta_data = {
                'path': '/etc/fake_service.config',
                'owner': 'fake_user',
                'group': 'fake_group',
                'mode': '0777'}

        fake_aerostatd = aerostat_server.Aerostatd(offline=True)
        fake_aerostatd.repo_path = fake_global = '/path/to/repo/'
        fake_aerostatd.config_repo_path = '/path/to/repo/'
        fake_sub_path = 'example_service/config.conf'
        fake_meta_path = fake_global + fake_sub_path + '.meta'


        self.mox.StubOutWithMock(os.path, 'exists')
        os.path.exists(fake_global + fake_sub_path).AndReturn(True)
        os.path.exists(fake_meta_path).AndReturn(True)

        fake_meta_file = StringIO.StringIO(
                ("path: /etc/fake_service.config\nowner: fake_user\n"
                 "group: fake_group\nmode: '0777'\n"))

        self.mox.StubOutWithMock(sys.modules['__builtin__'], 'open')
        sys.modules['__builtin__'].open(fake_meta_path).AndReturn(
                fake_meta_file)

        self.mox.ReplayAll()

        test_meta_data = fake_aerostatd.get_config_meta_data(fake_sub_path)
        self.assertEqual(test_meta_data, expected_meta_data)

    def test_get_config_meta_data_no_file(self):
        """Test get_config_meta_data function when there is no meta file."""

        expected_meta_data = {
                'path': '/etc/config.conf',
                'owner': 'root',
                'group': 'root',
                'mode': '0644'}

        fake_global = '/path/to/repo/configs/'
        fake_sub_path = 'example_service/config.conf'
        fake_config_path = fake_global + fake_sub_path
        fake_meta_path = fake_config_path + '.meta'

        self.mox.StubOutWithMock(os.path, 'exists')
        os.path.exists('/etc/aerostatd.conf').AndReturn(False)
        os.path.exists(fake_config_path).AndReturn(True)
        # Now suppose .meta file doesn't exist.
        os.path.exists(fake_meta_path).AndReturn(False)
        # Now suppose there's no config at all.
        os.path.exists(fake_config_path).AndReturn(False)

        self.mox.ReplayAll()

        fake_aerostatd = aerostat_server.Aerostatd(offline=True)
        fake_aerostatd.config_repo_path = fake_global
        test_meta_data = fake_aerostatd.get_config_meta_data(fake_sub_path)

        self.assertEqual(test_meta_data, expected_meta_data)
        self.assertEqual({},
                fake_aerostatd.get_config_meta_data(fake_sub_path))

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

        aerostatd = aerostat_server.Aerostatd(offline=True)
        self.mox.StubOutWithMock(aerostatd.config_db, '__getattr__')
        fake_col = self.mox.CreateMock(pymongo.collection.Collection)
        aerostatd.config_db.__getattr__('test').AndReturn(fake_col)
        fake_col.find_one({'name': fake_config_name}).AndReturn(
                fake_mongo_data)


        # Just update with the same information.
        fake_col.update({'name': fake_config_name}, {
            '$set':{'contents': 'fake contents',
                    'path': '/path/to/config.conf',
                    'owner': 'somebody',
                    'group': 'somepeople',
                    'mode': '0664'}})

        self.mox.ReplayAll()

        aerostatd.save_mongo_configs(
            'test', fake_config_name, 'fake contents', fake_meta_data)

    def test_parse_config_data(self):
        """Test parse_config_data function."""

        fake_aerostatd = aerostat_server.Aerostatd(offline=True)
        fake_aerostatd.config_repo_path = fake_repo = '/path/to/repo'
        fake_aerostatd.repo_path = '/path/to/repo'
        fake_config = 'test/config.conf'
        fake_file_contents = 'config data!'
        fake_meta_data = {
                'path': '/path/to/config.conf',
                'owner': 'somebody',
                'group': 'somepeople',
                'mode': '0664'}
        self.mox.StubOutWithMock(fake_aerostatd, 'get_config_meta_data')
        fake_aerostatd.get_config_meta_data(fake_config).AndReturn(fake_meta_data)
        fake_file = StringIO.StringIO(fake_file_contents)

        self.mox.StubOutWithMock(sys.modules['__builtin__'], 'open')
        sys.modules['__builtin__'].open(os.path.join(fake_repo, fake_config)) \
                .AndReturn(fake_file)

        expected_output = (
                'test', 'config.conf', fake_file_contents, fake_meta_data)

        self.mox.ReplayAll()

        self.assertEqual(fake_aerostatd.parse_config_data(fake_config),
               expected_output)

    def test_do_config_update(self):
        """Test do_config_update function."""
        fake_aerostatd = aerostat_server.Aerostatd(offline=True)
        fake_aerostatd.conf_repo_path = '/path/to/repo/'
        fake_db = self.mox.CreateMockAnything()
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

        fake_aerostatd.remote_repo_url = fake_repo_url
        fake_aerostatd.config_db = fake_db

        self.mox.StubOutWithMock(fake_aerostatd, 'update_or_clone_repo')
        fake_aerostatd.update_or_clone_repo().AndReturn(fake_repo)

        self.mox.StubOutWithMock(fake_aerostatd, 'parse_config_data')
        fake_aerostatd.parse_config_data('test/config.conf').AndReturn((
                fake_col_name, fake_file_name, '', fake_meta_data))

        self.mox.StubOutWithMock(fake_aerostatd, 'save_mongo_configs')
        fake_aerostatd.save_mongo_configs(fake_col_name,
                fake_file_name, '', fake_meta_data).AndReturn(12)

        self.mox.ReplayAll()
        result = fake_aerostatd.do_config_update()
        self.mox.VerifyAll()
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()

