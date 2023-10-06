from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.errors import AnsibleActionFail
from ansible.module_utils.six import string_types
from ansible.module_utils._text import to_text
from ansible.plugins.action import ActionBase
from ansible.utils.display import Display

display = Display()


class ActionModule(ActionBase):
    ''' Print statements during execution '''

    TRANSFERS_FILES = False
    _VALID_ARGS = frozenset(('msg', 'channel', 'color'))
    _VALID_CHANNELS = frozenset(('deprecated', 'warning', 'display', 'verbose', 'error', 'callback'))

    def run(self, tmp=None, task_vars=None):

        try:
            try:
                msg = self._task.args['msg']
            except KeyError:
                raise AnsibleActionFail("The required field 'msg' is missing")

            channel = self._task.args.get('channel', 'callback')

            if channel not in self._VALID_CHANNELS:
                raise AnsibleActionFail("Invalid channel '%s', valid values are: %s " % (channel, ', '.join(self._VALID_CHANNELS)))

            result = super(ActionModule, self).run(tmp, task_vars)

            if channel != 'callback':
                call = getattr(display, channel)
                call(to_text(msg, errors='surrogate_or_strict'))
            else:
                result['msg'] = msg

            #result['_ansible_verbose_override'] = True
            result['_ansible_always_verbose'] = True
            result['_ansible_display_fields'] = ['mg']
            result['failed'] = False
        except TypeError:
            raise AnsibleActionFail("The required field 'msg' is missing")

        return result
