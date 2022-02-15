#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2012, Michael DeHaan <michael.dehaan@gmail.com>
# Copyright: (c) 2017, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


DOCUMENTATION = r'''
---
module: fso
version_added: histerical
short_description: Manage file system objects and their properties
extends_documentation_fragment: [files, action_common_attributes]
description:
- Set attributes file system objects
- Alternatively, create or remove files, symlinks and directories.
options:
  path:
    description:
    - Path to the file being managed.
    type: path
    required: yes
  type:
    description: type of file system object
    type: string
    choices:
        file: a normal file
        link: a symbolic link
        hard: a hard link or additional file reference
        directory: container of files
        #pipe: unix named pipe
  state:
    type: string
    choices: ['present', 'absent']
    default: 'present'
  src:
    description:
        - For C(type='link') and C(type='hard'), the path of the file to link to.
        - Relative paths are relative to the file being created (C(path)) which is how
          the Unix command C(ln) treats relative paths.
    type: path
  force:
    description:
        - For certain cases in which a conflict is detected, this forces the operation, which would fail otherwise.
        - "Create a symlink when C(type='link') in two cases: the source file does not exist (may appear later) or
          the destination exists and is a file (which will get deleted)
        - Create a hard link when C(type='hard') and a file already exists in the destination
        - Create a directory when C(type=directory), C(state=present) and a file already exists in that path
        - Remove a directory when C(type=directory), C(state=absent) and that directory has contents
    type: bool
    default: no
  follow:
    description: This flag indicates that filesystem links, if they exist and are not being specifically operated on, should be followed.
    type: bool
    default: yes
  mtime:
    description:
    - This parameter indicates the time the file system object's "modification time" should be set to (if possible).
    - If not set, it will preserve the original.
    - Values must be in seconds from epoch or the string C(now)
    type: str
    aliases: [modification_time]
  atime:
    description:
    - This parameter indicates the time the file system object's "access time" should be set to (if possible).
    - If not set, it will preserve the original.
    - Values must be in seconds from epoch or the string C(now)
    type: str
    aliases: [access_time]
 #acls:
 #xattr:
seealso:
  - module: ansible.builtin.assemble
  - module: ansible.builtin.copy
  - module: ansible.builtin.file
  - module: ansible.builtin.stat
  - module: ansible.builtin.template
  - module: ansible.windows.win_file
attributes:
  check_mode:
      support: full
  diff_mode:
      details: permissions and ownership will be shown but contents will not, since this action does not really modify it.
      support: partial
  platform:
      platforms: posix
author:
 - Ansible Core Team
'''

EXAMPLES = r'''
- name: Ensure file ownership, group and permissions
  ansible.builtin.fso:
    path: /etc/foo.conf
    owner: foo
    group: foo
    mode: '0644'
    type: file
    state: present

- name: Ensure insecure permissions to an existing file
  ansible.builtin.fso:
    path: /work
    owner: root
    group: root
    mode: '1777'

- name: Ensure symbolic link
  ansible.builtin.fso:
    src: /file/to/link/to
    path: /path/to/symlink
    owner: foo
    group: foo
    type: link
    state: present

- name: Ensure hard links exist
  ansible.builtin.fso:
    src: '/tmp/{{ item.src }}'
    path: '{{ item.dest }}'
    type: hard
  loop:
    - { src: x, dest: y }
    - { src: z, dest: k }

- name: Using symbolic modes to establish wanted permissions (equivalent to 0644)
  ansible.builtin.fso:
    path: /etc/foo.conf
    state: present
    mode: u=rw,g=r,o=r

- name: Ensure directory exists with specific permissions
  ansible.builtin.fso:
    path: /etc/some_directory
    state: directory
    mode: '0755'

- name: Update modification and access time of given file to 'now'
  ansible.builtin.fso:
    path: /etc/some_file
    state: file
    mtime: now
    atime: now

- name: Ensure access time based on previous stat (in seconds from epoch value)
  ansible.builtin.fso:
    path: /etc/another_file
    state: file
    atime: '{{ "%Y%m%d%H%M.%S" | strftime(stat_var.stat.atime) }}'

- name: Ensure file does not exist (removes/deletes/unliks if it does)
  ansible.builtin.fso:
    path: /etc/foo.txt
    type: file
    state: absent

- name: Ensure directory does not exist (will recursively remove)
  ansible.builtin.fso:
    path: /etc/foo
    force: true
    type: directory
    state: absent

'''
RETURN = r'''
# TODO: with return fragmetns add mode/owner/group/etc
path:
    description: path of the filesystem object, equal to the value passed to I(path).
    returned: always
    type: str
    sample: /path/to/file.txt
state:
    description: Current state of the object
    returned: always
    type: str
    sample: present
    choices: [present, absent]
type:
    description: Current type of the object, it will be C(None)if absent
    returned: always
    type: str
    choices: [None, file, directory, link, hard]
src:
    description: Destination file/path, equal to the value passed to I(path).
    returned: when type is hard or link
    type: str
'''

