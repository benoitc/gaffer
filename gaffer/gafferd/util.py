# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

try:
    input = raw_input
except NameError:
    pass

from importlib import import_module
import os
import sys

if os.name == 'nt':
    import ctypes
    import _winreg

    _kernel32 = ctypes.windll.kernel32

    def executablepath():
        '''return full path of hg.exe'''
        size = 600
        buf = ctypes.create_string_buffer(size + 1)
        len = _kernel32.GetModuleFileNameA(None, ctypes.byref(buf), size)
        if len == 0:
            raise ctypes.WinError
        elif len == size:
            raise ctypes.WinError(122)
        return buf.value

    def system_path():
        # look for a system rcpath in the registry
        path = [_winreg.QueryValueEx(_winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,
            'SOFTWARE\\Gaffer'), None)[0].replace('/', '\\')]
        path.append(os.path.dirname(executablepath()))
        return path

    def user_path():
        home = os.path.expanduser('~')
        path = [os.path.join(home, '.gaffer'),]
        userprofile = os.environ.get('USERPROFILE')
        if userprofile:
            path.append(os.path.join(userprofile, '.gaffer'))
        return path

    def is_admin():
        try:
            # only windows users with admin privileges
            # can read the C:\windows\temp
            os.listdir(os.sep.join([os.environ.get('SystemRoot', 'C:\windows'),
                'temp']))
        except:
            return False
        return True

    def default_path():
        userprofile = os.environ.get('USERPROFILE')
        if userprofile:
            return os.path.join(userprofile, '.gaffer')
        return os.path.join(os.path.expanduser('~'), '.gaffer')

    default_user_path = default_path
else:
    def system_path():
        here = os.path.dirname(os.path.dirname(sys.argv[0]))
        return [os.path.join(here, 'etc', 'gaffer'),
                '/etc/gaffer']

    def user_path():
        home = os.path.expanduser('~')
        return [os.path.join(home, '.gaffer'),]

    def is_admin():
        if os.geteuid() == 0:
            return True
        return False

    def default_path():
        if is_admin():
            # if the user is an admin, first test if the program name root has
            # the etc folder. If not fallback to /usr/local/etc/gaffer.
            local_etc = os.path.join(os.path.dirname(os.path.dirname(
                sys.argv[0])), "etc")
            if os.path.isdir(local_etc):
                return os.path.join(local_etc, "gaffer")
            return os.path.join("usr", "local", "etc", "gaffer")

        # if not root, use the user path
        return os.path.join(os.path.expanduser('~'), '.gaffer')

    def default_user_path():
        return os.path.join(os.path.expanduser('~'), '.gaffer')


def load_backend(backend_name):
    """ load pool backend. If this is an external module it should be
    passed as "somelib.backend_mod".

    """
    try:
        if len(backend_name.split(".")) > 1:
            mod = import_module(backend_name)
        elif backend_name == "sqlite":
            mod = import_module("gaffer.gafferd.auth.SqliteAuthHandler")
        return mod
    except ImportError:
        error_msg = "%s isn't a socketpool backend" % backend_name
        raise ImportError(error_msg)

def confirm(prompt, resp=True):
    if resp:
        prompt = '%s [%s]|%s: ' % (prompt, 'y', 'n')
    else:
        prompt = '%s [%s]|%s: ' % (prompt, 'n', 'y')

    while True:
        ret = input(prompt).lower()
        if not ret:
            return resp

        if ret not in ('y', 'n'):
            print('please enter y or n.')
            continue

        if ret == "y":
            return True

        return False
