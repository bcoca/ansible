# Copyright (c) 2021 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.module_utils.compat.paramiko import paramiko
from ansible.plugins.connection import ConnectionBase
from ansible.plugins.connection.ssh import Connection as ssh
from ansible.plugins.connection.paramiko_ssh import Connection as paramiko_ssh
from ansible.utils.display import Display
from ansible.utils.ssh_functions import check_for_controlpersist


display = Display()


DOCUMENTATION = '''
    connection: smart
    short_description: decides which ssh plugin to use
    description:
        - This connection plugin is a fake, it either returns ssh or paramiko depending on the suitablity detected.
    author: ansible (@core)
    version_added: '2.10'
    options:
      host:
          description: Hostname/ip to connect to.
          default: inventory_hostname
          vars:
               - name: ansible_host
'''

# see if SSH can support ControlPersist if not use paramiko if present
if not check_for_controlpersist('ssh') and paramiko is not None:
    display.debug('ssh does not have controlpersist, chose paramiko instead')
    Connection = paramiko_ssh
else:
    Connection = ssh