import errno
import os
import shutil
import sys
import time

from pwd import getpwnam, getpwuid
from grp import getgrnam, getgrgid

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_bytes, to_native


# There will only be a single AnsibleModule object per module
module = None


class FSOError(Exception):

    def __init__(self, result, e=None):
        self._result = result
        self._e = e

    def __repr__(self):
        global module
        module.fail_json(**self._result, traceback=self._e)


def initial_diff(path, desired_state, curr_state, desired_type, curr_type):
    diff = {'before': {'path': path},
            'after': {'path': path},

    if desired_state != curr_state:
        diff['before']['state'] = curr_state
        diff['after']['state'] = desired_state

    if desired_type != curr_type:
        diff['before']['type'] = curr_type
        diff['after']['type'] = desired_type

    return diff


def get_current(b_path):
    ''' Find out current type, if target exists or is accessible '''

    iam = None
    try:
        s = os.lstat(b_path):
        if s.st_nlink > 1:
           iam = 'hard'
        elif stat.S_ISDIR(s.st_mode)
            iam = 'directory'
        elif stat.S_ISLNK(s.st_mode)
            iam = 'link'
        else:
            # could be many other things, but defaulting to file
            # stat.S_ISFILE(s.st_mode) actual file
            iam = 'file'
    except FileNotFoundError:
        pass
    except (OSError, IOError) as e:
        # also pass if missing, old filenotfound
        if e.errno != errno.ENOENT:
            raise FSOError({'path': b_path, 'state': None, 'type': None}, e)

    return iam, ('present' if iam is not None else 'absent')


# This should be moved into the common file utilities
def recursive_set_attributes(b_path, follow, file_args, mtime, atime):
    changed = False

    try:
        for b_root, b_dirs, b_files in os.walk(b_path):
            for b_fsobj in b_dirs + b_files:
                b_fsname = os.path.join(b_root, b_fsobj)
                if not os.path.islink(b_fsname):
                    tmp_file_args = file_args.copy()
                    tmp_file_args['path'] = to_native(b_fsname, errors='surrogate_or_strict')
                    changed |= module.set_fs_attributes_if_different(tmp_file_args, changed, expand=False)
                    changed |= update_timestamp_for_file(tmp_file_args['path'], mtime, atime)

                else:
                    # Change perms on the link
                    tmp_file_args = file_args.copy()
                    tmp_file_args['path'] = to_native(b_fsname, errors='surrogate_or_strict')
                    changed |= module.set_fs_attributes_if_different(tmp_file_args, changed, expand=False)
                    changed |= update_timestamp_for_file(tmp_file_args['path'], mtime, atime)

                    if follow:
                        b_fsname = os.path.join(b_root, os.readlink(b_fsname))
                        # The link target could be nonexistent
                        if os.path.exists(b_fsname):
                            if os.path.isdir(b_fsname):
                                # Link is a directory so change perms on the directory's contents
                                changed |= recursive_set_attributes(b_fsname, follow, file_args, mtime, atime)

                            # Change perms on the file pointed to by the link
                            tmp_file_args = file_args.copy()
                            tmp_file_args['path'] = to_native(b_fsname, errors='surrogate_or_strict')
                            changed |= module.set_fs_attributes_if_different(tmp_file_args, changed, expand=False)
                            changed |= update_timestamp_for_file(tmp_file_args['path'], mtime, atime)
    except RuntimeError as e:
        # on Python3 "RecursionError" is raised which is derived from "RuntimeError"
        # TODO once this function is moved into the common file utilities, this should probably raise more general exception
        raise AnsibleModuleError(
            results={'msg': "Could not recursively set attributes on %s. Original error was: '%s'" % (to_native(b_path), to_native(e))}
        )

    return changed


#
# States
#


def get_timestamp_for_time(formatted_time, time_format):
    if formatted_time == 'preserve':
        return None
    elif formatted_time == 'now':
        return Sentinel
    else:
        try:
            struct = time.strptime(formatted_time, time_format)
            struct_time = time.mktime(struct)
        except (ValueError, OverflowError) as e:
            raise AnsibleModuleError(results={'msg': 'Error while obtaining timestamp for time %s using format %s: %s'
                                              % (formatted_time, time_format, to_native(e, nonstring='simplerepr'))})

        return struct_time


def update_timestamp(path, mtime, atime, diff=None):
    b_path = to_bytes(path, errors='surrogate_or_strict')

    try:
        # When mtime and atime are set to 'now', rely on utime(path, None) which does not require ownership of the file
        # https://github.com/ansible/ansible/issues/50943
        if mtime is Sentinel and atime is Sentinel:
            # It's not exact but we can't rely on os.stat(path).st_mtime after setting os.utime(path, None) as it may
            # not be updated. Just use the current time for the diff values
            mtime = atime = time.time()

            previous_mtime = os.stat(b_path).st_mtime
            previous_atime = os.stat(b_path).st_atime

            set_time = None
        else:
            # If both parameters are None 'preserve', nothing to do
            if mtime is None and atime is None:
                return False

            previous_mtime = os.stat(b_path).st_mtime
            previous_atime = os.stat(b_path).st_atime

            if mtime is None:
                mtime = previous_mtime
            elif mtime is Sentinel:
                mtime = time.time()

            if atime is None:
                atime = previous_atime
            elif atime is Sentinel:
                atime = time.time()

            # If both timestamps are already ok, nothing to do
            if mtime == previous_mtime and atime == previous_atime:
                return False

            set_time = (atime, mtime)

        os.utime(b_path, set_time)

        if diff is not None:
            if 'before' not in diff:
                diff['before'] = {}
            if 'after' not in diff:
                diff['after'] = {}
            if mtime != previous_mtime:
                diff['before']['mtime'] = previous_mtime
                diff['after']['mtime'] = mtime
            if atime != previous_atime:
                diff['before']['atime'] = previous_atime
                diff['after']['atime'] = atime
    except OSError as e:
        raise AnsibleModuleError(results={'msg': 'Error while updating modification or access time: %s'
                                          % to_native(e, nonstring='simplerepr'), 'path': path})
    return True


def keep_backward_compatibility_on_timestamps(parameter, state):
    if state in ['file', 'hard', 'directory', 'link'] and parameter is None:
        return 'preserve'
    elif state == 'touch' and parameter is None:
        return 'now'
    else:
        return parameter


def ensure_absent(path, force):
    ''' remove the object if it exists '''

    result = {'path': path, 'changed': False, 'state': 'absent', 'type': None}
    b_path = to_bytes(path, errors='surrogate_or_strict')

    current_type, current_state = get_current(b_path)
    result['diff'] = initial_diff(path, 'absent', current_state, None, current_type)
    if current_type is not None

        if not module.check_mode:
            if current_type == 'directory' and force:
                try:
                    shutil.rmtree(b_path, ignore_errors=False)
                except Exception as e:
                    raise AnsibleModuleError(results={'msg': "rmtree failed: %s" % to_native(e)})
            else:
                try:
                    os.unlink(b_path)
                except OSError as e:
                    if e.errno != errno.ENOENT:  # It may already have been removed
                        results['msg'] = "unlinking failed: %s " % to_native(e)
                        results['state'] = "present"
                        results['type'] = current_type
                        raise AnsibleModuleError(results)

        result'changed'] = True

    return result


