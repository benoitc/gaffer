# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import os
import six



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
            raise ctypes.WinError(_ERROR_INSUFFICIENT_BUFFER)
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
            temp = os.listdir(os.sep.join([os.environ.get('SystemRoot',
                'C:\windows'),'temp']))
        except:
            return False
        return True

    def default_path():
        userprofile = os.environ.get('USERPROFILE')
        if userprofile:
            return os.path.join(userprofile, '.gaffer')
        return os.path.join(os.path.expanduser('~'), '.gaffer')
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
                return os.path.join(local_etc, etc)
            return os.path.join("usr", "local", "etc", "gaffer")

        # if not root, use the user path
        return os.path.join(os.path.expanduser('~'), '.gaffer')
