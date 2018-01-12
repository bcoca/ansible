# Copyright: (c) 2018, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


import datetime
import os
import json
import socket
import ssl
import sys

from ansible import constants as C
from ansible.cli import CLI
from ansible.errors import AnsibleOptionsError
from ansible.module_utils._text import to_native, to_text
from ansible.utils.cmd_functions import run_cmd

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class AgentCLI(CLI):
    ''' cucukachu '''

    def __init__(self, args, callback=None):

        super(AgentCLI, self).__init__(args, callback)

        self._sock = None
        self._connection = None

    def parse(self):
        ''' create an options parser for bin/ansible '''

        self.parser = CLI.base_parser(
            usage='%prog [options]',
            vault_opts=True,
            module_opts=True,
            desc="pulls playbooks from a VCS repo and executes them for the local host",
        )

        # options unique to pull
        self.parser.add_option('--listen', default=C.AGENT_LISTEN, action='store', dest='agent_listen', help='address and port to listen on')
        self.parser.add_option('--no-ssl', dest='use_ssl', default=C.AGENT_USE_SSL, action='store_false', help='deactivate ssl when listening on port')
        self.parser.add_option('--host-cert', default=C.AGENT_HOST_CERT, dest='host_cert', action='store', help='adds the hostkey for the repo url if not already added')
        self.parser.add_option('--ca-cert', default=C.AGENT_CA_CERT, dest='ca_cert', action='store', help='adds the hostkey for the repo url if not already added')

        super(AgentCLI, self).parse()

        display.verbosity = self.options.verbosity
        self.validate_conflicts(vault_opts=True)

    def _send(self, msg, **kwargs):
        self._connection.sendall(json.dump({'msg': msg}.update(kwargs or {})))

    def _fail(self, msg, **kwargs):
        self._send(msg, {'failed': True}.update(kwargs or {}))
        sys.exit(msg)

    def run(self):
        ''' listen to requests and peform ansible tasks '''

        super(AgentCLI, self).run()

        # daemonize

        # my bin path!
        bin_path = os.path.dirname(os.path.abspath(sys.argv[0]))

        # log command line
        now = datetime.datetime.now()
        display.log(now.strftime("Starting Ansible Agent at %F %T"))
        display.log(' '.join(sys.argv))

        # FIXME: better file vs address detection, find way to automate coin flip.
        if os.path.sep in socket:
            try:
                os.unlink(self.options.agent_listen)
            except OSError:
                if os.path.exists(self.options.agent_listen):
                    raise AnsibleOptionsError("Socket already exists and we cannot replace it: %s" % to_native(self.options.agent_listen))

            self._sock = socket.socket()
        else:
            # FIXME: ipv6 support? or just ride out ipv4 till end of times.
            self._sock = socket.socket(socket.AF_INET)

        # FIXME: roll our own encryption .. cause ... no really, find reason.
        if self.options.use_ssl:
            self._sock = ssl.wrap_socket(self._sock) # keyfile=None, certfile=None, server_side=False, cert_reqs=CERT_NONE, ssl_version={see docs}, ca_certs=None, do_handshake_on_connect=True, suppress_ragged_eofs=True, ciphers=None)

        #socket.settimeout(float_value)

        self._sock.bind(self.options.agent_socket)
        self._sock.listen(1) # fixme config backlog .. probs to num forks

        try:
            while True:  # connection loop
                display.log('waiting for connections')
                self._connection, self._client_address = self._sock.accept()
                req = ''
                try:
                    while True:  # request loop
                        display.log('reading data from %s' % self._client_address)
                        data = self._conection.recv(256)
                        if data:
                            req += data
                        else:
                            display.log('no more data form %s' % self._client_address)
                            break

                    try:
                        request = json.loads(req)
                    except Exception as e:
                        self._fail('failed to parse msg: %s' % to_text(e))
                        break

                    shell = False
                    # process request
                    if 'shell' in request:
                        cmd = request['shell']
                        shell = True
                    elif 'command' in request:
                        cmd = request['command']
                    elif 'pull' in request:
                        cmd = '%s/ansible-pull%s %s' % (bin_path, self.options)
                    elif 'die' in request:
                        self._fail('brain bomb activated')
                        sys.exit('harakiri')
                    elif 'end' in request:
                        break
                    elif 'task' in request:
                        self._run_task(request)
                    else:
                        self._fail('Unknown request recieved, ignoring')

                    if cmd:
                        display.log("running ansible to do actual work")
                        display.debug('EXEC: %s' % cmd)
                        rc, out, err = run_cmd(cmd, shell=shell, live=True)

                        # send response
                        self._send('ran X', {'rc': rc, 'stdout': out, 'stderr': err})
                finally:
                    self._connection.close()
        finally:
            self._sock.shutdown(socket.SHUT_RDWR)
            self._sock.close()

    def _run_task(self, request):

        from ansible.executor.task_queue_manager import TaskQueueManager
        from ansible.playbook.play import Play
        from ansible.playbook.task import Task
        from ansible.plugins.loader import get_all_plugin_loaders

        # deal with passwords
        self.normalize_become_options()
        (sshpass, becomepass) = self.ask_passwords()

        # dynamically load any plugins
        get_all_plugin_loaders()

        # basic prereqs
        loader, inventory, variable_manager = self._play_prereqs(self.options)

        # actual task/play
        task = Task.from_attrs(request['task'])
        play = Play.load_ds(dict(name="Ansible Agent", hosts='localhost', gather_facts='no', tasks=[task]), variable_manager=variable_manager, loader=loader)

        # runit
        try:
            tqm = TaskQueueManager(
                    inventory=inventory,
                    variable_manager=variable_manager,
                    loader=loader,
                    options=self.options,
                    passwords={'conn_pass': sshpass, 'become_pass': becomepass},
                    stdout_callback=C.AGENT_CALLBACK, # FIXME: local capture or direct send by sharing the connection?
                    run_tree=False,
            )

            result = tqm.run(play)
            stats = tqm._stats
        finally:
            if tqm:
                tqm.cleanup()
            if loader:
                loader.cleanup_all_tmp_files()

        #FIXME: should we just have callback do the sends?
        self._send('executed task', dict(failed=False, result=result, stats=stats))