def execute_touch(path, follow, atime, mtime):
    b_path = to_bytes(path, errors='surrogate_or_strict')
    prev_state = get_state(b_path)
    changed = False
    result = {'dest': path}
    mtime = get_timestamp_for_time(timestamps['modification_time'], timestamps['modification_time_format'])
    atime = get_timestamp_for_time(timestamps['access_time'], timestamps['access_time_format'])

    if not module.check_mode:
        if prev_state == 'absent':
            # Create an empty file if the filename did not already exist
            try:
                open(b_path, 'wb').close()
                changed = True
            except (OSError, IOError) as e:
                raise AnsibleModuleError(results={'msg': 'Error, could not touch target: %s'
                                                         % to_native(e, nonstring='simplerepr'),
                                                  'path': path})

        # Update the attributes on the file
        diff = initial_diff(path, 'touch', prev_state)
        file_args = module.load_file_common_arguments(module.params)
        try:
            changed = module.set_fs_attributes_if_different(file_args, changed, diff, expand=False)
            changed |= update_timestamp_for_file(file_args['path'], mtime, atime, diff)
        except SystemExit as e:
            if e.code:  # this is the exit code passed to sys.exit, not a constant -- pylint: disable=using-constant-test
                # We take this to mean that fail_json() was called from
                # somewhere in basic.py
                if prev_state == 'absent':
                    # If we just created the file we can safely remove it
                    os.remove(b_path)
            raise

        result['changed'] = changed
        result['diff'] = diff
    return result


