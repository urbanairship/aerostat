#!/usr/bin/env python
"""
Aerostat Unittests.
"""

__author__ = 'Gavin McQuillan (gavin@urbanairship.com)'
__copyright__ = 'Copyright 2010, UrbanAirship'

import urllib2
import unittest

import mox
from aerostat import aerostat

class AerostatTest(mox.MoxTestBase):

    def test_get_aws_data(self):
        """test get_aws_data function ensure that Amazon logic is good."""
        fake_instance_id = 'i-123d234'
        fake_ip = '123.234.123.3'
        self.mox.StubOutWithMock(urllib2, 'urlopen')
        fake_urlopen = self.mox.CreateMockAnything()
        fake_urlopen.read().AndReturn(fake_instance_id)
        fake_urlopen.read().AndReturn(fake_ip)

        urllib2.urlopen('http://169.254.169.254/'
                'latest/meta-data/instance-id').AndReturn(fake_urlopen)

        urllib2.urlopen('http://169.254.169.254/'
                'latest/meta-data/local-ipv4').AndReturn(fake_urlopen)

        self.mox.ReplayAll()

        test_instance_id, test_ip = aerostat.get_aws_data()

        self.assertEqual(test_instance_id, fake_instance_id)
        self.assertEqual(test_ip, fake_ip)


    def test_hostname_exists(self):
        """test hostname_exists function for negative and positive cases."""

        test_hostname1 = 'cassandra-0'
        test_hostname2 = 'cassandra-1'

        fake_db = self.mox.CreateMockAnything()
        fake_db.servers = self.mox.CreateMockAnything()
        fake_cursor_true = self.mox.CreateMockAnything()
        fake_cursor_true.count().AndReturn(1)

        fake_cursor_false = self.mox.CreateMockAnything()
        fake_cursor_false.count().AndReturn(0)

        fake_db.servers.find(
                {'hostname': test_hostname1}).AndReturn(fake_cursor_true)
        fake_db.servers.find(
                {'hostname': test_hostname2}).AndReturn(fake_cursor_false)

        self.mox.ReplayAll()

        self.assertTrue(aerostat.hostname_exists(fake_db, test_hostname1))
        self.assertFalse(aerostat.hostname_exists(
                fake_db, test_hostname2))


    def test_get_hostname(self):
        """Test get_hostname function."""

        expected_output = 'some-service-0'

        fake_row = {'hostname': 'some-service-0', 'instance_id': 'test-inst-id'}
        fake_db = self.mox.CreateMockAnything()
        fake_db.servers = self.mox.CreateMockAnything()
        fake_db.servers.find_one({'instance_id': 'test-inst-id'}).AndReturn(
                fake_row)

        self.mox.ReplayAll()


        self.assertEqual(expected_output,
                aerostat.get_hostname(fake_db, 'test-inst-id'))


    def test_get_master(self):
        """Test get_master function."""

        expected_output1 = 'master-instance-id'
        expected_output2 = None

        fake_row1 = {'hostname': 'testing-master',
                'instance_id': 'master-instance-id', 'service': 'testing'}

        fake_db = self.mox.CreateMockAnything()
        fake_db.servers = self.mox.CreateMockAnything()

        fake_db.servers.find({'hostname': 'testing-master'}).AndReturn(
                [fake_row1])
        fake_db.servers.find({'hostname': 'testing-master'}).AndReturn(
                [])

        self.mox.ReplayAll()

        self.assertEqual(expected_output1,
                aerostat.get_master(fake_db, 'testing'))
        self.assertEqual(expected_output2,
                aerostat.get_master(fake_db, 'testing'))


    def test_check_master(self):
        """Test check_master funciton."""

        expected_output1 = True
        expected_output2 = False
        fake_service = 'testing'

        fake_instance_id1 = 'test-master-instance'
        fake_instance_id2 = 'test-slave-instance'

        fake_db = self.mox.CreateMockAnything()

        self.mox.StubOutWithMock(aerostat, 'get_master')
        aerostat.get_master(
                fake_db, fake_service).AndReturn(
                        'test-master-instance')
        aerostat.get_master(
                fake_db, fake_service).AndReturn(
                        'test-master-instance')

        self.mox.ReplayAll()

        self.assertEqual(expected_output1, aerostat.check_master(
                fake_db, fake_service, fake_instance_id1))
        self.assertEqual(expected_output2, aerostat.check_master(
                fake_db, fake_service, fake_instance_id2))


if __name__ == '__main__':
    unittest.main()
