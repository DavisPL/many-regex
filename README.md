# Many Regex

Run a regex on tons of different libraries.

## Tentative Results

<img width="3947" height="2950" alt="regex_benchmark_comparison" src="https://github.com/user-attachments/assets/09dbd171-e07f-4d9f-add2-d89f2f86d2b3" />

<img width="4760" height="2993" alt="regex_benchmark_line_chart" src="https://github.com/user-attachments/assets/b38cc7e2-e5fc-460f-bf4f-613f2663e779" />

### Issue with [re2](https://pypi.org/project/re2/)

```
            |         |
            |         PyObject* {aka _object*}
      src/re2.cpp:15568:25: error: too few arguments to function ‘PyCodeObject* PyCode_New(int, int, int, int, int, PyObject*, PyObject*, PyObject*, PyObject*, PyObject*, PyObject*, PyObject*, PyObject*, PyObject*, int, PyObject*, PyObject*)’
      15568 |     py_code = PyCode_New(
            |               ~~~~~~~~~~^
      15569 |         0,            /*int argcount,*/
            |         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      15570 |         #if PY_MAJOR_VERSION >= 3
            |         ~~~~~~~~~~~~~~~~~~~~~~~~~
      15571 |         0,            /*int kwonlyargcount,*/
            |         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      15572 |         #endif
            |         ~~~~~~
      15573 |         0,            /*int nlocals,*/
            |         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      15574 |         0,            /*int stacksize,*/
            |         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      15575 |         0,            /*int flags,*/
            |         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      15576 |         __pyx_empty_bytes, /*PyObject *code,*/
            |         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      15577 |         __pyx_empty_tuple,  /*PyObject *consts,*/
            |         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      15578 |         __pyx_empty_tuple,  /*PyObject *names,*/
            |         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      15579 |         __pyx_empty_tuple,  /*PyObject *varnames,*/
            |         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      15580 |         __pyx_empty_tuple,  /*PyObject *freevars,*/
            |         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      15581 |         __pyx_empty_tuple,  /*PyObject *cellvars,*/
            |         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      15582 |         py_srcfile,   /*PyObject *filename,*/
            |         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      15583 |         py_funcname,  /*PyObject *name,*/
            |         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      15584 |         __pyx_lineno,   /*int firstlineno,*/
            |         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      15585 |         __pyx_empty_bytes  /*PyObject *lnotab*/
            |         ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
      15586 |     );
            |     ~
      /usr/include/python3.13/cpython/code.h:213:1: note: declared here
        213 | PyCode_New(
            | ^~~~~~~~~~
      src/re2.cpp:15595:13: error: invalid use of incomplete type ‘PyFrameObject’ {aka ‘struct _frame’}
      15595 |     py_frame->f_lineno = __pyx_lineno;
            |             ^~
      In file included from /usr/include/python3.13/Python.h:68:
      /usr/include/python3.13/pytypedefs.h:22:16: note: forward declaration of ‘PyFrameObject’ {aka ‘struct _frame’}
         22 | typedef struct _frame PyFrameObject;
            |                ^~~~~~
      error: command '/usr/bin/g++' failed with exit code 1
      [end of output]

  note: This error originates from a subprocess, and is likely not a problem with pip.
  ERROR: Failed building wheel for re2
Failed to build re2
error: failed-wheel-build-for-install

× Failed to build installable wheels for some pyproject.toml based projects
╰─> re2
(venv) many-regex (main) λ
```
