# (c) 2016 Red Hat Inc.
# (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = """
---
author: Ansible Networking Team
connection: network_cli
short_description: Use network_cli to run command on network appliances
description:
  - This connection plugin provides a connection to remote devices over the
    SSH and implements a CLI shell.  This connection plugin is typically used by
    network devices for sending and receiving CLi commands to network devices.
version_added: "2.3"
fragments:
    - connection_persistent
    - connection_paramiko
options:
  network_os:
    description:
      - Configures the device platform network operating system.  This value is
        used to load the correct terminal and cliconf plugins to communicate
        with the remote device.
    vars:
      - name: ansible_network_os
"""

import getpass
import json
import logging
import re
import os
import signal
import socket
import traceback
from io import BytesIO

from ansible.errors import AnsibleConnectionFailure
from ansible.module_utils.six import PY3
from ansible.module_utils.six.moves import cPickle
from ansible.module_utils.network.common.utils import to_list
from ansible.module_utils._text import to_bytes, to_text
from ansible.playbook.play_context import PlayContext
from ansible.plugins.connection import NetworkConnectionBase
from ansible.plugins.loader import cliconf_loader, terminal_loader, connection_loader


class AnsibleCmdRespRecv(Exception):
    pass


class Connection(NetworkConnectionBase):
    ''' CLI (shell) SSH connections on Paramiko '''

    transport = 'network_cli'
    has_pipelining = True

    def __init__(self, play_context, new_stdin, *args, **kwargs):
        super(Connection, self).__init__(play_context, new_stdin, *args, **kwargs)

        self._ssh_shell = None

        self._matched_prompt = None
        self._matched_cmd_prompt = None
        self._matched_pattern = None
        self._last_response = None
        self._history = list()
        self._command_response = None

        self._terminal = None
        self.cliconf = None
        self.paramiko_conn = None

        if self._play_context.verbosity > 3:
            logging.getLogger('paramiko').setLevel(logging.DEBUG)

        if self._network_os:

            self.cliconf = cliconf_loader.get(self._network_os, self)
            if self.cliconf:
                self.queue_message('vvvv', 'loaded cliconf plugin for network_os %s' % self._network_os)
                self._sub_plugin = {'type': 'cliconf', 'name': self._network_os, 'obj': self.cliconf}
            else:
                self.queue_message('vvvv', 'unable to load cliconf for network_os %s' % self._network_os)
        else:
            raise AnsibleConnectionFailure(
                'Unable to automatically determine host network os. Please '
                'manually configure ansible_network_os value for this host'
            )
        self.queue_message('log', 'network_os is set to %s' % self._network_os)

    def _get_log_channel(self):
        name = "p=%s u=%s | " % (os.getpid(), getpass.getuser())
        name += "paramiko [%s]" % self._play_context.remote_addr
        return name

    def get_prompt(self):
        """Returns the current prompt from the device"""
        return self._matched_prompt

    def exec_command(self, cmd, in_data=None, sudoable=True):
        # this try..except block is just to handle the transition to supporting
        # network_cli as a toplevel connection.  Once connection=local is gone,
        # this block can be removed as well and all calls passed directly to
        # the local connection
        if self._ssh_shell:
            try:
                cmd = json.loads(to_text(cmd, errors='surrogate_or_strict'))
                kwargs = {'command': to_bytes(cmd['command'], errors='surrogate_or_strict')}
                for key in ('prompt', 'answer', 'sendonly', 'newline', 'prompt_retry_check'):
                    if cmd.get(key) is True or cmd.get(key) is False:
                        kwargs[key] = cmd[key]
                    elif cmd.get(key) is not None:
                        kwargs[key] = to_bytes(cmd[key], errors='surrogate_or_strict')
                return self.send(**kwargs)
            except ValueError:
                cmd = to_bytes(cmd, errors='surrogate_or_strict')
                return self.send(command=cmd)

        else:
            return super(Connection, self).exec_command(cmd, in_data, sudoable)

    def update_play_context(self, pc_data):
        """Updates the play context information for the connection"""
        pc_data = to_bytes(pc_data)
        if PY3:
            pc_data = cPickle.loads(pc_data, encoding='bytes')
        else:
            pc_data = cPickle.loads(pc_data)
        play_context = PlayContext()
        play_context.deserialize(pc_data)

        self.queue_message('vvvv', 'updating play_context for connection')
        if self._play_context.become ^ play_context.become:
            if play_context.become is True:
                auth_pass = play_context.become_pass
                self._terminal.on_become(passwd=auth_pass)
                self.queue_message('vvvv', 'authorizing connection')
            else:
                self._terminal.on_unbecome()
                self.queue_message('vvvv', 'deauthorizing connection')

        self._play_context = play_context

        if hasattr(self, 'reset_history'):
            self.reset_history()
        if hasattr(self, 'disable_response_logging'):
            self.disable_response_logging()

    def _connect(self):
        '''
        Connects to the remote device and starts the terminal
        '''
        if not self.connected:
            self.paramiko_conn = connection_loader.get('paramiko', self._play_context, '/dev/null')
            self.paramiko_conn._set_log_channel(self._get_log_channel())
            self.paramiko_conn.set_options(direct={'look_for_keys': not bool(self._play_context.password and not self._play_context.private_key_file)})
            self.paramiko_conn.force_persistence = self.force_persistence
            ssh = self.paramiko_conn._connect()

            host = self.get_option('remote_addr')
            self.queue_message('vvvv', 'ssh connection done, setting terminal')

            self._ssh_shell = ssh.ssh.invoke_shell()
            self._ssh_shell.settimeout(self.get_option('persistent_command_timeout'))

            self._terminal = terminal_loader.get(self._network_os, self)
            if not self._terminal:
                raise AnsibleConnectionFailure('network os %s is not supported' % self._network_os)

            self.queue_message('vvvv', 'loaded terminal plugin for network_os %s' % self._network_os)

            self.receive(prompts=self._terminal.terminal_initial_prompt, answer=self._terminal.terminal_initial_answer,
                         newline=self._terminal.terminal_inital_prompt_newline)

            self.queue_message('vvvv', 'firing event: on_open_shell()')
            self._terminal.on_open_shell()

            if self._play_context.become and self._play_context.become_method == 'enable':
                self.queue_message('vvvv', 'firing event: on_become')
                auth_pass = self._play_context.become_pass
                self._terminal.on_become(passwd=auth_pass)

            self.queue_message('vvvv', 'ssh connection has completed successfully')
            self._connected = True

        return self

    def close(self):
        '''
        Close the active connection to the device
        '''
        # only close the connection if its connected.
        if self._connected:
            self.queue_message('debug', "closing ssh connection to device")
            if self._ssh_shell:
                self.queue_message('debug', "firing event: on_close_shell()")
                self._terminal.on_close_shell()
                self._ssh_shell.close()
                self._ssh_shell = None
                self.queue_message('debug', "cli session is now closed")

                self.paramiko_conn.close()
                self.paramiko_conn = None
                self.queue_message('debug', "ssh connection has been closed successfully")
        super(Connection, self).close()

    def receive(self, command=None, prompts=None, answer=None, newline=True, prompt_retry_check=False, check_all=False):
        '''
        Handles receiving of output from command
        '''
        self._matched_prompt = None
        self._matched_cmd_prompt = None
        recv = BytesIO()
        handled = False
        command_prompt_matched = False
        matched_prompt_window = window_count = 0

        cache_socket_timeout = self._ssh_shell.gettimeout()
        command_timeout = self.get_option('persistent_command_timeout')
        self._validate_timeout_value(command_timeout, "persistent_command_timeout")
        if cache_socket_timeout != command_timeout:
            self._ssh_shell.settimeout(command_timeout)

        buffer_read_timeout = self.get_option('persistent_buffer_read_timeout')
        self._validate_timeout_value(buffer_read_timeout, "persistent_buffer_read_timeout")

        self._log_messages("command: %s" % command)
        while True:
            if command_prompt_matched:
                try:
                    signal.signal(signal.SIGALRM, self._handle_buffer_read_timeout)
                    signal.setitimer(signal.ITIMER_REAL, buffer_read_timeout)
                    data = self._ssh_shell.recv(256)
                    signal.alarm(0)
                    self._log_messages("response-%s: %s" % (window_count + 1, data))
                    # if data is still received on channel it indicates the prompt string
                    # is wrongly matched in between response chunks, continue to read
                    # remaining response.
                    command_prompt_matched = False

                    # restart command_timeout timer
                    signal.signal(signal.SIGALRM, self._handle_command_timeout)
                    signal.alarm(command_timeout)

                except AnsibleCmdRespRecv:
                    # reset socket timeout to global timeout
                    self._ssh_shell.settimeout(cache_socket_timeout)
                    return self._command_response
            else:
                data = self._ssh_shell.recv(256)
                self._log_messages("response-%s: %s" % (window_count + 1, data))
            # when a channel stream is closed, received data will be empty
            if not data:
                break

            recv.write(data)
            offset = recv.tell() - 256 if recv.tell() > 256 else 0
            recv.seek(offset)

            window = self._strip(recv.read())
            window_count += 1

            if prompts and not handled:
                handled = self._handle_prompt(window, prompts, answer, newline, False, check_all)
                matched_prompt_window = window_count
            elif prompts and handled and prompt_retry_check and matched_prompt_window + 1 == window_count:
                # check again even when handled, if same prompt repeats in next window
                # (like in the case of a wrong enable password, etc) indicates
                # value of answer is wrong, report this as error.
                if self._handle_prompt(window, prompts, answer, newline, prompt_retry_check, check_all):
                    raise AnsibleConnectionFailure("For matched prompt '%s', answer is not valid" % self._matched_cmd_prompt)

            if self._find_prompt(window):
                self._last_response = recv.getvalue()
                resp = self._strip(self._last_response)
                self._command_response = self._sanitize(resp, command)
                if buffer_read_timeout == 0.0:
                    # reset socket timeout to global timeout
                    self._ssh_shell.settimeout(cache_socket_timeout)
                    return self._command_response
                else:
                    command_prompt_matched = True

    def send(self, command, prompt=None, answer=None, newline=True, sendonly=False, prompt_retry_check=False, check_all=False):
        '''
        Sends the command to the device in the opened shell
        '''
        if check_all:
            prompt_len = len(to_list(prompt))
            answer_len = len(to_list(answer))
            if prompt_len != answer_len:
                raise AnsibleConnectionFailure("Number of prompts (%s) is not same as that of answers (%s)" % (prompt_len, answer_len))
        try:
            self._history.append(command)
            self._ssh_shell.sendall(b'%s\r' % command)
            if sendonly:
                return
            response = self.receive(command, prompt, answer, newline, prompt_retry_check, check_all)
            return to_text(response, errors='surrogate_or_strict')
        except (socket.timeout, AttributeError):
            self.queue_message('error', traceback.format_exc())
            raise AnsibleConnectionFailure("timeout value %s seconds reached while trying to send command: %s"
                                           % (self._ssh_shell.gettimeout(), command.strip()))

    def _handle_buffer_read_timeout(self, signum, frame):
        self.queue_message('vvvv', "Response received, triggered 'persistent_buffer_read_timeout' timer of %s seconds" %
                           self.get_option('persistent_buffer_read_timeout'))
        raise AnsibleCmdRespRecv()

    def _handle_command_timeout(self, signum, frame):
        msg = 'command timeout triggered, timeout value is %s secs.\nSee the timeout setting options in the Network Debug and Troubleshooting Guide.'\
              % self.get_option('persistent_command_timeout')
        self.queue_message('log', msg)
        raise AnsibleConnectionFailure(msg)

    def _strip(self, data):
        '''
        Removes ANSI codes from device response
        '''
        for regex in self._terminal.ansi_re:
            data = regex.sub(b'', data)
        return data

    def _handle_prompt(self, resp, prompts, answer, newline, prompt_retry_check=False, check_all=False):
        '''
        Matches the command prompt and responds

        :arg resp: Byte string containing the raw response from the remote
        :arg prompts: Sequence of byte strings that we consider prompts for input
        :arg answer: Sequence of Byte string to send back to the remote if we find a prompt.
                A carriage return is automatically appended to this string.
        :param prompt_retry_check: Bool value for trying to detect more prompts
        :param check_all: Bool value to indicate if all the values in prompt sequence should be matched or any one of
                          given prompt.
        :returns: True if a prompt was found in ``resp``. If check_all is True
                  will True only after all the prompt in the prompts list are matched. False otherwise.
        '''
        single_prompt = False
        if not isinstance(prompts, list):
            prompts = [prompts]
            single_prompt = True
        if not isinstance(answer, list):
            answer = [answer]
        prompts_regex = [re.compile(r, re.I) for r in prompts]
        for index, regex in enumerate(prompts_regex):
            match = regex.search(resp)
            if match:
                self._matched_cmd_prompt = match.group()
                self._log_messages("matched command prompt: %s" % self._matched_cmd_prompt)

                # if prompt_retry_check is enabled to check if same prompt is
                # repeated don't send answer again.
                if not prompt_retry_check:
                    prompt_answer = answer[index] if len(answer) > index else answer[0]
                    self._ssh_shell.sendall(b'%s' % prompt_answer)
                    if newline:
                        self._ssh_shell.sendall(b'\r')
                        prompt_answer += b'\r'
                    self._log_messages("matched command prompt answer: %s" % prompt_answer)
                if check_all and prompts and not single_prompt:
                    prompts.pop(0)
                    answer.pop(0)
                    return False
                return True
        return False

    def _sanitize(self, resp, command=None):
        '''
        Removes elements from the response before returning to the caller
        '''
        cleaned = []
        for line in resp.splitlines():
            if (command and line.strip() == command.strip()) or self._matched_prompt.strip() in line:
                continue
            cleaned.append(line)
        return b'\n'.join(cleaned).strip()

    def _find_prompt(self, response):
        '''Searches the buffered response for a matching command prompt
        '''
        errored_response = None
        is_error_message = False
        for regex in self._terminal.terminal_stderr_re:
            if regex.search(response):
                is_error_message = True

                # Check if error response ends with command prompt if not
                # receive it buffered prompt
                for regex in self._terminal.terminal_stdout_re:
                    match = regex.search(response)
                    if match:
                        errored_response = response
                        self._matched_pattern = regex.pattern
                        self._matched_prompt = match.group()
                        self._log_messages("matched error regex '%s' from response '%s'" % (self._matched_pattern, errored_response))
                        break

        if not is_error_message:
            for regex in self._terminal.terminal_stdout_re:
                match = regex.search(response)
                if match:
                    self._matched_pattern = regex.pattern
                    self._matched_prompt = match.group()
                    self._log_messages("matched cli prompt '%s' with regex '%s' from response '%s'" % (self._matched_prompt, self._matched_pattern, response))
                    if not errored_response:
                        return True

        if errored_response:
            raise AnsibleConnectionFailure(errored_response)

        return False

    def _validate_timeout_value(self, timeout, timer_name):
        if timeout < 0:
            raise AnsibleConnectionFailure("'%s' timer value '%s' is invalid, value should be greater than or equal to zero." % (timer_name, timeout))