def ensure_file_attributes(path, follow, timestamps):
    b_path = to_bytes(path, errors='surrogate_or_strict')
    prev_state = get_state(b_path)
    file_args = module.load_file_common_arguments(module.params)
    mtime = get_timestamp_for_time(timestamps['modification_time'], timestamps['modification_time_format'])
    atime = get_timestamp_for_time(timestamps['access_time'], timestamps['access_time_format'])

    if prev_state != 'file':
        if follow and prev_state == 'link':
            # follow symlink and operate on original
            b_path = os.path.realpath(b_path)
            path = to_native(b_path, errors='strict')
            prev_state = get_state(b_path)
            file_args['path'] = path

    if prev_state not in ('file', 'hard'):
        # file is not absent and any other state is a conflict
        raise AnsibleModuleError(results={'msg': 'file (%s) is %s, cannot continue' % (path, prev_state),
                                          'path': path, 'state': prev_state})

    diff = initial_diff(path, 'file', prev_state)
    changed = module.set_fs_attributes_if_different(file_args, False, diff, expand=False)
    changed |= update_timestamp_for_file(file_args['path'], mtime, atime, diff)
    return {'path': path, 'changed': changed, 'diff': diff}


def ensure_directory(path, follow, recurse, timestamps):
    b_path = to_bytes(path, errors='surrogate_or_strict')
    prev_state = get_state(b_path)
    file_args = module.load_file_common_arguments(module.params)
    mtime = get_timestamp_for_time(timestamps['modification_time'], timestamps['modification_time_format'])
    atime = get_timestamp_for_time(timestamps['access_time'], timestamps['access_time_format'])

    # For followed symlinks, we need to operate on the target of the link
    if follow and prev_state == 'link':
        b_path = os.path.realpath(b_path)
        path = to_native(b_path, errors='strict')
        file_args['path'] = path
        prev_state = get_state(b_path)

    changed = False
    diff = initial_diff(path, 'directory', prev_state)

    if prev_state == 'absent':
        # Create directory and assign permissions to it
        if module.check_mode:
            return {'path': path, 'changed': True, 'diff': diff}
        curpath = ''

        try:
            # Split the path so we can apply filesystem attributes recursively
            # from the root (/) directory for absolute paths or the base path
            # of a relative path.  We can then walk the appropriate directory
            # path to apply attributes.
            # Something like mkdir -p with mode applied to all of the newly created directories
            for dirname in path.strip('/').split('/'):
                curpath = '/'.join([curpath, dirname])
                # Remove leading slash if we're creating a relative path
                if not os.path.isabs(path):
                    curpath = curpath.lstrip('/')
                b_curpath = to_bytes(curpath, errors='surrogate_or_strict')
                if not os.path.exists(b_curpath):
                    try:
                        os.mkdir(b_curpath)
                        changed = True
                    except OSError as ex:
                        # Possibly something else created the dir since the os.path.exists
                        # check above. As long as it's a dir, we don't need to error out.
                        if not (ex.errno == errno.EEXIST and os.path.isdir(b_curpath)):
                            raise
                    tmp_file_args = file_args.copy()
                    tmp_file_args['path'] = curpath
                    changed = module.set_fs_attributes_if_different(tmp_file_args, changed, diff, expand=False)
                    changed |= update_timestamp_for_file(file_args['path'], mtime, atime, diff)
        except Exception as e:
            raise AnsibleModuleError(results={'msg': 'There was an issue creating %s as requested:'
                                                     ' %s' % (curpath, to_native(e)),
                                              'path': path})
        return {'path': path, 'changed': changed, 'diff': diff}

    elif prev_state != 'directory':
        # We already know prev_state is not 'absent', therefore it exists in some form.
        raise AnsibleModuleError(results={'msg': '%s already exists as a %s' % (path, prev_state),
                                          'path': path})

    #
    # previous state == directory
    #

    changed = module.set_fs_attributes_if_different(file_args, changed, diff, expand=False)
    changed |= update_timestamp_for_file(file_args['path'], mtime, atime, diff)
    if recurse:
        changed |= recursive_set_attributes(b_path, follow, file_args, mtime, atime)

    return {'path': path, 'changed': changed, 'diff': diff}


