# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

from gaffer.gafferd.pbkdf2 import pbkdf2_hex


def test_pbkdf2():

    def check(data, salt, iterations, keylen, expected):
        rv = pbkdf2_hex(data, salt, iterations, keylen)
        err_msg = """Test Failed:
        Expected:   %(expected)s
        Got:        %(rv)s
        Parameters:'
            data=%(data)s
            salt=%(salt)s
            iterations=%(iterations)s""" % {"expected": expected,
                    "rv": rv, "data": data, "salt": salt,
                    "iterations": iterations}

        assert rv == expected, err_msg

    # From RFC 6070
    check(b'password', b'salt', 1, 20,
          b'0c60c80f961f0e71f3a9b524af6012062fe037a6')
    check(b'password', b'salt', 2, 20,
          b'ea6c014dc72d6f8ccd1ed92ace1d41f0d8de8957')
    check(b'password', b'salt', 4096, 20,
          b'4b007901b765489abead49d926f721d065a429c1')
    check(b'passwordPASSWORDpassword', b'saltSALTsaltSALTsaltSALTsaltSALTsalt',
          4096, 25, b'3d2eec4fe41c849b80c8d83662c0e44a8b291a964cf2f07038')
    check(b'pass\x00word', b'sa\x00lt', 4096, 16,
          b'56fa6aa75548099dcc37d7f03425e0c3')
    # This one is from the RFC but it just takes for ages
    ##check('password', 'salt', 16777216, 20,
    ##      'eefe3d61cd4da4e4e9945b3d6ba2158c2634e984')

    # From Crypt-PBKDF2
    check(b'password', b'ATHENA.MIT.EDUraeburn', 1, 16,
          b'cdedb5281bb2f801565a1122b2563515')
    check(b'password', b'ATHENA.MIT.EDUraeburn', 1, 32,
          b'cdedb5281bb2f801565a1122b25635150ad1f7a04bb9f3a333ecc0e2e1f70837')
    check(b'password', b'ATHENA.MIT.EDUraeburn', 2, 16,
          b'01dbee7f4a9e243e988b62c73cda935d')
    check(b'password', b'ATHENA.MIT.EDUraeburn', 2, 32,
          b'01dbee7f4a9e243e988b62c73cda935da05378b93244ec8f48a99e61ad799d86')
    check(b'password', b'ATHENA.MIT.EDUraeburn', 1200, 32,
          b'5c08eb61fdf71e4e4ec3cf6ba1f5512ba7e52ddbc5e5142f708a31e2e62b1e13')
    check(b'X' * 64, b'pass phrase equals block size', 1200, 32,
          b'139c30c0966bc32ba55fdbf212530ac9c5ec59f1a452f5cc9ad940fea0598ed1')
    check(b'X' * 65, b'pass phrase exceeds block size', 1200, 32,
          b'9ccad6d468770cd51b10e6a68721be611a8b4d282601db3b36be9246915ec82a')
