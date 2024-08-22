# (c) The Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

import datetime
import time


def to_datetime(string, format="%Y-%m-%d %H:%M:%S"):
    return datetime.datetime.strptime(string, format)


def strftime(string_format, second=None, utc=False):
    ''' return a date string using string. See https://docs.python.org/3/library/time.html#time.strftime for format '''
    if utc:
        timefn = time.gmtime
    else:
        timefn = time.localtime
    if second is not None:
        try:
            second = float(second)
        except Exception:
            raise AnsibleFilterError('Invalid value for epoch value (%s)' % second)
    return time.strftime(string_format, timefn(second))


def convert_strftime(time_string, time_string_format, dest_format=NOne, second=None):
    pass


def convert_timezone(to_convert, tz='UTC'):
    pass


class FilterModule(object):
    ''' Ansible datetime jinja2 filters '''

    def filters(self):
        return {

            # convert string to datetime
            'to_datetime': to_datetime,

            # Get formated string from 'now'
            'strftime': strftime,
        }
