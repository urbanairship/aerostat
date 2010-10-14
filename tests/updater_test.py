#!/usr/bin/env python

"""
Unittests for Aerostat Updater.
"""

import os
import StringIO
import sys
import unittest

import mox
import shutil

from aerostat import updater


class UpdaterTest(mox.MoxTestBase):
    """Test the Updater class."""

    def test_append_hosts_line(self):
        """Test append_hosts_line function."""

        expected_output = ['127.0.0.1 localhost', 'fake_ip fake_host']
        fake_updater = updater.Updater()

        self.mox.ReplayAll()

        fake_updater.append_hosts_line('fake_ip', 'fake_host')
        self.assertEqual(fake_updater.hosts_data, expected_output)

    def test_format_aliases(self):
        """Test format_aliases function."""

        fake_aliases = ['alias1', 'alias2', 'alias3']
        fake_ip = 'test_ip'

        expected_output = [
                '127.0.0.1 localhost', 'test_ip alias1', 'test_ip alias2',
                'test_ip alias3']

        expected_bad_alias_output = ['127.0.0.1 localhost']

        fake_updater = updater.Updater()
        fake_updater_bad_alias = updater.Updater()

        self.mox.ReplayAll()

        fake_updater.format_aliases(fake_ip, fake_aliases)
        self.assertEqual(fake_updater.hosts_data, expected_output)
        self.assertEqual(fake_updater_bad_alias.hosts_data, expected_bad_alias_output)

    def test_delete_aero_sect(self):
        """Test delete_aero_sect."""

        expected_output = ['127.0.0.1 localhost']
        fake_updater = updater.Updater()
        fake_hosts_content = ['127.0.0.1 localhost\n',
                              '# AEROSTAT\n',
                              'test_ip test_host\n',
                              '# /AEROSTAT\n']

        self.mox.ReplayAll()

        self.assertEqual(fake_updater.delete_aero_sect(fake_hosts_content),
                expected_output)

    def test_write_hosts_file_fresh(self):
        """Test write hosts file on a fresh host."""

        expected_output = '# AEROSTAT\ntest_ip test_host\n# /AEROSTAT\n'
        fake_updater = updater.Updater()
        fake_updater.hosts_data = ['test_ip test_host']
        fake_hosts_file1 = StringIO.StringIO('')
        fake_hosts_file2 = StringIO.StringIO('')

        self.mox.StubOutWithMock(os, 'rename')
        os.rename('/etc/hosts.tmp', '/etc/hosts').AndReturn(None)

        self.mox.StubOutWithMock(fake_hosts_file2, 'close')
        fake_hosts_file2.close().AndReturn(None)

        self.mox.StubOutWithMock(sys.modules['__builtin__'], 'open')
        sys.modules['__builtin__'].open('/etc/hosts.legacy', 'r').AndReturn(
                fake_hosts_file1)

        sys.modules['__builtin__'].open('/etc/hosts.tmp', 'w').AndReturn(
                fake_hosts_file2)

        self.mox.StubOutWithMock(fake_updater, 'delete_aero_sect')
        fake_updater.delete_aero_sect([]).AndReturn([])

        self.mox.ReplayAll()

        fake_updater.write_hosts_file()
        self.assertEqual(fake_hosts_file2.getvalue(), expected_output)

    def test_write_hosts_file_old(self):
        """Test write hosts file on an old host."""

        expected_output = ('127.0.0.1 localhost\n# AEROSTAT\n'
        'test_ip test_host\n# /AEROSTAT\n')

        fake_updater = updater.Updater()
        fake_updater.hosts_data = ['test_ip test_host']
        fake_hosts_file1 = StringIO.StringIO(expected_output)  # begin as we end.
        fake_hosts_file2 = StringIO.StringIO(expected_output)  # begin as we end.

        self.mox.StubOutWithMock(os, 'rename')
        os.rename('/etc/hosts.tmp', '/etc/hosts').AndReturn(None)

        self.mox.StubOutWithMock(sys.modules['__builtin__'], 'open')
        sys.modules['__builtin__'].open('/etc/hosts.legacy', 'r').AndReturn(
                fake_hosts_file1)

        sys.modules['__builtin__'].open('/etc/hosts.tmp', 'w').AndReturn(
                fake_hosts_file2)

        self.mox.StubOutWithMock(fake_hosts_file2, 'close')
        fake_hosts_file2.close().AndReturn(0)

        test_readlines = ['127.0.0.1 localhost\n',
                          '# AEROSTAT\n',
                          'test_ip test_host\n',
                          '# /AEROSTAT\n']
        test_preceding = ['127.0.0.1 localhost']  # This is outside of Aerostat

        self.mox.StubOutWithMock(fake_updater, 'delete_aero_sect')
        fake_updater.delete_aero_sect(test_readlines).AndReturn(test_preceding)

        self.mox.ReplayAll()

        fake_updater.write_hosts_file()
        self.assertEqual(fake_hosts_file2.getvalue(), expected_output)

    def test_do_update(self):
        """Test do_update function."""

        expected_output = [
            '127.0.0.1 localhost',
            '12.123.234.5 mongodb-slave-1',
            '12.123.234.5 mongo-primary-slave',
            '12.123.234.5 first-prime']

        fake_db = self.mox.CreateMockAnything()
        fake_db.servers = self.mox.CreateMockAnything()

        fake_data = [{
                'hostname': 'mongodb-slave-1',
                'ip': '12.123.234.5',
                'service': 'mongodb',
                'service_type': 'masterful',
                'instance_id': 'i-23426',
                'aliases': ['mongo-primary-slave', 'first-prime']}]

        fake_db.servers.find().AndReturn(fake_data)

        self.mox.StubOutWithMock(os, 'rename')
        self.mox.StubOutWithMock(shutil, 'copyfile')
        shutil.copyfile('/etc/hosts', '/etc/hosts.bak').AndReturn(0)

        fake_updater = updater.Updater()

        self.mox.StubOutWithMock(fake_updater, 'write_hosts_file')
        fake_updater.write_hosts_file().AndReturn(None)

        self.mox.ReplayAll()

        fake_updater.do_update(fake_db, False)
        self.assertEqual(fake_updater.hosts_data, expected_output)


if __name__ == '__main__':
    unittest.main()