def ensure_symlink(path, src, follow, force, timestamps):
    b_path = to_bytes(path, errors='surrogate_or_strict')
    b_src = to_bytes(src, errors='surrogate_or_strict')
    prev_state = get_state(b_path)
    mtime = get_timestamp_for_time(timestamps['modification_time'], timestamps['modification_time_format'])
    atime = get_timestamp_for_time(timestamps['access_time'], timestamps['access_time_format'])
    # source is both the source of a symlink or an informational passing of the src for a template module
    # or copy module, even if this module never uses it, it is needed to key off some things
    if src is None:
        if follow:
            # use the current target of the link as the source
            src = to_native(os.readlink(b_path), errors='strict')
            b_src = to_bytes(src, errors='surrogate_or_strict')

    if not os.path.islink(b_path) and os.path.isdir(b_path):
        relpath = path
    else:
        b_relpath = os.path.dirname(b_path)
        relpath = to_native(b_relpath, errors='strict')

    absrc = os.path.join(relpath, src)
    b_absrc = to_bytes(absrc, errors='surrogate_or_strict')
    if not force and not os.path.exists(b_absrc):
        raise AnsibleModuleError(results={'msg': 'src file does not exist, use "force=yes" if you'
                                                 ' really want to create the link: %s' % absrc,
                                          'path': path, 'src': src})

    if prev_state == 'directory':
        if not force:
            raise AnsibleModuleError(results={'msg': 'refusing to convert from %s to symlink for %s'
                                                     % (prev_state, path),
                                              'path': path})
        elif os.listdir(b_path):
            # refuse to replace a directory that has files in it
            raise AnsibleModuleError(results={'msg': 'the directory %s is not empty, refusing to'
                                                     ' convert it' % path,
                                              'path': path})
    elif prev_state in ('file', 'hard') and not force:
        raise AnsibleModuleError(results={'msg': 'refusing to convert from %s to symlink for %s'
                                                 % (prev_state, path),
                                          'path': path})

    diff = initial_diff(path, 'link', prev_state)
    changed = False

    if prev_state in ('hard', 'file', 'directory', 'absent'):
        changed = True
    elif prev_state == 'link':
        b_old_src = os.readlink(b_path)
        if b_old_src != b_src:
            diff['before']['src'] = to_native(b_old_src, errors='strict')
            diff['after']['src'] = src
            changed = True
    else:
        raise AnsibleModuleError(results={'msg': 'unexpected position reached', 'dest': path, 'src': src})

    if changed and not module.check_mode:
        if prev_state != 'absent':
            # try to replace atomically
            b_tmppath = to_bytes(os.path.sep).join(
                [os.path.dirname(b_path), to_bytes(".%s.%s.tmp" % (os.getpid(), time.time()))]
            )
            try:
                if prev_state == 'directory':
                    os.rmdir(b_path)
                os.symlink(b_src, b_tmppath)
                os.rename(b_tmppath, b_path)
            except OSError as e:
                if os.path.exists(b_tmppath):
                    os.unlink(b_tmppath)
                raise AnsibleModuleError(results={'msg': 'Error while replacing: %s'
                                                         % to_native(e, nonstring='simplerepr'),
                                                  'path': path})
        else:
            try:
                os.symlink(b_src, b_path)
            except OSError as e:
                raise AnsibleModuleError(results={'msg': 'Error while linking: %s'
                                                         % to_native(e, nonstring='simplerepr'),
                                                  'path': path})

    if module.check_mode and not os.path.exists(b_path):
        return {'dest': path, 'src': src, 'changed': changed, 'diff': diff}

    # Now that we might have created the symlink, get the arguments.
    # We need to do it now so we can properly follow the symlink if needed
    # because load_file_common_arguments sets 'path' according
    # the value of follow and the symlink existence.
    file_args = module.load_file_common_arguments(module.params)

    # Whenever we create a link to a nonexistent target we know that the nonexistent target
    # cannot have any permissions set on it.  Skip setting those and emit a warning (the user
    # can set follow=False to remove the warning)
    if follow and os.path.islink(b_path) and not os.path.exists(file_args['path']):
        module.warn('Cannot set fs attributes on a non-existent symlink target. follow should be'
                    ' set to False to avoid this.')
    else:
        changed = module.set_fs_attributes_if_different(file_args, changed, diff, expand=False)
        changed |= update_timestamp_for_file(file_args['path'], mtime, atime, diff)

    return {'dest': path, 'src': src, 'changed': changed, 'diff': diff}


