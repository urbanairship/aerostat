#!/usr/bin/env python

"""
Aerostat Updater.
"""
import os

import shutil
import subprocess
import sys

from aerostat import logging


class Updater(object):
    """Update the /etc/hosts file on the localhost."""

    def __init__(self):
        """Initialize object."""

        self.hosts_data = ['127.0.0.1 localhost']

    def append_hosts_line(self, ip, hostname):
        """Format string appropriate for /etc/hosts file.

        Args:
            ip: str, ip address which mapping is made against.
            hostname: str, hostname to map against ip.
        Modifies:
            self.hosts_data, appends more hostname -> ip mappings. One mapping
            per list item, which translates into one line in the file.
        """
        logging.debug('Parsing mapping for host %s and ip %s' % (
                hostname, ip))
        self.hosts_data.append('%s %s' % (ip, hostname))

    def format_aliases(self, ip, aliases):
        """Format all of the alias lines as if they were also hosts.

        Args:
            ip: str, ip to do mapping against.
            aliases: list of str, hostnames to map ip to in additon to
            algorithmic hostname.
        Modifies:
            self.hosts_data, appends more hostname -> ip mappings. One mapping
            per list item, which translates into one line in the file.
        """
        for alias in aliases:
            if ip:
                self.append_hosts_line(ip, alias)

    def delete_aero_sect(self, hosts_content):
        """Remove aerostat section and return remaining lines.

        Args:
            hosts_content: list of str, /etc/hosts values as read from file.
        Returns:
            list of str, only those lines that do not belong to Aerostat.
        """
        preceding = []
        for line in hosts_content:
            if line.strip() == '# AEROSTAT':
                logging.info('Scanned to Aerostat Section. Removing.')
                break
            else:
                preceding.append(line.strip())

        return preceding

    def write_hosts_file(self):
        """Write out the new /etc/hosts file."""

        try:
            hosts_file_read = open('/etc/hosts.legacy', 'r')
            hosts_content = hosts_file_read.readlines()
            # Keep non-Aerostat Data for new file write.
            hosts_file_read.close()
        except IOError:
            hosts_content = []

        preceding = self.delete_aero_sect(hosts_content)
        # Create new Aeorstat tag headers.
        aerostat_section = ['# AEROSTAT']
        aerostat_section.extend(self.hosts_data)
        self.hosts_data = aerostat_section
        self.hosts_data.append('# /AEROSTAT')

        hosts_file_write = open('/etc/hosts.tmp', 'w')
        # Remember to pre-pend old information.
        if preceding:
            preceding.extend(self.hosts_data)
            self.hosts_data = preceding

        # Actually write to the file.
        hosts_string = '\n'.join(self.hosts_data) + '\n'
        hosts_file_write.write(hosts_string)
        hosts_file_write.close()
        os.rename('/etc/hosts.tmp', '/etc/hosts')

    def do_update(self, db, dry_run=None, legacy_updater=None):
        """Update /etc/hosts.

        Args:
            db: mongdb db reference.
            dry_run: bool, whether or not to actually update /etc/hosts.
            legacy_updater: binary to run in order to update /etc/hosts
            (helpful for transitions).
        Returns:
            bool, True if changes are made to the system.
        """

        if legacy_updater:
            # Call legacy host updater, allow it to write to /etc/hosts.
            retcode = subprocess.call([legacy_updater])
            if retcode < 0:
                logging.error('Call to %s failed!' % legacy_updater)
                sys.exit(1)

        self.hosts_data = ['127.0.0.1 localhost']  # Reset data, otherwise we append
        aerostat_data = db.servers.find()

        # extract hostname, ip and aliases
        for item in aerostat_data:
            if item['ip']:
                self.append_hosts_line(item['ip'], item['hostname'])
            if item['aliases']:
                self.format_aliases(item['ip'], item['aliases'])

        if dry_run:
            dry_run_output = '\n'.join(self.hosts_data) + '\n'
            logging.debug(
                    ('DRY RUN: Your /etc/hosts file would look'
                    'like this: \n%s' % dry_run_output))
            return False

        # Only make any changes if there are actual data available to write.
        if self.hosts_data:
            logging.info('Copying /etc/hosts to /etc/hosts.bak')
            shutil.copyfile('/etc/hosts', '/etc/hosts.bak')
            logging.info('Writing new /etc/hosts file.')
            self.write_hosts_file()
        else:
            logging.error('No data returned from aerostat. Write aborted.')

        return True


