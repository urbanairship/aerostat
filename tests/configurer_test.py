#!/usr/bin/env python

"""
Configurer Unittests.
"""
import os
import shutil
import socket
import StringIO
import subprocess
import sys
import tempfile
import unittest

import mox

from aerostat import configurer


class ConfiguratorTest(mox.MoxTestBase):
    """Test Class for Aerostat's Configurator Class."""

    def test_get_service_name(self):
        """test get_service_name function."""

        self.mox.StubOutWithMock(socket, 'gethostname')
        socket.gethostname().AndReturn('test-0')

        self.mox.ReplayAll()

        conf = configurer.Configurer()
        self.assertEqual('test', conf.get_service_name())

    def test_get_configs(self):
        """Test get_configs function."""

        fake_db = self.mox.CreateMockAnything()
        fake_col = self.mox.CreateMockAnything()
        fake_db.test = fake_col  # Needs to match fake_service.
        fake_service = 'test'
        fake_configs = ['test.conf']
        fake_mongo_data = [{
                'name': 'test.conf',
                'owner': 'tester',
                'group': 'test',
                'mode': '0444',
                'contents': 'Fun!'}]

        fake_col.find().AndReturn(fake_mongo_data)
        # This should only run the first 2/3 times.
        fake_col.find({'name': 'test.conf'}).AndReturn(fake_mongo_data)
        fake_col.find({'name': 'test.conf'}).AndReturn(fake_mongo_data)

        conf = configurer.Configurer()
        self.mox.StubOutWithMock(conf, 'get_service_name')
        # This should only run the first 2/3 times.
        conf.get_service_name().AndReturn(fake_service)
        conf.get_service_name().AndReturn(fake_service)

        self.mox.ReplayAll()

        expected_result = fake_mongo_data
        # Defaults
        self.assertEqual(expected_result, conf.get_configs(fake_db))
        # Config supplied
        self.assertEqual(expected_result, conf.get_configs(fake_db,
            configs=fake_configs))
        # Config and Service supplied.
        self.assertEqual(expected_result, conf.get_configs(fake_db,
            service='test', configs=fake_configs))

    def test_create_dir_path(self):
        """Test _create_dir_path."""

        fake_path = '/etc/path/to/config.conf'
        fake_base_path = '/etc/path/to'
        mkdir_cmd = ['mkdir', '-p', '-m', '761', fake_base_path]

        self.mox.StubOutWithMock(os.path, 'exists')
        os.path.exists(fake_base_path).AndReturn(False)
        os.path.exists(fake_base_path).AndReturn(True)

        self.mox.StubOutWithMock(subprocess, 'call')
        subprocess.call(mkdir_cmd).AndReturn(0)

        self.mox.ReplayAll()

        conf = configurer.Configurer()
        self.assertTrue(conf._create_dir_path(fake_path))  # No path exists
        self.assertTrue(conf._create_dir_path(fake_path))  # Path does exist.

    def test_update_conf_perms(self):
        """Test _update_conf_perms function."""

        fake_file_name = 'test.conf'
        fake_file_path = '/etc/fake/test.conf'
        fake_owner = 'me'
        fake_group = 'ua'
        fake_mode = '600'
        fake_chmod_cmd = ['chmod', fake_mode, fake_file_path]
        fake_chown_cmd = [
                'chown', '%s:%s' % (fake_owner, fake_group), fake_file_path]

        self.mox.StubOutWithMock(subprocess, 'call')
        subprocess.call(fake_chmod_cmd).AndReturn(0)
        subprocess.call(fake_chown_cmd).AndReturn(0)

        self.mox.ReplayAll()

        conf = configurer.Configurer()
        self.assertTrue(conf._update_conf_perms(
            fake_file_name, fake_file_path, fake_owner, fake_group, fake_mode))

    def test_write_configs(self):
        """Test write_configs function."""

        #TODO(gavin): exhaustively test when file doesn't exist, etc.
        fake_config_data = [{
            'name': 'test.conf',
            'path': '/path/to/test.conf',
            'owner': 'tester',
            'group': 'test',
            'mode': '0600',
            'contents': 'Yay unittests!'}]

        fake_temp_name = '/tmp/something'
        fake_temp_file = StringIO.StringIO()
        self.mox.StubOutWithMock(tempfile, 'mkstemp')
        tempfile.mkstemp(text=True).AndReturn((4, fake_temp_name))
        fake_path = '/path/to/test.conf'

        self.mox.StubOutWithMock(sys.modules['__builtin__'], 'open')
        sys.modules['__builtin__'].open(fake_temp_name, 'w').AndReturn(
                fake_temp_file)

        self.mox.StubOutWithMock(shutil, 'move')
        shutil.move(fake_temp_name, fake_path).AndReturn(None)

        conf = configurer.Configurer()

        self.mox.StubOutWithMock(conf, '_create_dir_path')
        conf._create_dir_path(fake_config_data[0]['path']).AndReturn(True)
        fake_return_codes = [('test.conf', 0, 0)]
        self.mox.StubOutWithMock(conf, '_update_conf_perms')
        conf._update_conf_perms(
                fake_config_data[0]['name'],
                fake_config_data[0]['path'],
                fake_config_data[0]['owner'],
                fake_config_data[0]['group'],
                fake_config_data[0]['mode']).AndReturn(fake_return_codes)

        self.mox.ReplayAll()

        self.assertTrue(conf.write_configs(fake_config_data))

    def test_do_update(self):
        """Test do_update function."""

        fake_db = self.mox.CreateMockAnything()
        fake_mongo_data = [{
                'name': 'test.conf',
                'owner': 'tester',
                'group': 'test',
                'mode': '0444',
                'contents': 'Fun!'}]

        conf = configurer.Configurer()
        self.mox.StubOutWithMock(conf, 'get_configs')
        conf.get_configs(fake_db, service=None, configs=None).AndReturn(
                fake_mongo_data)
        self.mox.StubOutWithMock(conf, 'write_configs')
        conf.write_configs(fake_mongo_data).AndReturn(True)

        self.mox.ReplayAll()

        self.assertTrue(conf.do_update(fake_db))


if __name__ == '__main__':
    unittest.main()