def ensure_hardlink(path, src, follow, force, atime, mtime):
    b_path = to_bytes(path, errors='surrogate_or_strict')
    b_src = to_bytes(src, errors='surrogate_or_strict')
    prev_state = get_state(b_path)
    file_args = module.load_file_common_arguments(module.params)

    # src is the source of a hardlink.  We require it if we are creating a new hardlink.
    # We require path in the argument_spec so we know it is present at this point.
    if src is None:
        raise AnsibleModuleError(results={'msg': 'src is required for creating new hardlinks'})

    if not os.path.exists(b_src):
        raise AnsibleModuleError(results={'msg': 'src does not exist', 'path': path, 'src': src})

    diff = initial_diff(path, 'hard', prev_state)
    changed = False

    if prev_state == 'absent':
        changed = True
    elif prev_state == 'link':
        b_old_src = os.readlink(b_path)
        if b_old_src != b_src:
            diff['before']['src'] = to_native(b_old_src, errors='strict')
            diff['after']['src'] = src
            changed = True
    elif prev_state == 'hard':
        if not os.stat(b_path).st_ino == os.stat(b_src).st_ino:
            changed = True
            if not force:
                raise AnsibleModuleError(results={'msg': 'Cannot link, different hard link exists at destination',
                                                  'path': path, 'src': src})
    elif prev_state == 'file':
        changed = True
        if not force:
            raise AnsibleModuleError(results={'msg': 'Cannot link, %s exists at destination' % prev_state,
                                              'path': path, 'src': src})
    elif prev_state == 'directory':
        changed = True
        if os.path.exists(b_path):
            if os.stat(b_path).st_ino == os.stat(b_src).st_ino:
                return {'path': path, 'changed': False}
            elif not force:
                raise AnsibleModuleError(results={'msg': 'Cannot link: different hard link exists at destination',
                                                  'path': path, 'src': src})
    else:
        raise AnsibleModuleError(results={'msg': 'unexpected position reached', 'path': path, 'src': src})

    if changed and not module.check_mode:
        if prev_state != 'absent':
            # try to replace atomically
            b_tmppath = to_bytes(os.path.sep).join(
                [os.path.dirname(b_path), to_bytes(".%s.%s.tmp" % (os.getpid(), time.time()))]
            )
            try:
                if prev_state == 'directory':
                    if os.path.exists(b_path):
                        try:
                            os.unlink(b_path)
                        except OSError as e:
                            if e.errno != errno.ENOENT:  # It may already have been removed
                                raise
                os.link(b_src, b_tmppath)
                os.rename(b_tmppath, b_path)
            except OSError as e:
                if os.path.exists(b_tmppath):
                    os.unlink(b_tmppath)
                raise AnsibleModuleError(results={'msg': 'Error while replacing: %s'
                                                         % to_native(e, nonstring='simplerepr'),
                                                  'path': path})
        else:
            try:
                os.link(b_src, b_path)
            except OSError as e:
                raise AnsibleModuleError(results={'msg': 'Error while linking: %s'
                                                         % to_native(e, nonstring='simplerepr'),
                                                  'path': path})

    if module.check_mode and not os.path.exists(b_path):
        return {'path': path, 'src': src, 'changed': changed, 'diff': diff}

    changed = module.set_fs_attributes_if_different(file_args, changed, diff, expand=False)
    changed |= update_timestamp_for_file(file_args['path'], mtime, atime, diff)

    return {'path': path, 'src': src, 'changed': changed, 'diff': diff}


