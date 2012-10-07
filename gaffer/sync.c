/* -*- coding: utf-8 -
 *
 * This file is part of gaffer. See the NOTICE for more information. */

#include <pthread.h>
#if defined( __ia64__ ) && defined( __INTEL_COMPILER )
# include <ia64intrin.h>
#endif
#include <stdio.h>

#include "Python.h"

struct module_state {
    PyObject *error;
};

#if PY_MAJOR_VERSION >= 3
#define GETSTATE(m) ((struct module_state*)PyModule_GetState(m))
#else
#define GETSTATE(m) (&_state)
static struct module_state _state;
#endif

static
PyObject* compare_and_swap(PyObject *self, PyObject *args)
{
    int oldval, newval, r;
    if (!PyArg_ParseTuple(args, "ii", &oldval, &newval))
        return NULL;
    r = __sync_bool_compare_and_swap(&oldval, oldval, newval);

    return Py_BuildValue("i", oldval);
}

static
PyObject* increment(PyObject *self, PyObject *args)
{
    int val;
    if (!PyArg_ParseTuple(args, "i", &val))
	    return NULL;

    return  Py_BuildValue("i", __sync_add_and_fetch(&val, 1));
}

static
PyObject* decrement(PyObject *self, PyObject *args)
{
    int val;
    if (!PyArg_ParseTuple(args, "i", &val))
	    return NULL;

    return Py_BuildValue("i", __sync_sub_and_fetch(&val, 1));
}

static
PyObject* add(PyObject *self, PyObject *args)
{
    int val, inc;
    if (!PyArg_ParseTuple(args, "ii", &val, &inc))
	    return NULL;

    return  Py_BuildValue("i", __sync_add_and_fetch(&val, inc));
}

static
PyObject* sub(PyObject *self, PyObject *args)
{
    int val, inc;
    if (!PyArg_ParseTuple(args, "ii", &val, &inc))
	    return NULL;

    return Py_BuildValue("i", __sync_sub_and_fetch(&val, inc));
}



static
PyObject* atomic_read(PyObject *self, PyObject *args)
{
    int val;
    if (!PyArg_ParseTuple(args, "i", &val))
	    return NULL;

    return Py_BuildValue("i", __sync_add_and_fetch(&val, 0));
}


static PyMethodDef
sync_methods[] = {
    {"compare_and_swap", compare_and_swap, METH_VARARGS,
        "Atomically compare and swap 2 integers"},
    {"increment", increment, METH_VARARGS, "Atomically increment an integer"},
    {"decrement", decrement, METH_VARARGS, "Atomically decrement an integer"},
    {"add", add, METH_VARARGS, "Atomically increment an integer with a value"},
    {"sub", sub, METH_VARARGS, "Atomically decrement an integer with a value"},
    {"atomic_read", atomic_read, METH_VARARGS, "Atomically read an integer"},
    {NULL, NULL, 0, NULL}
};

#if PY_MAJOR_VERSION >= 3

static int sync_traverse(PyObject *m, visitproc visit, void *arg) {
    Py_VISIT(GETSTATE(m)->error);
    return 0;
}

static int sync_clear(PyObject *m) {
    Py_CLEAR(GETSTATE(m)->error);
    return 0;
}


static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "sync",
        NULL,
        sizeof(struct module_state),
        sync_methods,
        NULL,
        sync_traverse,
        sync_clear,
        NULL
};

#define INITERROR return NULL

PyObject *
PyInit_sync(void)

#else
#define INITERROR return

void
initsync(void)
#endif
{
#if PY_MAJOR_VERSION >= 3
    PyObject *module = PyModule_Create(&moduledef);
#else
    PyObject *module = Py_InitModule("sync", sync_methods);
#endif

    if (module == NULL)
        INITERROR;
    struct module_state *st = GETSTATE(module);

    st->error = PyErr_NewException("sync.Error", NULL, NULL);
    if (st->error == NULL) {
        Py_DECREF(module);
        INITERROR;
    }

#if PY_MAJOR_VERSION >= 3
    return module;
#endif
}
