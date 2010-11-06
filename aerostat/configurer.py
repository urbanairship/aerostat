#!/usr/bin/env python

"""
Configurer - Update configuration files based on contents and metadata stored
on the aerostat server.
"""

import os
import shutil
import socket
import subprocess
import tempfile

from aerostat import logging
from jinja2 import Template

class Configurer(object):
    """Get and write config files."""

    def __init__(self):
        self._hostname = None
        self._service_name = None

    def get_hostname(self):
        """get hostname"""
        if self._hostname is None:
            self._hostname = socket.gethostname()
        return self._hostname

    def get_service_name(self):
        """get service name."""
        if self._service_name is None:
            self._service_name = self.get_hostname().split('-')[0]
        return self._service_name

    def get_configs(self, db, service=None, configs=None):
        """Get all configs for this node, or optionally just ones specified.

        Args:
            db: a pymongo.Connection.Database obj.
            service: str, optional name of service whose configs you want.
            configs: list or str, optional list of config filenames.
        Returns:
            a list of dicts, keyed on filename, includes path, mode, owner,
            contents of a config file.
        """
        if not service:
            service = self.get_service_name()

        col = getattr(db, service, None)
        config_data = [] # Content plus meta data.
        if not configs:
            config_data = list(col.find())
        else:
            for config in configs:
                config_data.extend(list(col.find({'name': config})))

        return config_data

    def _create_dir_path(self, path):
        """Create the directory path for the configs, if necssary.

        Args:
            path: str, path of config.
        Returns:
            bool, True if exit code for mkdir is 0, or if
            directory already exists.
        """
        base_path = '/'.join(path.split('/')[:-1])
        if not os.path.exists(base_path):
            mkdir_cmd = ['mkdir', '-p', '-m', '755', base_path]
            mkdir_ret = subprocess.call(mkdir_cmd)
            if mkdir_ret == 0:
                logging.info('Mkdir (%s) successful' % path)
            else:
                logging.error('Mkdir (%s) unsuccessful' % path)

            return mkdir_ret == 0

        return True

    def _update_conf_perms(self, file_name, file_path, owner, group, mode):
        """Chown and Chmod as appropriate.

        Args:
            file_name: str, name of file.
            file_path: str, full path of file.
            owner: str, system user to own file.
            group: str, group to own file.
            mode: str, octal mode for a POSIX file.
        Returns:
            Tuple of (file_name, return of chmod, return of chown)
        """
        chmod_cmd = ['chmod', str(mode), file_path]
        chmod_ret_code = subprocess.call(chmod_cmd)
        chown_cmd = [
                'chown', '%s:%s' % (owner, group), file_path]
        chown_ret_code = subprocess.call(chown_cmd)

        return (file_name, chmod_ret_code, chown_ret_code)

    def write_configs(self, config_data):
        """Write configs to appropriate paths with appropriate permisions.

        Args:
            config_data: list of dicts of configuration data for server.
        Returns:
            list, containing tuples of return codes for each file's perm ops.
        """
        print config_data
        return_codes = []
        for config in config_data:
            if not self._create_dir_path(config['path']):
                logging.error(
                    'Could not create directory tree for %s' % config['path'])
                continue

            if 'contents' in config.keys(): # Possibly an empty config
                temp_fd, temp_file = tempfile.mkstemp(text=True)
                print temp_fd, temp_file

                # If we have Jinja templ values to insert into the config
                if 'keywords' in config.keys():
                    logging.debug('replacing keywords in config template')
                    config['contents'] = self.render_template(
                            config['contents'], config['keywords'])

                temp = open(temp_file, 'w')
                temp.write(config['contents'])
                temp.close()

                try:
                    shutil.move(temp_file, config['path'])
                except shutil.Error, e:
                    logging.warn(
                            'Invalid Path Specified: %s. Traceback:\n %s' % (
                                config['path'], e))
                    continue

            file_ret_codes = self._update_conf_perms(
                    config['name'], config['path'], config['owner'],
                    config['group'], config['mode'])

            return_codes.append(file_ret_codes)

        return return_codes

    def render_template(self, config_contents, template_data):
        """Setup Customizations for configs that need it.

        Args:
            config_contents: str, the raw Jinja template/config file.
            template_data: dict, key->value structure to pass to Jinja.
        Returns:
            str, customized config_contents, ready to be written to file.
        """
        config_contents['service_name'] = self.get_service_name()
        config_contents['hostname'] = self.get_hostname()
        template = Template(config_contents)

        return template.render(template_data)

    def do_update(self, db, service=None, config_names=None):
        """Get relevant configs from mongo, update the client.

        Args:
            db: pymongo.Connection.Database obj.
            service: str, name of service to request data for.
            configs_names: list of str, specific names of files to load.
        Returns:
            bool, True on success with no problems.
        Outcome:
            Many server configuration files could be overwritten here.
        """
        configs = self.get_configs(db, service=service, configs=config_names)

        return self.write_configs(configs)
