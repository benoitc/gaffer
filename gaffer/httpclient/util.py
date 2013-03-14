# -*- coding: utf-8 -
#
# This file is part of gaffer. See the NOTICE for more information.

import six

from ..util import quote, quote_plus

def url_quote(s, charset='utf-8', safe='/:'):
    """URL encode a single string with a given encoding."""
    if isinstance(s, six.text_type):
        s = s.encode(charset)
    elif not isinstance(s, str):
        s = str(s)
    return quote(s, safe=safe)


def url_encode(obj, charset="utf8", encode_keys=False):
    items = []
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            items.append((k, v))
    else:
        items = list(items)

    tmp = []
    for k, v in items:
        if encode_keys:
            k = encode(k, charset)

        if not isinstance(v, (tuple, list)):
            v = [v]

        for v1 in v:
            if v1 is None:
                v1 = ''
            elif six.callable(v1):
                v1 = encode(v1(), charset)
            else:
                v1 = encode(v1, charset)
            tmp.append('%s=%s' % (quote(k), quote_plus(v1)))
    return '&'.join(tmp)

def encode(v, charset="utf8"):
    if isinstance(v, six.text_type):
        v = v.encode(charset)
    else:
        v = str(v)
    return v


def make_uri(base, *args, **kwargs):
    """Assemble a uri based on a base, any number of path segments,
    and query string parameters.

    """

    # get encoding parameters
    charset = kwargs.pop("charset", "utf-8")
    safe = kwargs.pop("safe", "/:")
    encode_keys = kwargs.pop("encode_keys", True)

    base_trailing_slash = False
    if base and base.endswith("/"):
        base_trailing_slash = True
        base = base[:-1]
    retval = [base]

    # build the path
    _path = []
    trailing_slash = False
    for s in args:
        if s is not None and isinstance(s, six.string_types):
            if len(s) > 1 and s.endswith('/'):
                trailing_slash = True
            else:
                trailing_slash = False
            _path.append(url_quote(s.strip('/'), charset, safe))

    path_str =""
    if _path:
        path_str = "/".join([''] + _path)
        if trailing_slash:
            path_str = path_str + "/"
    elif base_trailing_slash:
        path_str = path_str + "/"

    if path_str:
        retval.append(path_str)

    params_str = url_encode(kwargs, charset, encode_keys)
    if params_str:
        retval.extend(['?', params_str])

    return ''.join(retval)
