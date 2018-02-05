# Copyright (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
    name: puppet 
    plugin_type: inventory
    short_description: PuppetDB inventory source
    description:
        - Get inventory hosts from a PuppetDB.
        - Uses a <name>.pdb.yaml (or .pdb.yml) YAML configuration file.
        - The inventory_hostname is always the 'node'.
    extends_documentation_fragment:
      - constructed
      - inventory_cache
    options:
        host:
            description: puppetdb host name
            default: localhost
        port:
            description: puppetdb host name
            type: integer
            : True
        timeout:
        verify_ssl:
            description: Do strict ssl verification
            aliases: ['ssl_verify']
            default: True
            type: boolean
        ssl_key:
            description: SSL key
            type: path
        ssl_cert:
            description: SSL Certificate
            type: path
'''

EXAMPLES = '''
# file must be named .pdb.yml or pdb.yml
'''

import os

from collections import MutableMapping
from subprocess import Popen, PIPE

from ansible.errors import AnsibleParserError
from ansible.module_utils._text import to_bytes, to_native, to_text
from ansible.plugins.inventory import BaseInventoryPlugin, Constructable, Cacheable


try:
    from pypuppetdb import connect
    HAS_PUPPETDB = True
except ImportError:
    HAS_PUPPETDB = False


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    ''' Host inventory parser for ansible using local virtualbox. '''

    NAME = 'puppet'

    def verify_file(self, path):

        valid = False
        if super(InventoryModule, self).verify_file(path):
            if path.endswith(('.pdb.yaml', '.pdb.yml')):
                valid = True
        return valid

    def parse(self, inventory, loader, path, cache=True):

        super(InventoryModule, self).parse(inventory, loader, path)

        if not HAS_PUPPETDB:
            raise AnsibleError("The puppetdb python library is required for the puppet inventory plugin.")

        cache_key = self.get_cache_key(path)

        config_data = self._read_config_data(path)

        # set _options from config data
        self._consume_options(config_data)

        source_data = None
        if cache:
            cache = self._options.get('cache')

        update_cache = False
        if cache:
            try:
                source_data = self.cache.get(cache_key)
            except KeyError:
                update_cache = True

#  FIXME
        if not source_data:
            b_pwfile = to_bytes(self.get_option('settings_password_file'), errors='surrogate_or_strict')
            running = self.get_option('running_only')

            # start getting data
            cmd = [self.VBOX, b'list', b'-l']
            if running:
                cmd.append(b'runningvms')
            else:
                cmd.append(b'vms')

            if b_pwfile and os.path.exists(b_pwfile):
                cmd.append(b'--settingspwfile')
                cmd.append(b_pwfile)

            try:
                p = Popen(cmd, stdout=PIPE)
            except Exception as e:
                AnsibleParserError(to_native(e))

            source_data = p.stdout.read().splitlines()

        using_current_cache = cache and not update_cache
        cacheable_results = self._populate_from_source(source_data, using_current_cache)

        if update_cache:
            self.cache.set(cache_key, cacheable_results)
