# (c) The Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

from jinja2.filters import pass_environment

from ansible.errors import AnsibleFilterTypeError
from ansible.inventory.group import to_safe_group_name
from ansible.module_utils.common.text.converters import to_native
from ansible.utils.display import Display

display = Display()


@pass_environment
def sanitize_group_name(environment, name, replacer="_", force=False, silent=False):
    try:
        return to_safe_group_name(name, replacer=replacer, force=force, silent=silent)
    except TypeError as e:
        raise AnsibleFilterTypeError(to_native(e), orig_exc=e)


class FilterModule(object):
    ''' Ansible sanitization jinja2 filters '''

    def filters(self):
        return {
            # Group names
            'sanitize_group_name': sanitize_group_name,
        }
