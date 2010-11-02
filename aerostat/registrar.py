#!/usr/bin/env python

"""
Registrar - Handle registration tasks of new hosts, or host name changes within
aerostat.
"""

import os
import operator

import aerostat

from aerostat import logging


class Registrar(object):
    """Pick a hostname algorithmically and register it with the database."""

    def get_types(self):
        """Returns server_type and service_type.

        /etc/aerostat_info is a file that's created by the user_data script,
        which is executed the first time Ubuntu servers are booted up in EC2.

        The file format looks something like:
        <service_name> <service_type> <alias1> <alias2> <aliasN>

        Only service_name field is required.
        User_data is set in the installer config.
        """
        aerostat_info_file = os.environ.get('AEROSTAT_INFO','/etc/aerostat_info')
        logging.debug('get_types(): opening type info from %s.' % aerostat_info_file)
        server_info = open(aerostat_info_file, 'r')
        logging.debug('get_types(): reading type info from %s.' % aerostat_info_file)
        types = server_info.read().strip().split()
        logging.debug('recovered type info from %s.' % aerostat_info_file)
        server_info.close()

        return types

    def check_dup(self, db, instance_id):
        """Check that there aren't duplicate name enties.

        Args:
            db: pymongo DB instnace.
            instance_id: str, name of instance to check.
        Returns:
            bool, whether or not there are duplicates.
        """
        if db.servers.find({'instance_id': instance_id}).count() > 0:
            logging.warning('Duplicate instance found: %s' % instance_id)
            return True
        return False

    def get_smallest_gap(self, db, service):
        """Check if there's a gap in the hostname numbers."""
        gaps = list(db.servers.find({'instance_id': '', 'service': service}))
        if len(gaps) > 0:
            # There is a gap
            logging.info('Gap in hostnames detected.')
            gaps.sort(key=operator.itemgetter('hostname'))

            return gaps[0]['hostname']

    def hostname_instance_exists(self, db, hostname):
        """Check to see if a given hostname has an instance attached."""

        result = db.servers.find_one({'hostname': hostname})
        # Should only ever have one instance_id in aerostat.
        if result and result['instance_id']:
            logging.info('Hostname/instance pair exists for %s' % hostname)
            return True
        else:
            logging.info('Hostname/inst pair does\'t exist for %s' % hostname)
            return False

    def alias_exists(self, db, aliases):
        """Check if alias exists for any host, regardless of number.

        Args:
            db: pymongo.Connection.db instnace.
            aliases: a list of str, all of the aliases for a row.
        Returns:
            If matches are found, it returns the aliases for those rows.
        """
        results = list(db.servers.find({'aliases' : { '$in' : aliases}}))
        if len(results) > 0:
            logging.info('Detected at least one alias.')
            ret_val = []
            [ret_val.extend(result['aliases']) for result in results]
            return ret_val

    def pick_name(self, db, service, service_type, instance_id):
        """Check against the names in the aerostat database.

        This is the basic logic behind deciding which names are available.
        It checks the aerostat database, and using a combination of the
        service_type and the instance_id, it determines if there are:
            1) duplicate entries - in which case, it overwrites the older entry.
            2) depending on type, it will determine the next logical name in the
            services progression.
            3) this function then returns that string value.

        Args:
            db: a pymongo.Connection.db instance.
            service: str, the name retrieved from /etc/aerostat_info.
            service_type: str, kind of service hierarchy, masterful or iterative.
            instance_id: str, name of instance, to check for dups.
        Returns:
            str, the appropriate hostname for the client node.
        """
        hostname = None
        # Check for duplicates. But only if instances have names.
        if self.check_dup(db, instance_id) and aerostat.get_hostname(
                db, instance_id):
            logging.warn('Duplicate instance found')
            return None

        results = list(db.servers.find({'service': service}))
        # We only want to count instances in our service with hostnames.
        named_in_service = [item for item in results if item['hostname']]
        num = len(named_in_service)
        logging.info('%s number of hosts with same service found' % num)

        if service_type == 'masterful':
            master_hostname = '%s-master' % (service,)
            if not named_in_service:
                hostname = master_hostname  # first instance will be master.
            elif aerostat.hostname_exists(db,
                        master_hostname) and not self.hostname_instance_exists(
                                db, master_hostname):
                hostname = master_hostname  # replace fallen master.
            else:
                smallest_slave_gap = self.get_smallest_gap(db, service)
                if smallest_slave_gap:
                    hostname = smallest_slave_gap
                else:
                    hostname = '%s-slave-%s' % (service, num)
        else:  # We're iterative.
            smallest_gap = self.get_smallest_gap(db, service)
            # find out if there are gaps in the hostnames, use smallest.
            if smallest_gap:
                hostname = smallest_gap
            else:
                hostname =  '%s-%s' % (service, num) # New instance, no gaps.

        return hostname

    def reset_conflict_aliases(self, db, conflicts):
        """Remove individual aliases used by old hostnames.

        Args:
            db: pymongo.Connection.db instance.
            conflicts: list of str, aliases which already exist.

        Essentially, we remove all individual instances of an alias among
        all conflicting sets of aliases for our servers.
        """
        for result in db.servers.find({'aliases' : { '$in': conflicts}}):
            new_aliases = list(set(result['aliases']) - set(conflicts))
            db.servers.update({'instance_id': result['instance_id']},
                    {'$set': {'aliases': new_aliases}})

        return True

    def register_name(
            self, db, hostname, local_ip, instance_id, service,
            service_type, aliases):
        """Insert Hostname -> IP relationship into Aerostat DB.

        Args:
            db: a pymongo.Connection.db instnace.
            hostname: str, name of client host.
            local_ip: str, ip address of client host.
            instance_id: str, name of EC2 instance.
            service: str, name of service.
            service_type: str, name of server category.
            aliases: list of str, alternate names.
        Returns:
            True if registration succeeded.
        """
        if aliases:
            aliases = list(set(aliases))  # remove any duplicates.
            conflicting_aliases = self.alias_exists(db, aliases)
            if conflicting_aliases:
                # Update Aliases in all hosts to not have said alias anymore.
                self.reset_conflict_aliases(db, conflicting_aliases)

        if aerostat.hostname_exists(db, hostname):
            # hostname already exists, fill in the gap.
            db.servers.update(
                    {'hostname': hostname},
                    {'$set': {
                        'ip': local_ip,
                        'service': service,
                        'service_type': service_type,
                        'instance_id': instance_id,
                        'aliases': aliases}})
        else:
            # This is a new host being added to the service cluster.
            db.servers.insert(
                    {'hostname': hostname,
                     'ip': local_ip,
                     'service': service,
                     'service_type': service_type,
                     'instance_id': instance_id,
                     'aliases': aliases})

        #If registration succeeded
        return True

    def set_sys_hostname(self, hostname):
        """Change system hostname permanently.

        Args:
            hostname: str, new hostname for host.

        Returns:
            bool, whether or not hostname was successfully updated.

        Note: this should be run with root permissions.
        """
        status = os.system('/bin/hostname %s' % (hostname,))
        if status is 0:
            os.remove('/etc/hostname')
            f = open('/etc/hostname', 'w')
            f.write(hostname)
            f.close()

            return True
        else:
            return False

    def parse_service_info(self):
        """Sort out what is service and service-type from config."""

        service = None
        service_type = None
        aliases = None
        name_type_info = self.get_types()

        if len(name_type_info) > 2:
            service, service_type = name_type_info[:2]
            aliases = name_type_info[2:]
        elif len(name_type_info) > 1:
            service, service_type = name_type_info
        else:
            service = name_type_info.pop()
            service_type = 'iterative'

        return (service, service_type, aliases)

    def change_hostname(self, db, value, inst=None, host=None):
        """Change the hostname of the specified instance or hostname."""

        if not inst and not host:
            logging.error('You need to specify either instance or hostname')
            return False

        if inst and host:
            logging.error('You cannot specify both inst and hostname')
            return False

        key = 'instance_id'
        if host:
            key = 'hostname'

        param = inst or host
        db.servers.update(
                { key: param},
                {'$set':
                    {'hostname': value}})

        return True

    def change_master(self, db, service, service_type, cur_host_inst):
        """Change cur_host to cur_master's hostname in aerostat.

        Args:
            db: mongodb db reference.
            service: str, name of service.
            service_type: str, type of service (masterful, or iterative).
            cur_host_inst: str, current hosts's instance id.
        Returns:
            bool, True if successful.
        """
        # If we're not masterful, or current host is already master: pass.
        if service_type != 'masterful' or aerostat.check_master(
                db, service, cur_host_inst):

            return False

        cur_master_inst = aerostat.get_master(db, service)
        master_hostname = '%s-master' % (service,)
        if cur_master_inst:
            # There is a master instance alive; null out its hostname.
            self.change_hostname(db, '' , inst=cur_master_inst)

        self.change_hostname(db, '', inst=cur_host_inst)
        self.change_hostname(db, master_hostname, inst=cur_host_inst)
        if cur_master_inst:
            # Find a place to put the old master.
            new_master = self.pick_name(db, service,
                    service_type, cur_master_inst)
            self.change_hostname(db, new_master, inst=cur_master_inst)

        return True

    def do_registrar(self, db, dry_run, change_master, offline):
        """Setup hostname for a newly bootstraped server.

        Args:
            db: mongodb database reference.
            dry_run: bool, should we actually apply changes.
            change_master: bool, should we swap masters.
            offline: bool, should we connect to aws.
        Returns:
            bool, True if system settings are correctly changed.
        """

        service, service_type, aliases = self.parse_service_info()
        instance_id, local_ip = aerostat.get_aws_data(offline)
        if change_master:
            self.change_master(
                    db, service, service_type, instance_id)

            return True

        hostname = self.pick_name(db, service, service_type, instance_id)
        change_host = False
        # If we successfully aquired a hostname (not dup) from mongodb
        if dry_run:
            logging.debug('DRY RUN: you would register with: %s' % hostname)

            return False

        if hostname:
            change_host = self.set_sys_hostname(hostname)
        if change_host:
            self.register_name(
                    db, hostname, local_ip, instance_id, service,
                    service_type, aliases)

        return True
