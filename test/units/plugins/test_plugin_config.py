# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

import sys
import unittest

from unittest.mock import MagicMock, patch

from ansible.plugins import AnsiblePlugin  #, AnsibleJinja2Plugin

# constants config
myC = MagicMock()
myC.config = MagicMock()

import q

@patch('ansible.plugins.C', myC)
class TestErrors(unittest.TestCase):

    def setUp(self):
        # ansible.plugins.C.config.initialize_plugin_configuration_definitions('Ansible', 'ansible_test', dstring['options'])

        '''
        myC.config.get_configuration_definitions = MagicMock() #(plugin_type=self.plugin_type, name=self._load_name)
        myC.config.get_plugin_options = MagicMock() #(self.plugin_type, self._load_name, keys=task_keys, variables=var_options, direct=direct)
        myC.config.get_config_value_and_origin = MagicMock() # (option, plugin_type=self.plugin_type, plugin_name=self._load_name, variables=hostvars)
        myC.config.get_config_value = MagicMock() #(option, plugin_type=self.plugin_type, plugin_name=self._load_name, direct={option: value})
        myC.config.get_config_default = MagicMock() # (option, plugin_type=self.plugin_type, plugin_name=self._load_name)
        '''

        self.p = AnsiblePlugin()
        self.p._load_name = 'ansible_test'
        #self.p._defs = None

    def test_plugin_type(self):
        self.assertEqual(self.p.plugin_type, 'ansibleplugin')

    @unittest.skip('TODO')
    def test_set_options(self):
        pass

    @unittest.skip('TODO')
    def test_set_option(self):
        pass

    @unittest.skip('TODO')
    def test_has_option(self):
        pass

    @unittest.skip('TODO')
    def test_get_options(self):
        pass

    @unittest.skip('TODO')
    def test_get_option(self):
        pass

    @unittest.skip('TODO')
    def test_get_option_and_origin(self):
        pass

    @unittest.skip('TODO')
    def test_get_option_default(self):
        pass

    def tearDown(self):
        myC.config = MagicMock()


if __name__ == "__main__":
    unittest.main()
