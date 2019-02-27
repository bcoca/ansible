# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


class ModuleDocFragment(object):

    # Standard files documentation fragment
    DOCUMENTATION = r'''
options:
  persistent_buffer_read_timeout:
    type: float
    description:
      - Configures, in seconds, the amount of time to wait for the data to be read
        from Paramiko channel after the command prompt is matched. This timeout
        value ensures that command prompt matched is correct and there is no more data
        left to be received from remote host.
    default: 0.1
    ini:
      - section: persistent_connection
        key: buffer_read_timeout
    env:
      - name: ANSIBLE_PERSISTENT_BUFFER_READ_TIMEOUT
    vars:
      - name: ansible_buffer_read_timeout
  persistent_log_messages:
    type: boolean
    description:
      - This flag will enable logging the command executed and response received from
        target device in the ansible log file. For this option to work 'log_path' ansible
        configuration option is required to be set to a file path with write access.
      - Be sure to fully understand the security implications of enabling this
        option as it could create a security vulnerability by logging sensitive information in log file.
    default: False
    ini:
      - section: persistent_connection
        key: log_messages
    env:
      - name: ANSIBLE_PERSISTENT_LOG_MESSAGES
    vars:
      - name: ansible_persistent_log_messages
'''
