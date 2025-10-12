# Many Regex

Run a regex on tons of different libraries.

## Roadmap

- [ ] include JavaScript / TypeScript libraries
- [ ] include Go libraries
- [ ] include Rust libraries
- [x] Vary input size and not just input pattern
- [x] Make table of Regex libraries

## Tests

Each Regex pattern was run with an input size of 0 to 30 on all 4 of the tested Regex libraries.

<img width="3560" height="2063" alt="test_4_performance" src="https://github.com/user-attachments/assets/b60917b1-aa53-447a-a316-55182d26ed6b" />

Here is an example of one of the tests.

1. [Nested quantifiers (`^(a+)+$`)](images/test_1_performance.png)
2. [Nested quantifiers with Kleene star (`^(a*)*$`)](images/test_2_performance.png)
3. [Nested quantifiers with mismatch (`^(a+)+b$`)](images/test_3_performance.png)
4. [Alternation with overlapping patterns (`^(a|a)*$`)](images/test_4_performance.png)
5. [Alternation with prefix overlap (`^(a|ab)*$`)](images/test_5_performance.png)
6. [Multiple alternations (`(a|a|a|a|a|b)*c`)](images/test_6_performance.png)
7. [Triple nested groups (`^((a+)+)+$`)](images/test_7_performance.png)
8. [Nested Kleene star with suffix (`^(a*)*b$`)](images/test_8_performance.png)
9. [Nested plus with suffix (`^(a+)*b$`)](images/test_9_performance.png)
10. [Email-like pattern (ReDoS)](images/test_10_performance.png)
11. [Overlapping character classes lowercase (`^([a-z]+)+[A-Z]$`)](images/test_11_performance.png)
12. [Overlapping character classes alphanumeric (`^([0-9a-z]+)+[A-Z]$`)](images/test_12_performance.png)
13. [Wildcard nested quantifiers (`^(.*)*$`)](images/test_13_performance.png)
14. [Wildcard plus nested (`^(.+)+$`)](images/test_14_performance.png)
15. [Wildcard with suffix (`^(.*)+b$`)](images/test_15_performance.png)
16. [Multiple overlapping quantifiers (`^(a*)+b$`)](images/test_16_performance.png)
17. [Optional nested quantifiers (`^(a?)+b$`)](images/test_17_performance.png)
18. [Non-greedy nested quantifiers (`^(a*?)*b$`)](images/test_18_performance.png)
19. [Word boundary catastrophic (`^(\\w+\\s*)+$`)](images/test_19_performance.png)
20. [Word with spaces pattern (`^([\\w]+[\\s]*)*$`)](images/test_20_performance.png)
21. [Digit nested plus (`^(\\d+)+$`)](images/test_21_performance.png)
22. [Digit nested star (`^([0-9]+)*$`)](images/test_22_performance.png)
23. [Complex alternation plus (`^(a+|a+)+$`)](images/test_23_performance.png)
24. [Complex alternation star (`^(a*|a*)*$`)](images/test_24_performance.png)
25. [Alternation with length variation (`^(aa+|a+)+$`)](images/test_25_performance.png)
26. [URL pattern (simplified)](images/test_26_performance.png)
27. [Whitespace with letters (`^(\\s*a+\\s*)+$`)](images/test_27_performance.png)
28. [Whitespace alternation (`^(\\s+|a+)*b$`)](images/test_28_performance.png)
29. [Optional group patterns (`^(a+)?b?(a+)?$`)](images/test_29_performance.png)
30. [Optional with nested groups (`^(a+b?)+c$`)](images/test_30_performance.png)
31. [Character class repetition (`^([a-zA-Z]+)*$`)](images/test_31_performance.png)
32. [Alphanumeric with symbol (`^([a-z0-9]+)+[!]$`)](images/test_32_performance.png)
33. [Nested alternation simple (`^((a|b)+)+c$`)](images/test_33_performance.png)
34. [Nested alternation overlap (`^((a|ab)+)+c$`)](images/test_34_performance.png)
35. [Long repeating with suffix (`^(a+b)+c$`)](images/test_35_performance.png)
36. [Repeating pattern variation (`^(ab+)+c$`)](images/test_36_performance.png)

## Libraries

| Name  | Language | Claimed to be linear                         | Found to be harmful |
| ---   | --       | --                                           | --                  |
| Re    | Python   | No                                           | Yes                 |
| Rure  | Python   | Yes "guarantees linear time"                 | No                  |
| Regex | Python   | Reduces backtracking chance but no guarantee | Yes                 |
| Pyre2 | Python   | Yes "guarantees linear-time behavior"        | No                  |


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
