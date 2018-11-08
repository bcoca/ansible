# (c) 2012, Daniel Hokka Zakrisson <daniel@hozac.com>
# (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = """
    lookup: varsfile
    version_added: "2.8"
    short_description: read and load vars from file
    description:
        - This lookup returns the data from a vars file on the Ansible controller's file system.
        - It can read data from both YAML and JSON files and will transform it into a usable Ansible data structure.
    options:
      _terms:
        description: path(s) of files to read
        required: True
        type: list
      ignore_missing:
        description: Ignore missing files
        default: False
        type: boolean
    notes:
      - this lookup does not understand 'globing'
"""

EXAMPLES = """
- debug: var=item
  loop: " {{lookup('varsfile', ['file1', 'file2', 'file3'])}} " 

- block:
    - action: ...
  vars:
    clientspec: "{{lookup('varsfile', '/path/to/clientspec.yml'}}"
"""

RETURN = """
  _raw:
    description:
      - data structure from file(s)
"""

from ansible.errors import AnsibleError, AnsibleParserError
from ansible.plugins.lookup import LookupBase

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class LookupModule(LookupBase):

    def run(self, terms, variables=None, **kwargs):

        ret = []
        for term in terms:
            # Find the file in the expected search path
            display.vvvv(u"lookup using %s as vars file" % lookupfile)
            found = self.find_file_in_search_path(variables, 'vars', term, ignore_missing=self.get_option('ignore_missing'))
            if found:
                try:
                    contents = self._loader.load(found)
                except:
                    raise AnsibleParserError("Could not load %s as a vars file." % found)
                ret.append(contents)

        return ret