def check_owner_exists(module, owner):
    try:
        uid = int(owner)
        try:
            getpwuid(uid).pw_name
        except KeyError:
            module.warn('failed to look up user with uid %s. Create user up to this point in real play' % uid)
    except ValueError:
        try:
            getpwnam(owner).pw_uid
        except KeyError:
            module.warn('failed to look up user %s. Create user up to this point in real play' % owner)


def check_group_exists(module, group):
    try:
        gid = int(group)
        try:
            getgrgid(gid).gr_name
        except KeyError:
            module.warn('failed to look up group with gid %s. Create group up to this point in real play' % gid)
    except ValueError:
        try:
            getgrnam(group).gr_gid
        except KeyError:
            module.warn('failed to look up group %s. Create group up to this point in real play' % group)


def main():

    global module

    module = AnsibleModule(
        argument_spec=dict(
            _original_basename=dict(type='str'),  # Internal use only, for recursive ops
            path=dict(type='path', required=True),
            state=dict(type='str', choices=['absent', 'directory', 'file', 'hard', 'link', 'touch']),
            src=dict(type='path'),
            # time
            mtime=dict(type='str', aliases=('modification_time',)),
            mtime_format=dict(type='str', default='%Y%m%d%H%M.%S', aliases=('modification_time_format',)),
            atime=dict(type='str', aliases='(access_time',)),
            atime_format=dict(type='str', default='%Y%m%d%H%M.%S', aliases=('access_time_format',)),
            # when links
            force=dict(type='bool', default=False),
            follow=dict(type='bool', default=True),
        ),
        add_file_common_args=True,
        supports_check_mode=True,
    )

    # When we rewrite basic.py, we will do something similar to this on instantiating an AnsibleModule
    sys.excepthook = _ansible_excepthook
    additional_parameter_handling(module.params)
    params = module.params

    path = params['path']
    state = params['state']
    fsotype = params['type']
    force = params['force']
    follow = params['follow']
    src = params['src']

    if module.check_mode and state != 'absent':
        file_args = module.load_file_common_arguments(module.params)
        if file_args['owner']:
            check_owner_exists(module, file_args['owner'])
        if file_args['group']:
            check_group_exists(module, file_args['group'])

    if state == 'absent':
        result = ensure_absent(path, force)
    else:
        if fsotype == 'file':
            result = ensure_file_attributes(path, follow, atime, mtime)
        elif fsotype == 'directory':
            result = ensure_directory(path, follow, atime, mtime)
        elif fsotype == 'link':
            result = ensure_symlink(path, src, follow, force, atime, mtime)
        elif fsotype == 'hard':
            result = ensure_hardlink(path, src, follow, force, atime, mtime)
        else:
            module.fail_json(

    module.exit_json(**result)


if __name__ == '__main__':
    main()
