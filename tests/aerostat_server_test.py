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


if __name__ == '__main__':
    unittest.main()

