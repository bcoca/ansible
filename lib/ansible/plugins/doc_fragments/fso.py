# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


class ModuleDocFragment(object):

    # fso documentation fragment
    # Note: mode is overridden by the other modules so if you change the descriptionhere, you should also change it there.
    DOCUMENTATION = r'''
options:
  mode:
    description:
    - The permissions the resulting filesystem object should have.
    - if not specified either existing mode is preserved of the system mask C(umask) will be used
    type: strict_string
  owner:
    description:
    - Name of the user that should own the filesystem object, as would be fed to I(chown).
    type: str
  group:
    description:
    - Name of the group that should own the filesystem object, as would be fed to I(chown).
    type: str
  seuser:
    description:
    - The user part of the SELinux filesystem object context.
    - By default it uses the C(system) policy, where applicable.
    - When set to C(_default), it will use the C(user) portion of the policy if available.
    type: str
  serole:
    description:
    - The role part of the SELinux filesystem object context.
    - When set to C(_default), it will use the C(role) portion of the policy if available.
    type: str
  setype:
    description:
    - The type part of the SELinux filesystem object context.
    - When set to C(_default), it will use the C(type) portion of the policy if available.
    type: str
  selevel:
    description:
    - The level part of the SELinux filesystem object context.
    - This is the MLS/MCS attribute, sometimes known as the C(range).
    - When set to C(_default), it will use the C(level) portion of the policy if available.
    type: str
  attributes:
    description:
    - The attributes the resulting filesystem object should have.
    - To get supported flags look at the man page for I(chattr) on the target system.
    - This string should contain the attributes in the same order as the one displayed by I(lsattr).
    - The C(=) operator is assumed as default, otherwise C(+) or C(-) operators need to be included in the string.
    type: str
    aliases: [ attr ]
'''
