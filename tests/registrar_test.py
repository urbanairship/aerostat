#!/usr/bin/env python

"""
Aerostat Registrar Unittests
"""

import os
import StringIO
import sys
import unittest

import mox

from aerostat import aerostat
from aerostat import registrar

class RegistrarTest(mox.MoxTestBase):
    """Test Class for Aerostat (client) module."""

    def test_get_types_masterful(self):
        """test get_types function for masterful service_types."""

        fake_host_file = StringIO.StringIO('mongodb masterful')
        fake_results = ['mongodb', 'masterful']
        self.mox.StubOutWithMock(sys.modules['__builtin__'], 'open')
        sys.modules['__builtin__'].open('/etc/aerostat_info', 'r').AndReturn(
                fake_host_file)

        self.mox.ReplayAll()

        fake_registrar = registrar.Registrar()

        self.assertEqual(fake_registrar.get_types(), fake_results)

    def test_get_types_iterative(self):
        """test get_types function for iterative service_types."""

        fake_host_file = StringIO.StringIO('web')
        fake_results = ['web']
        self.mox.StubOutWithMock(sys.modules['__builtin__'], 'open')
        sys.modules['__builtin__'].open('/etc/aerostat_info', 'r').AndReturn(
                fake_host_file)

        self.mox.ReplayAll()

        fake_registrar = registrar.Registrar()

        self.assertEqual(fake_registrar.get_types(), fake_results)

    def test_get_types_aliases(self):
        """test get_types for when aliases are supplied."""

        fake_host_file = StringIO.StringIO('web iterative web-master web-slave')
        fake_results = ['web', 'iterative', 'web-master', 'web-slave']
        self.mox.StubOutWithMock(sys.modules['__builtin__'], 'open')
        sys.modules['__builtin__'].open('/etc/aerostat_info', 'r').AndReturn(
                fake_host_file)

        self.mox.ReplayAll()

        fake_registrar = registrar.Registrar()

        self.assertEqual(fake_registrar.get_types(), fake_results)

    def test_get_smallest_gap(self):
        """test get_smallest_gap function."""

        expected_hostname = 'cassandra-1'

        fake_service = 'cassandra'
        fake_results = [
                {u'instance_id': u'',
                 u'ip': u'10.212.127.1',
                 u'_id': '4bd60012bcd9590caa000002',
                 u'hostname': u'cassandra-2',
                 u'server_type': u'cassandra'},
                {u'instance_id': u'',
                 u'ip': u'10.212.127.34',
                 u'_id': '4bd60012bcd9590caa000001',
                 u'hostname': u'cassandra-1',
                 u'server_type': u'cassandra'}]

        fake_db = self.mox.CreateMockAnything()
        fake_db.servers = self.mox.CreateMockAnything()
        fake_db.servers.find(
                {'instance_id': '', 'service': fake_service}).AndReturn(
                        fake_results)

        self.mox.ReplayAll()

        fake_registrar = registrar.Registrar()
        test_hostname = fake_registrar.get_smallest_gap(fake_db, fake_service)

        self.assertEqual(test_hostname, expected_hostname)

    def test_hostname_instance_exists(self):
        """Test negative and postitive cases of inst/host combo existing."""

        test_hostname1 = 'mongodb-master'

        fake_results1 = {
                 u'instance_id': u'i-tester',
                 u'ip': u'10.212.127.1',
                 u'_id': '4bd60012bcd9590caa000000',
                 u'hostname': u'mongodb-master',
                 u'server_type': u'mongodb',
                 u'aliases': ['mongodb-masta']}

        fake_results2 = {
                 u'instance_id': u'',
                 u'ip': u'10.212.127.1',
                 u'_id': '4bd60012bcd9590caa000000',
                 u'hostname': u'mongodb-master',
                 u'server_type': u'mongodb',
                 u'aliases': ['mongodb-masta']}


        fake_db = self.mox.CreateMockAnything()
        fake_db.servers = self.mox.CreateMockAnything()

        fake_db.servers.find_one = self.mox.CreateMockAnything()
        fake_db.servers.find_one({'hostname': test_hostname1}).AndReturn(
                fake_results1)
        fake_db.servers.find_one({'hostname': test_hostname1}).AndReturn(
                fake_results2)

        self.mox.ReplayAll()

        fake_registrar = registrar.Registrar()

        self.assertTrue(fake_registrar.hostname_instance_exists(
                fake_db, test_hostname1))
        self.assertFalse(fake_registrar.hostname_instance_exists(
                fake_db, test_hostname1))


    def test_alias_exists(self):
        """Test postitive and negative cases for aliases existing."""

        expected_good_output = ['cassandra-giga']

        test_aliases1 = ['cassandra-test']
        test_aliases2 = ['cassandra-mega', 'cassandra-giga']
        fake_results1 = []
        fake_results2 = [
                {u'instance_id': u'',
                 u'ip': u'10.212.127.1',
                 u'_id': '4bd60012bcd9590caa000000',
                 u'hostname': u'cassandra-0',
                 u'server_type': u'cassandra',
                 u'aliases': ['cassandra-giga']}]

        fake_db = self.mox.CreateMockAnything()
        fake_db.servers = self.mox.CreateMockAnything()
        fake_db.servers.find({'aliases': {'$in' : test_aliases1}}).AndReturn(
                fake_results1)
        fake_db.servers.find({'aliases': {'$in': test_aliases2}}).AndReturn(
                fake_results2)

        self.mox.ReplayAll()

        fake_registrar = registrar.Registrar()

        self.assertFalse(fake_registrar.alias_exists(fake_db, test_aliases1))
        self.assertEqual(fake_registrar.alias_exists(
                fake_db, test_aliases2), expected_good_output)

    def test_change_hostname(self):
        """test change_hostname function."""

        fake_inst = 'fake_inst'
        fake_host = 'fake_host'
        fake_db = self.mox.CreateMockAnything()
        fake_db.servers = self.mox.CreateMockAnything()
        fake_db.servers.update(
                {'instance_id': fake_inst},
                {'$set':
                    {'hostname': fake_host}}).AndReturn(None)
        fake_db.servers.update(
                {'hostname': fake_host},
                {'$set':
                    {'hostname': fake_host}}).AndReturn(None)

        self.mox.ReplayAll()

        fake_registrar = registrar.Registrar()

        self.assertTrue(fake_registrar.change_hostname(
                fake_db, fake_host, inst=fake_inst))
        self.assertTrue(fake_registrar.change_hostname(
                fake_db, fake_host, host=fake_host))

        self.assertFalse(fake_registrar.change_hostname(
                fake_db, fake_host))
        self.assertFalse(fake_registrar.change_hostname(
                fake_db, fake_host, host=fake_host, inst=fake_inst))

    def test_change_master(self):
        """Test change_master function."""

        fake_service = 'testing'
        fake_service_type = 'masterful'
        test_inst1 = 'test-instance1'
        test_inst2 = 'test-instance2'
        master_inst = test_inst2
        master_hostname = 'testing-master'
        slave_hostname = 'tesing-slave-1'

        fake_db = self.mox.CreateMockAnything()
        fake_registrar = registrar.Registrar()

        self.mox.StubOutWithMock(aerostat, 'check_master')
        aerostat.check_master(
                fake_db, fake_service, test_inst1).AndReturn(False)
        aerostat.check_master(
                fake_db, fake_service, test_inst2).AndReturn(True)

        self.mox.StubOutWithMock(aerostat, 'get_master')
        aerostat.get_master(fake_db, fake_service).AndReturn(
                master_inst)

        self.mox.StubOutWithMock(fake_registrar, 'change_hostname')
        fake_registrar.change_hostname(fake_db, '', inst=master_inst)
        fake_registrar.change_hostname(fake_db, '', inst=test_inst1)
        fake_registrar.change_hostname(fake_db, master_hostname,
                inst=test_inst1)
        fake_registrar.change_hostname(fake_db, slave_hostname,
                inst=master_inst)

        self.mox.StubOutWithMock(fake_registrar, 'pick_name')
        # This should only be called when replacing the master.
        fake_registrar.pick_name(fake_db, fake_service, fake_service_type,
                test_inst2).AndReturn(slave_hostname)

        self.mox.ReplayAll()

        self.assertTrue(fake_registrar.change_master(
                fake_db, fake_service, fake_service_type, test_inst1))
        self.assertFalse(fake_registrar.change_master(
                fake_db, fake_service, fake_service_type, test_inst2))

    def test_pick_name(self):
        """Test pick_name function under normal parameters."""

        expected_hostname = 'mongodb-slave-1'

        fake_service = 'mongodb'
        fake_service_type = 'masterful'
        fake_instance_id = 'i-test'

        fake_row = {
                'hostname': 'mongodb-master',
                'ip': '12.123.234.3',
                'service': 'mongodb',
                'service_type': 'masterful',
                'instance_id': 'i-d23lk3kjl'}

        fake_db = self.mox.CreateMockAnything()
        fake_db.servers = self.mox.CreateMockAnything()
        # I'm cheating here by using a list instead of an iterable obj.

        fake_registrar = registrar.Registrar()
        self.mox.StubOutWithMock(aerostat, 'hostname_exists')
        self.mox.StubOutWithMock(fake_registrar, 'hostname_instance_exists')
        self.mox.StubOutWithMock(fake_registrar, 'check_dup')
        self.mox.StubOutWithMock(fake_registrar, 'get_smallest_gap')

        aerostat.hostname_exists(
                fake_db, 'mongodb-master').AndReturn(True)
        fake_registrar.hostname_instance_exists(
                fake_db, 'mongodb-master').AndReturn(True)
        fake_registrar.check_dup(fake_db, fake_instance_id).AndReturn(False)
        fake_registrar.get_smallest_gap(fake_db, fake_service).AndReturn('mongodb-slave-1')

        # I'm cheating here by using a list instead of an iterable obj.
        fake_db.servers.find(
                {'service': fake_service}).AndReturn([fake_row])

        self.mox.ReplayAll()

        test_hostname = fake_registrar.pick_name(fake_db, fake_service,
                fake_service_type, fake_instance_id)

        self.assertEqual(test_hostname, expected_hostname)

    def test_pick_name_duplicate_inst(self):
        """test pick_name function when there is a duplicate."""

        expected_hostname = None

        fake_service = 'mongodb'
        fake_service_type = 'masterful'
        fake_instance_id = 'i-test'

        fake_db = self.mox.CreateMockAnything()

        fake_db.servers = self.mox.CreateMockAnything()
        fake_registrar = registrar.Registrar()

        self.mox.StubOutWithMock(aerostat, 'get_hostname')
        aerostat.get_hostname(fake_db, fake_instance_id).AndReturn(
                'mongodb-master')
        self.mox.StubOutWithMock(fake_registrar, 'check_dup')
        fake_registrar.check_dup(fake_db, fake_instance_id).AndReturn(True)

        self.mox.ReplayAll()

        test_hostname = fake_registrar.pick_name(
                fake_db, fake_service,
                fake_service_type, fake_instance_id)

        self.assertEqual(test_hostname, expected_hostname)

    def test_pick_name_duplicate_inst_no_host(self):
        """test pick_name when there is a duplicate, but no hostname."""

        # This tests the case where a master name swap is underway.
        # the <service>-master hostname is removed from the former instance.
        # then added to the new master. Meanwhile, the old master needs
        # to have a name picked. So we ignore the fact that its instance_id
        # is already in the database as long as it has no hostname.

        # Replace fallen master.
        expected_hostname1 = 'mongodb-master'
        # You were master, replace gap in slave names.
        expected_hostname2 = 'mongodb-slave-1'

        fake_service = 'mongodb'
        fake_service_type = 'masterful'
        fake_instance_id1 = 'i-test'
        fake_instance_id2 = 'i-test2'

        # Missing Master
        fake_row1 = {'hostname': '', 'ip': '12.123.234.3',
                'service': 'mongodb', 'service_type': 'masterful',
                'instance_id': 'i-test'}

        # Missing Slave
        fake_row2 = [
                fake_row1,
                {'hostname': 'mongodb-master', 'ip': '12.1.1.2',
                 'service': 'mongodb', 'service_type': 'masterful',
                 'instance_id': 'i-test2'}]

        fake_db = self.mox.CreateMockAnything()

        fake_db.servers = self.mox.CreateMockAnything()
        fake_db.servers.find(
                {'service': fake_service}).AndReturn([fake_row1])
        fake_db.servers.find(
                {'service': fake_service}).AndReturn(fake_row2)

        fake_registrar = registrar.Registrar()

        self.mox.StubOutWithMock(aerostat, 'get_hostname')
        aerostat.get_hostname(fake_db, fake_instance_id1).AndReturn(
                '')
        aerostat.get_hostname(fake_db, fake_instance_id2).AndReturn(
                '')

        self.mox.StubOutWithMock(fake_registrar, 'check_dup')
        fake_registrar.check_dup(fake_db, fake_instance_id1).AndReturn(True)
        fake_registrar.check_dup(fake_db, fake_instance_id2).AndReturn(True)

        # Called for Slave.
        self.mox.StubOutWithMock(aerostat, 'hostname_exists')
        aerostat.hostname_exists(
                fake_db, 'mongodb-master').AndReturn(True)

        self.mox.StubOutWithMock(fake_registrar, 'hostname_instance_exists')
        fake_registrar.hostname_instance_exists(
                fake_db, 'mongodb-master').AndReturn(True)

        self.mox.StubOutWithMock(fake_registrar, 'get_smallest_gap')
        fake_registrar.get_smallest_gap(fake_db, fake_service).AndReturn(expected_hostname2)

        self.mox.ReplayAll()

        test_hostname1 = fake_registrar.pick_name(
                fake_db, fake_service,
                fake_service_type, fake_instance_id1)

        test_hostname2 = fake_registrar.pick_name(
                fake_db, fake_service,
                fake_service_type, fake_instance_id2)

        self.assertEqual(test_hostname1, expected_hostname1)
        self.assertEqual(test_hostname2, expected_hostname2)


    def test_reset_conflict_aliases(self):
        """"test resetting conflict aliases on mongodb."""

        fake_conflicts = ['test']
        fake_row = {
                'hostname': 'mongodb-slave-1',
                'ip': '12.123.234.5',
                'service': 'mongodb',
                'service_type': 'masterful',
                'instance_id': 'i-23426',
                'aliases': ['test', 'not_test']}

        fake_db = self.mox.CreateMockAnything()
        fake_db.servers = self.mox.CreateMockAnything()
        fake_db.servers.find({'aliases' : { '$in' : ['test']}}).AndReturn(
                [fake_row])
        fake_db.servers.update({'instance_id': 'i-23426'},
                {'$set': {'aliases': ['not_test']}})

        self.mox.ReplayAll()

        fake_registrar = registrar.Registrar()

        self.assertTrue(
                fake_registrar.reset_conflict_aliases(fake_db, fake_conflicts))

    def test_register_name(self):
        """Test registration of new hostnames."""

        fake_hostname = 'mongodb-slave-1'
        fake_ip = '12.123.234.5'
        fake_instance_id = 'i-23426'
        fake_service = 'mongodb'
        fake_service_type = 'masterful'
        fake_aliases = []

        fake_row = {
                'hostname': 'mongodb-slave-1',
                'ip': '12.123.234.5',
                'service': 'mongodb',
                'service_type': 'masterful',
                'instance_id': 'i-23426',
                'aliases': []}

        fake_hostname_exists = False

        fake_db = self.mox.CreateMockAnything()
        fake_db.servers = self.mox.CreateMockAnything()
        fake_db.servers.insert(fake_row).AndReturn(None)

        fake_registrar = registrar.Registrar()
        self.mox.StubOutWithMock(aerostat, 'hostname_exists')
        aerostat.hostname_exists(fake_db, fake_hostname).AndReturn(
                fake_hostname_exists)

        self.mox.ReplayAll()

        test_value = fake_registrar.register_name(
                fake_db, fake_hostname, fake_ip,
                fake_instance_id, fake_service, fake_service_type, fake_aliases)

        self.assertTrue(test_value)

    def test_set_sys_hostname(self):
        """test set_sys_hostname."""

        self.mox.StubOutWithMock(os, 'system')
        os.system('/bin/hostname mongodb-slave-1').AndReturn(0)

        self.mox.StubOutWithMock(os, 'remove')
        os.remove('/etc/hostname').AndReturn(0)


        fake_hostname_file = StringIO.StringIO()
        self.mox.StubOutWithMock(sys.modules['__builtin__'], 'open')
        sys.modules['__builtin__'].open('/etc/hostname', 'w').AndReturn(
                fake_hostname_file)

        self.mox.ReplayAll()

        fake_registrar = registrar.Registrar()

        self.assertTrue(fake_registrar.set_sys_hostname('mongodb-slave-1'))

    def test_parse_service_info(self):
        """test parse_service_info function."""

        expected_first = ('web', 'iterative', None)
        expected_second = ('web', 'masterful', None)
        expected_third = ('web', 'masterful', ['webby-prime', 'webby-mega'])

        fake_registrar = registrar.Registrar()

        self.mox.StubOutWithMock(fake_registrar, 'get_types')

        fake_types_simple = ['web']
        fake_types_adv = ['web', 'masterful']
        fake_types_complex = ['web', 'masterful', 'webby-prime', 'webby-mega']

        fake_registrar.get_types().AndReturn(fake_types_simple)
        fake_registrar.get_types().AndReturn(fake_types_adv)
        fake_registrar.get_types().AndReturn(fake_types_complex)

        self.mox.ReplayAll()

        self.assertEqual(
                fake_registrar.parse_service_info(), expected_first)
        self.assertEqual(
                fake_registrar.parse_service_info(), expected_second)
        self.assertEqual(
                fake_registrar.parse_service_info(), expected_third)


if __name__ == '__main__':
    unittest.main()
