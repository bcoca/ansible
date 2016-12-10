# (c) 2012-2014, Michael DeHaan <michael.dehaan@gmail.com>
#
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

import multiprocessing
import os
import tempfile

from ansible import constants as C
from ansible.compat.six import string_types
from ansible.errors import AnsibleError
from ansible.executor.play_iterator import PlayIterator
from ansible.executor.stats import AggregateStats
from ansible.module_utils._text import to_text
from ansible.playbook.block import Block
from ansible.playbook.play_context import PlayContext
from ansible.plugins import callback_loader, strategy_loader, module_loader
from ansible.plugins.callback import CallbackBase
from ansible.template import Templar
from ansible.utils.helpers import pct_to_int
from ansible.vars.hostvars import HostVars

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

__all__ = ['TaskQueueManager']


class TaskQueueManager:

    '''
    This class handles the multiprocessing requirements of Ansible by
    creating a pool of worker forks, a result handler fork, and a
    manager object with shared datastructures/queues for coordinating
    work between all processes.

    The queue manager is responsible for loading the play strategy plugin,
    which dispatches the Play's tasks to hosts.
    '''

    RUN_OK                = 0
    RUN_ERROR             = 1
    RUN_FAILED_HOSTS      = 2
    RUN_UNREACHABLE_HOSTS = 4
    RUN_FAILED_BREAK_PLAY = 8
    RUN_UNKNOWN_ERROR     = 255

    def __init__(self, inventory, variable_manager, loader, options, passwords, callbacks=None ):

        self._inventory        = inventory
        self._variable_manager = variable_manager
        self._loader           = loader
        self._options          = options
        self._stats            = AggregateStats()
        self.passwords         = passwords
        self._start_at_done    = False

        if callbacks is None:
            self._callbacks = []
        else:
            self.callbacks = callbacks

        # make sure the module path (if specified) is parsed and
        # added to the module_loader object
        if options.module_path is not None:
            for path in options.module_path.split(os.pathsep):
                module_loader.add_directory(path)

        # a special flag to help us exit cleanly
        self._terminated = False

        # this dictionary is used to keep track of notified handlers
        self._notified_handlers = dict()
        self._listening_handlers = dict()

        # dictionaries to keep track of failed/unreachable hosts
        self._failed_hosts      = dict()
        self._unreachable_hosts = dict()

        self._final_q = multiprocessing.Queue()

        # A temporary file (opened pre-fork) used by connection
        # plugins for inter-process locking.
        self._connection_lockfile = tempfile.TemporaryFile()

    def _initialize_processes(self, num):
        self._workers = []

        for i in range(num):
            rslt_q = multiprocessing.Queue()
            self._workers.append([None, rslt_q])

    def _initialize_notified_handlers(self, play):
        '''
        Clears and initializes the shared notified handlers dict with entries
        for each handler in the play, which is an empty array that will contain
        inventory hostnames for those hosts triggering the handler.
        '''

        # Zero the dictionary first by removing any entries there.
        # Proxied dicts don't support iteritems, so we have to use keys()
        self._notified_handlers.clear()
        self._listening_handlers.clear()

        def _process_block(b):
            temp_list = []
            for t in b.block:
                if isinstance(t, Block):
                    temp_list.extend(_process_block(t))
                else:
                    temp_list.append(t)
            return temp_list

        handler_list = []
        for handler_block in play.handlers:
            handler_list.extend(_process_block(handler_block))

        # then initialize it with the given handler list
        for handler in handler_list:
            if handler not in self._notified_handlers:
                self._notified_handlers[handler] = []
            if handler.listen:
                listeners = handler.listen
                if not isinstance(listeners, list):
                    listeners = [ listeners ]
                for listener in listeners:
                    if listener not in self._listening_handlers:
                        self._listening_handlers[listener] = []

                    # if the handler has a name, we append it to the list of listening
                    # handlers, otherwise we use the uuid to avoid trampling on other
                    # nameless listeners
                    if handler.name:
                        self._listening_handlers[listener].append(handler.get_name())
                    else:
                        self._listening_handlers[listener].append(handler._uuid)

    def run(self, play):
        '''
        Iterates over the roles/tasks in a play, using the given (or default)
        strategy for queueing tasks. The default is the linear strategy, which
        operates like classic Ansible by keeping all hosts in lock-step with
        a given task (meaning no hosts move on to the next task until all hosts
        are done with the current task).
        '''

        all_vars = self._variable_manager.get_vars(loader=self._loader, play=play)
        templar = Templar(loader=self._loader, variables=all_vars)

        new_play = play.copy()
        new_play.post_validate(templar)
        new_play.handlers = new_play.compile_roles_handlers() + new_play.handlers

        self.hostvars = HostVars(
            inventory=self._inventory,
            variable_manager=self._variable_manager,
            loader=self._loader,
        )

        # Fork # of forks, # of hosts or serial, whichever is lowest
        num_hosts = len(self._inventory.get_hosts(new_play.hosts, ignore_restrictions=True))

        max_serial = 0
        if new_play.serial:
            # the play has not been post_validated here, so we may need
            # to convert the scalar value to a list at this point
            serial_items = new_play.serial
            if not isinstance(serial_items, list):
                serial_items = [serial_items]
            max_serial = max([pct_to_int(x, num_hosts) for x in serial_items])

        contenders = [self._options.forks, max_serial, num_hosts]
        contenders = [v for v in contenders if v is not None and v > 0]
        self._initialize_processes(min(contenders))

        play_context = PlayContext(new_play, self._options, self.passwords, self._connection_lockfile.fileno())
        for callback_plugin in self._callbacks:
            if hasattr(callback_plugin, 'set_play_context'):
                callback_plugin.set_play_context(play_context)

        display.send_callback('v2_playbook_on_play_start', new_play)

        # initialize the shared dictionary containing the notified handlers
        self._initialize_notified_handlers(new_play)

        # load the specified strategy (or the default linear one)
        strategy = strategy_loader.get(new_play.strategy, self)
        if strategy is None:
            raise AnsibleError("Invalid play strategy specified: %s" % new_play.strategy, obj=play._ds)

        # build the iterator
        iterator = PlayIterator(
            inventory=self._inventory,
            play=new_play,
            play_context=play_context,
            variable_manager=self._variable_manager,
            all_vars=all_vars,
            start_at_done = self._start_at_done,
        )

        # Because the TQM may survive multiple play runs, we start by marking
        # any hosts as failed in the iterator here which may have been marked
        # as failed in previous runs. Then we clear the internal list of failed
        # hosts so we know what failed this round.
        for host_name in self._failed_hosts.keys():
            host = self._inventory.get_host(host_name)
            iterator.mark_host_failed(host)

        self.clear_failed_hosts()

        # during initialization, the PlayContext will clear the start_at_task
        # field to signal that a matching task was found, so check that here
        # and remember it so we don't try to skip tasks on future plays
        if getattr(self._options, 'start_at_task', None) is not None and play_context.start_at_task is None:
            self._start_at_done = True

        # and run the play using the strategy and cleanup on way out
        play_return = strategy.run(iterator, play_context)

        # now re-save the hosts that failed from the iterator to our internal list
        for host_name in iterator.get_failed_hosts():
            self._failed_hosts[host_name] = True

        strategy.cleanup()
        self._cleanup_processes()
        return play_return

    def cleanup(self):
        display.debug("RUNNING CLEANUP")
        self.terminate()
        self._final_q.close()
        self._cleanup_processes()

    def _cleanup_processes(self):
        if hasattr(self, '_workers'):
            for (worker_prc, rslt_q) in self._workers:
                rslt_q.close()
                if worker_prc and worker_prc.is_alive():
                    try:
                        worker_prc.terminate()
                    except AttributeError:
                        pass

    def clear_failed_hosts(self):
        self._failed_hosts = dict()

    def get_inventory(self):
        return self._inventory

    def get_variable_manager(self):
        return self._variable_manager

    def get_loader(self):
        return self._loader

    def get_workers(self):
        return self._workers[:]

    def terminate(self):
        self._terminated = True

    def has_dead_workers(self):

        # [<WorkerProcess(WorkerProcess-2, stopped[SIGKILL])>,
        # <WorkerProcess(WorkerProcess-2, stopped[SIGTERM])>

        defunct = False
        for idx,x in enumerate(self._workers):
            if hasattr(x[0], 'exitcode'):
                if x[0].exitcode in [-9, -15]:
                    defunct = True
        return defunct

