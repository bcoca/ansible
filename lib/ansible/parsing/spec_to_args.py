# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

# Make coding more python3-ish
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import yaml

from ansible.errors import AnsibleError

def extract_spec_from_module(module_file):

    mymodule = __import__(module_file)
    docs = ''

    if hasattr(mymodule, 'DOCUMENTATION'):
        docs = mymodule.DOCUMENATION
        docs_only = True
    else:
        try:
            docs = mymodule.__doc__
            docs_only = False
        except:
            pass

    if not docs:
        raise AnsibleError("Could not find documentation for %s" % module_file)

    try:
        return docs_to_argspec(docs, docs_only)
    except AnsibleError as e:
        raise AnsibleError("Failed to parse docs for %s: %s" % (module_file, str(e)))

def docs_to_argspec(docstring, just_docs=True):
    ''' allows modules to use documentation as spec '''

    try:
        docs = yaml.load(docstring)
    except yaml.YAMLError, e:
        raise AnsibleError("Could not parse module doc string: %s" % str(e))
    if not just_docs:
        docs = docs.get('documentation')

    if not docs:
        raise AnsibleError("No usable module docs found")

    if 'options' not in docs:
        raise AnsibleError('No options to process into spec')

    options = {}
    for (key, value) in docs['options'].items():

        options[key] = {}

        if 'type' in value:
            # skip str as its the default
            if value['type'] not in ('str', 'string'):
                #FIXME: translate 'long form types'?
                options[key]['type'] = value['type']

        if 'choices' in value:
            if value.get('type') not in ('bool', 'boolean'):
                #FIXME: should check choices are a list
                options[key]['choices'] = value['choices']

        if 'default' in value:
            if value['default'] != None:
                if value.get('type', '') in ['bool', 'boolean'] and value['default'] not in (True, False):
                    raise ValueError('invalid value for bool')
                if 'choices' in options[key] and value['default'] not in options[key]['choices']:
                    raise ValueError('specified default is not a valid choice')
                options[key]['default'] = value['default']

        if 'aliases' in value:
            #FIXME: should check aliases are a list
            options[key]['aliases'] = value['aliases']

        if 'no_log' in value:
            if value['no_log'] in (True, False):
                options[key]['no_log'] = value['no_log']
            else:
                raise ValueError('invalid value for no_log, it must be a boolean')

    return options
