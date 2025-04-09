# -*- coding: utf-8 -*-
# Copyright: (c) Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations


class ModuleDocFragment(object):

    DOCUMENTATION = r'''
options:
  checksum_algorithm:
    description:
      - Algorithm to use when determining checksums for a file.
      - The remote host has to support the hashing method specified, V(md5)
        can be unavailable if the host is FIPS-140 compliant.
      - If the host is unable to use specified algorithm, an error will occur.
      - Default changed to O(sha256) in version '2.18'.
    type: str
    choices: [ md5, sha1, sha224, sha256, sha384, sha512 ]
    default: sha256
    aliases: [ hashing ]
'''
