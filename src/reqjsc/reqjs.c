/* Include Python machinery */
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#if PY_VERSION_HEX < 0x030B0000
#define PyType_GetModuleByDef _PyType_GetModuleByDef
#endif /* PY_VERSION_HEX < 0x030B0000 */

#if PY_VERSION_HEX < 0x030C0000
#include <structmember.h>
#define Py_T_INT       T_INT
#define Py_T_OBJECT_EX T_OBJECT_EX
#define Py_READONLY    READONLY
#endif /* PY_VERSION_HEX < 0x030C0000 */

#if PY_VERSION_HEX >= 0x030D0000 && PY_VERSION_HEX < 0x030E0000
#define PyUnicode_Equal _PyUnicode_Equal
#endif /* PY_VERSION_HEX >= 0x030D0000 && PY_VERSION_HEX < 0x030E0000 */

/* Include quickjs regular expression lib (libregexp) */
#include "cutils.h" /* utf8_encode, get_hi_surrogate, get_lo_surrogate */
#include "libregexp.h"


/* Implementations needed by libregexp */

bool
lre_check_stack_overflow(void *opaque, size_t alloca_size)
{
    return false;
}


int
lre_check_timeout(void *opaque)
{
    return 0;
}


void *
lre_realloc(void *opaque, void *ptr, size_t size)
{
    // Link libregexp memory management function to Python memory functions

    if (ptr == NULL) {
        return PyMem_RawMalloc(size);
    }
    if (size == 0) {
        PyMem_RawFree(ptr);
        return NULL;
    }
    return PyMem_RawRealloc(ptr, size);
}


static struct PyModuleDef reqjs_module;


// Module state
typedef struct {
    PyObject *ReQJSPattern_Type;  // Pattern class
    PyObject *ReQJSMatch_Type;    // Match class
    PyObject *Error_Type;         // Error class
} ReQJS_state;


/* Regex python objects */

// Pattern instance
typedef struct {
    PyObject_HEAD
    uint8_t *byte_code;
    PyObject *pattern;
    PyObject *groupindex;
} ReQJSPattern;


static inline int
_pattern_capture_count(ReQJSPattern *self)
{
    return lre_get_capture_count(self->byte_code);
}


static inline int
_pattern_flags(ReQJSPattern *self)
{
    return lre_get_flags(self->byte_code);
}


static inline const char *
_pattern_groupnames(ReQJSPattern *self)
{
    return lre_get_groupnames(self->byte_code);
}


// Match instance
typedef struct {
    PyObject_VAR_HEAD
    PyObject *re;           // The Pattern
    PyObject *string;       // The python string being matched
    PyObject *utf16_bytes;  // The python bytes object containing UTF-16 data
    uint8_t *string_data;   // The buffer that is exposed to libregexp
    int string_type;        // The type of string
    int pos;                // The character position where searching starts
    int endpos;             // The character position where searching ends
    int adjustment;         // The code point adjustment for UCS4 data
    int unit_endpos;        // The code unit position where searching ends
    int spans[][2];         // The start and end positions of the groups
} ReQJSMatch;


static inline PyObject *
_match_groupindex(ReQJSMatch *self)
{
    return ((ReQJSPattern *)self->re)->groupindex;
}


static uint8_t **
_match_alloc_capture(ReQJSMatch *self)
{
    int alloc_count;

    alloc_count = lre_get_alloc_count(((ReQJSPattern *)self->re)->byte_code);
    if (alloc_count > 0) {
        uint8_t **capture;

        capture = PyMem_RawMalloc(sizeof(capture[0]) * alloc_count);
        if (capture == NULL) {
            return (uint8_t **)PyErr_NoMemory();
        }
        return capture;
    }
    return NULL;
}


static inline int
_match_lre_exec(ReQJSMatch *self, uint8_t **capture)
{
    int buf_type = self->string_type != PyUnicode_1BYTE_KIND;

    return lre_exec(capture, ((ReQJSPattern *)self->re)->byte_code,
                    self->string_data, self->pos + self->adjustment,
                    self->unit_endpos, buf_type, NULL);
}


/* Match implementation */

static int
ReQJSMatch_traverse(PyObject *op, visitproc visit, void *arg)
{
    ReQJSMatch *self = (ReQJSMatch *)op;
    Py_VISIT(self->re);
    Py_VISIT(self->string);
    Py_VISIT(self->utf16_bytes);
    return 0;
}


int
ReQJSMatch_clear(PyObject *self)
{
    ReQJSMatch *obj = (ReQJSMatch *)self;
    Py_CLEAR(obj->re);
    Py_CLEAR(obj->string);
    Py_CLEAR(obj->utf16_bytes);
    return 0;
}


void
ReQJS_dealloc(PyObject *self)
{
#if PY_VERSION_HEX >= 0x030C0000
    PyObject *exc = PyErr_GetRaisedException();
#endif
    PyTypeObject *tp = Py_TYPE(self);

    PyObject_GC_UnTrack(self);
#if PY_VERSION_HEX >= 0x030C0000
    if (tp->tp_clear(self) < 0) {
        PyErr_WriteUnraisable(self);
    }
#else
    tp->tp_clear(self);
#endif

    // Free memory
    tp->tp_free(self);

    // Decrement reference to type
    Py_DECREF(tp);

#if PY_VERSION_HEX >= 0x030C0000
    if (PyErr_Occurred()) {
        PyErr_WriteUnraisable(NULL);
    }
    PyErr_SetRaisedException(exc);
#endif
}


static PyObject *
_match_group_from_span(ReQJSMatch *match, int *span, PyObject *empty)
{
    /* Return the string that makes up a group */
    if (span[0] == -1) {
        return Py_NewRef(empty);
    }
    return PyUnicode_Substring(match->string, span[0], span[1]);
}


static int *
_match_span_from_obj(ReQJSMatch *match, PyObject *py_idx)
{
    /* Converts python group index number or name into group span */
    Py_ssize_t idx;

    if (PyIndex_Check(py_idx)) {
        /* Index is a number */
        idx = PyNumber_AsSsize_t(py_idx, NULL);
    }
    else {
        /* Index is not a number, try to interpret as group name and get
           numeric index from pattern group name dict
        */
        PyObject *groupindex;
        idx = -1;

        groupindex = _match_groupindex(match);
        if (groupindex) {
            PyObject *py_long_idx;

            py_long_idx = PyDict_GetItemWithError(groupindex, py_idx);
            if (py_long_idx) {
                idx = PyLong_AsSsize_t(py_long_idx);
            }
        }
    }

    // bounds checking
    if (idx < 0 || idx >= Py_SIZE(match)) {
        if (!PyErr_Occurred()) {
            PyErr_SetString(PyExc_IndexError, "no such group");
        }
        return NULL;
    }

    return match->spans[idx];
}


static PyObject *
_match_group_from_idx(ReQJSMatch *match, PyObject *idx, PyObject *empty)
{
    /* Get the string that makes up the requested group */
    int *span;

    span = _match_span_from_obj(match, idx);
    if (span == NULL) {
        return NULL;
    }
    return _match_group_from_span(match, span, empty);
}


static PyObject *
ReQJSMatch_group(ReQJSMatch *self, PyObject *const *args, Py_ssize_t nargs)
{
    PyObject *groups;
    Py_ssize_t i;

    if (nargs == 0) {
        /* No args, return the first group, i.e. the full match */
        return _match_group_from_span(self, self->spans[0], Py_None);
    }
    if (nargs == 1) {
        /* Return the requested group content */
        return _match_group_from_idx(self, args[0], Py_None);
    }
    /* Return a tuple of the requested groups */
    groups = PyTuple_New(nargs);
    if (groups == NULL) {
        return NULL;
    }
    for (i = 0; i < nargs; i++) {
        PyObject *group = _match_group_from_idx(self, args[i], Py_None);
        if (group == NULL) {
            Py_DECREF(groups);
            return NULL;
        }
        PyTuple_SET_ITEM(groups, i, group);
    }
    return groups;
}


static PyObject *
ReQJSMatch_getitem(ReQJSMatch *self, PyObject *index)
{
    return _match_group_from_idx(self, index, Py_None);
}


static int *
_match_span(ReQJSMatch *self, PyObject *const *args, Py_ssize_t nargs)
{
    /* Helper function that checks args and returns the requested group span */
    if (nargs == 0) {
        return self->spans[0];
    }
    if (nargs == 1) {
        return _match_span_from_obj(self, args[0]);
    }
    PyErr_SetString(PyExc_ValueError, "Too many arguments");
    return NULL;
}


static inline PyObject *
_match_start_end(ReQJSMatch *self,
                 PyObject *const *args,
                 Py_ssize_t nargs,
                 size_t start_end)
{
    /* Return the start or end index of a group span */
    int *span;

    span = _match_span(self, args, nargs);
    if (span == NULL) {
        return NULL;
    }
    return PyLong_FromLong(span[start_end]);
}


static PyObject *
ReQJSMatch_start(ReQJSMatch *self, PyObject *const *args, Py_ssize_t nargs)
{
    /* Return the start index of the requested group span */
    return _match_start_end(self, args, nargs, 0);
}


static PyObject *
ReQJSMatch_end(ReQJSMatch *self, PyObject *const *args, Py_ssize_t nargs)
{
    /* Return the end index of the requested group span */
    return _match_start_end(self, args, nargs, 1);
}


static PyObject *
ReQJSMatch_span(ReQJSMatch *self, PyObject *const *args, Py_ssize_t nargs)
{
    /* Returns the requested group span as a tuple of python ints */
    int *span;

    span = _match_span(self, args, nargs);
    if (span == NULL) {
        return NULL;
    }
    return Py_BuildValue("ii", span[0], span[1]);
}


static ReQJSMatch *
_match_new(PyTypeObject *defining_class, Py_ssize_t size)
{
    PyTypeObject *MatchType;
    ReQJS_state *state = PyType_GetModuleState(defining_class);
    if (state == NULL) {
        return NULL;
    }

    MatchType = (PyTypeObject *)state->ReQJSMatch_Type;
    return (ReQJSMatch *)MatchType->tp_alloc(MatchType, size);
}


static inline int
get_adjustment(Py_UCS4 *py_data, int from_idx, int to_idx)
{
    int adjustment = 0;
    while (from_idx < to_idx) {
        Py_UCS4 codepoint = py_data[from_idx++];
        if (codepoint > UINT16_MAX) {
            adjustment += 1;
        }
    }
    return adjustment;
}


static int
_match_init_from_args(ReQJSPattern *pattern,
                      ReQJSMatch *match,
                      PyObject *const *args,
                      Py_ssize_t nargs)
{
    Py_ssize_t pos;
    Py_ssize_t endpos;
    Py_ssize_t py_len;

    if (nargs != 3) {
        PyErr_SetString(PyExc_ValueError, "Wrong number of arguments.");
        return -1;
    }

    if (!PyUnicode_Check(args[0])) {
        PyErr_SetString(PyExc_TypeError, "Must be a string");
        return -1;
    }
    match->string = Py_NewRef(args[0]);

    pos = PyNumber_AsSsize_t(args[1], NULL);
    if (pos == -1 && PyErr_Occurred()) {
        return -1;
    }
    endpos = PyNumber_AsSsize_t(args[2], NULL);
    if (endpos == -1 && PyErr_Occurred()) {
        return -1;
    }

    py_len = PyUnicode_GET_LENGTH(match->string);
    PySlice_AdjustIndices(py_len, &pos, &endpos, 1);

    if (pos > INT_MAX) {
        PyErr_SetString(PyExc_ValueError, "pos value too large");
        return -1;
    }
    if (endpos > INT_MAX) {
        PyErr_SetString(PyExc_ValueError, "endpos value too large");
        return -1;
    }

    if (endpos < pos) {
        /* endpos less than start pos: no match */
        return 0;
    }
    match->re = Py_NewRef((PyObject *)pattern);
    match->string_type = PyUnicode_KIND(match->string);
    match->pos = (int)pos;
    match->endpos = (int)endpos;
    if (match->string_type == PyUnicode_4BYTE_KIND) {
        /*  Data consists of a 4 bytes character array. libregexp needs UTF-16
            data and indices that point to the code unit (uint16 array index).
            The indices must be adjusted for surrogate pairs which take up two
            code units.
        */
        Py_UCS4 *py_data;
        Py_ssize_t unit_endpos;

        py_data = PyUnicode_4BYTE_DATA(match->string);

        // get UTF-16 data
        match->utf16_bytes = PyUnicode_AsUTF16String(match->string);
        if (match->utf16_bytes == NULL) {
            return -1;
        }
        match->string_data = (uint8_t *)PyBytes_AS_STRING(match->utf16_bytes)
                             + 2;  // skip BOM

        /* adjust pos for surrogate pairs */
        match->adjustment = get_adjustment(py_data, 0, match->pos);
        if (match->pos > INT_MAX - match->adjustment) {
            PyErr_SetString(PyExc_ValueError, "pos value too large");
            return -1;
        }

        /* adjust end pos for surrogate pairs */
        if (match->endpos == py_len) {
            /* easier than counting special characters*/
            unit_endpos = PyBytes_GET_SIZE(match->utf16_bytes) / 2 - 1;
            if (unit_endpos > INT_MAX) {
                PyErr_SetString(PyExc_ValueError, "endpos value too large");
                return -1;
            }
        }
        else {
            /* count special characters between pos and endpos */
            if (endpos > INT_MAX - match->adjustment) {
                PyErr_SetString(PyExc_ValueError, "endpos value too large");
                return -1;
            }
            unit_endpos = endpos + match->adjustment;
            int adjustment =
                get_adjustment(py_data, match->pos, match->endpos);
            if (unit_endpos > INT_MAX - adjustment) {
                PyErr_SetString(PyExc_ValueError, "endpos value too large");
                return -1;
            }
            unit_endpos += adjustment;
        }
        match->unit_endpos = (int)unit_endpos;
    }
    else {
        /* libregexp can handle both single (Latin1) and double byte (UCS2)
           string data. Just point to internal python buffer */
        match->string_data = PyUnicode_DATA(match->string);
        match->unit_endpos = match->endpos;
    }
    return 0;
}


static int
unit_to_point_idx(ReQJSMatch *match,
                  Py_UCS4 *py_data,
                  int curr_point_idx,
                  int unit_idx)
{
    /* Adjust index by counting the number of non-BMP characters */
    int end_point_idx = unit_idx - match->adjustment;
    while (curr_point_idx < end_point_idx) {
        Py_UCS4 codepoint = py_data[curr_point_idx++];
        if (codepoint > UINT16_MAX) {
            end_point_idx -= 1;
        }
    }
    match->adjustment = unit_idx - end_point_idx;
    return end_point_idx;
}


static void
_match_adjust_spans(ReQJSMatch *match)
{
    /* Convert code unit indices to code point indices */
    int match_size;
    int i;
    int point_idx;
    int *span;
    int *prev_span;
    Py_UCS4 *py_data;

    match_size = (int)Py_SIZE(match);
    point_idx = match->pos;  // current code point (character) index
    prev_span = NULL;
    py_data = PyUnicode_4BYTE_DATA(match->string);

    // Loop through groups
    for (i = 0; i < match_size; i++) {
        span = match->spans[i];
        if (span[0] == -1) {
            // non-contributing group
            continue;
        }
        if (prev_span && (prev_span[1] <= span[0])) {
            // Adjust previous group end if it precedes current start
            point_idx = prev_span[1] =
                unit_to_point_idx(match, py_data, point_idx, prev_span[1]);
        }
        // Adjust current group start
        point_idx = span[0] =
            unit_to_point_idx(match, py_data, point_idx, span[0]);
        prev_span = span;
    }

    // Loop through groups in reverse order and adjust applicable group ends
    for (i -= 1; i >= 0; i--) {
        span = match->spans[i];
        if (span[1] > point_idx) {
            point_idx = span[1] =
                unit_to_point_idx(match, py_data, point_idx, span[1]);
        }
    }
}


static int
_match_exec(ReQJSMatch *match)
{
    /* Really execute a prepared Match object */

    uint8_t **capture = NULL;
    int result;

    if (match->endpos < match->pos) {
        return 0;
    }
    capture = _match_alloc_capture(match);
    if (capture == NULL && PyErr_Occurred()) {
        return -1;
    }
    Py_BEGIN_ALLOW_THREADS;
    result = _match_lre_exec(match, capture);
    Py_END_ALLOW_THREADS;

    if (result == 1) {
        /* Pattern matches */
        int match_size;
        int shift;

        match_size = (int)Py_SIZE(match);
        shift = match->string_type != PyUnicode_1BYTE_KIND;
        if (match_size) {
            // Fill group indices
            for (int i = 0; i < match_size; i++) {
                uint8_t **ptr_span;
                int *span;

                ptr_span = capture + 2 * i;
                span = match->spans[i];

                if (ptr_span[0] && ptr_span[1]) {
                    /* Contributing group, calculate index using pointer
                       arithmetic and adjust byte index for 16 byte character
                       values
                     */
                    span[0] =
                        (int)((ptr_span[0] - match->string_data) >> shift);
                    span[1] =
                        (int)((ptr_span[1] - match->string_data) >> shift);
                }
                else {
                    /* Non-contributing group */
                    span[0] = -1;
                    span[1] = -1;
                }
            }

            if (match->string_type == PyUnicode_4BYTE_KIND) {
                /* libregexp reports code UNIT indices. We need code POINT
                   indices. For non-BMP strings these are not the same, and
                   must be adjusted. */
                _match_adjust_spans(match);
            }
        }
    }
    else if (result != 0) {
        if (result == LRE_RET_MEMORY_ERROR) {
            PyErr_NoMemory();
        }
        else if (result == LRE_RET_TIMEOUT) {
            PyErr_SetString(PyExc_TimeoutError, "Timeout occurred");
        }
        else {
            PyErr_SetString(PyExc_ValueError, "Unknown return code");
        }
    }
    PyMem_RawFree(capture);
    return result;
}


static PyObject *
_match_exec_match(ReQJSMatch *self)
{
    int result = _match_exec(self);
    if (result == 1) {
        // Return the successful Match object
        return Py_NewRef(self);
    }
    if (result == 0) {
        // No match, but also no error. Return None.
        Py_RETURN_NONE;
    }
    return NULL;
}


static PyObject *
ReQJSMatch_next(ReQJSMatch *self,
                PyTypeObject *defining_class,
                PyObject *const *args,
                Py_ssize_t nargs,
                PyObject *kwnames)
{
    /* Get the next match after the current match (self) */
    ReQJSMatch *match;
    PyObject *result;
    int *span;

    if (PyVectorcall_NARGS(nargs) != 0) {
        PyErr_SetString(PyExc_ValueError, "Unexpected argument");
        return NULL;
    }

    // Create new Match
    match = _match_new(defining_class, Py_SIZE(self));
    if (match == NULL) {
        return NULL;
    }

    // Copy state from current Match
    match->re = Py_NewRef(self->re);
    match->string = Py_NewRef(self->string);
    match->utf16_bytes = Py_XNewRef(self->utf16_bytes);
    match->string_data = self->string_data;
    match->string_type = self->string_type;
    match->adjustment = self->adjustment;
    match->endpos = self->endpos;
    match->unit_endpos = self->unit_endpos;

    // Set start position to end of current Match
    span = self->spans[0];
    match->pos = span[1];

    // Increment start if current Match is empty to prevent infinite loop
    if (span[0] == span[1]) {
        match->pos += 1;
        if (match->pos > match->endpos) {
            Py_DECREF(match);
            Py_RETURN_NONE;
        }
        if (match->string_type == PyUnicode_4BYTE_KIND) {
            Py_UCS4 *py_data = PyUnicode_4BYTE_DATA(match->string);
            if (py_data[match->pos - 1] > UINT16_MAX) {
                match->adjustment += 1;
            }
        }
    }

    // And execute the new Match
    result = _match_exec_match(match);
    Py_DECREF(match);
    return result;
}


PyObject *
ReQJSMatch_expand(ReQJSMatch *self, PyObject *args, PyObject *kwargs)
{
    /* Apply string template to match */
    static char *kwlist[] = { "template", NULL };
    PyObject *template;
    PyObject *format_method;
    PyObject *fmt_args = NULL;
    PyObject *fmt_kwargs = NULL;
    PyObject *result = NULL;
    PyObject *empty_str = NULL;
    PyObject *groupindex;
    Py_ssize_t i;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O", kwlist, &template)) {
        return NULL;
    }

    // get template.format method
    format_method = PyObject_GetAttrString(template, "format");
    if (format_method == NULL) {
        return NULL;
    }

    // create args tuple from groups
#if PY_VERSION_HEX < 0x030D0000
    empty_str = PyUnicode_FromStringAndSize("", 0);
    if (empty_str == NULL) {
        goto done;
    }
#else
    empty_str = Py_GetConstant(Py_CONSTANT_EMPTY_STR);
#endif
    fmt_args = PyTuple_New(Py_SIZE(self));
    if (fmt_args == NULL) {
        goto done;
    }
    for (i = 0; i < Py_SIZE(self); i++) {
        PyObject *arg =
            _match_group_from_span(self, self->spans[i], empty_str);
        if (arg == NULL) {
            goto done;
        }
        PyTuple_SET_ITEM(fmt_args, i, arg);
    }

    // create kwargs dict from group names
    groupindex = _match_groupindex(self);
    if (groupindex) {
        PyObject *name, *py_idx;
        Py_ssize_t pos = 0;
        fmt_kwargs = PyDict_New();

        while (PyDict_Next(groupindex, &pos, &name, &py_idx)) {
            Py_ssize_t group_idx = PyLong_AsSsize_t(py_idx);
            if (group_idx == -1 && PyErr_Occurred()) {
                goto done;
            }
            if (PyDict_SetItem(fmt_kwargs, name,
                               PyTuple_GET_ITEM(fmt_args, group_idx))
                < 0) {
                goto done;
            }
        }
    }

    // call template.format(*args, **kwargs)
    result = PyObject_Call(format_method, fmt_args, fmt_kwargs);

done:
    Py_DECREF(format_method);
    Py_XDECREF(empty_str);
    Py_XDECREF(fmt_args);
    Py_XDECREF(fmt_kwargs);
    return result;
}


PyDoc_STRVAR(reqjs_match_doc, "A Match object.");
PyDoc_STRVAR(
    _match_start_doc,
    "Returns the index of the start of the substring matched by `group`; "
    "`group` defaults to zero (meaning the whole matched substring). Return "
    "-1 if group exists but did not contribute to the match.\n\n"
    ":param group: The group index or group name\n"
    ":type group: int | str, optional\n"
    ":raises IndexError: When the group, referred to by index or name, does "
    "    not exist.\n"
    ":return: The start index of the matched substring or -1 for a "
    "    non-contributing group\n"
    ":rtype: int");
PyDoc_STRVAR(
    _match_end_doc,
    "Returns the index of the end of the substring matched by group; group "
    "defaults to zero (meaning the whole matched substring). Return -1 if "
    "group exists but did not contribute to the match.\n\n"
    ":param group: The group index or group name\n"
    ":type group: int | str, optional\n"
    ":raises IndexError: When the group, referred to by index or name, does "
    "    not exist.\n"
    ":return: The end index of the matched substring or -1 for a "
    "    non-contributing group\n"
    ":rtype: int");

static PyMethodDef ReQJSMatch_methods[] = {
    { "group", (PyCFunction)ReQJSMatch_group, METH_FASTCALL, NULL },
    { "start", (PyCFunction)ReQJSMatch_start, METH_FASTCALL,
     _match_start_doc },
    { "end", (PyCFunction)ReQJSMatch_end, METH_FASTCALL, _match_end_doc },
    { "span", (PyCFunction)ReQJSMatch_span, METH_FASTCALL, NULL },
    { "expand", (PyCFunction)ReQJSMatch_expand, METH_VARARGS | METH_KEYWORDS,
     NULL },
    { "_next", (PyCFunction)ReQJSMatch_next,
     METH_METHOD | METH_FASTCALL | METH_KEYWORDS, NULL },
    { NULL, NULL }
};


static PyMemberDef ReQJSMatch_members[] = {
    { "re", Py_T_OBJECT_EX, offsetof(ReQJSMatch, re), Py_READONLY, NULL },
    { "string", Py_T_OBJECT_EX, offsetof(ReQJSMatch, string), Py_READONLY,
     NULL },
    { "pos", Py_T_INT, offsetof(ReQJSMatch, pos), Py_READONLY, NULL },
    { "endpos", Py_T_INT, offsetof(ReQJSMatch, endpos), Py_READONLY, NULL },
    { NULL }
};

static PyType_Slot match_type_slots[] = {
    { Py_tp_doc,       (char *)reqjs_match_doc },
    { Py_tp_traverse,  ReQJSMatch_traverse     },
    { Py_tp_clear,     ReQJSMatch_clear        },
    { Py_tp_dealloc,   ReQJS_dealloc           },
    { Py_tp_methods,   ReQJSMatch_methods      },
    { Py_tp_members,   ReQJSMatch_members      },
    { Py_mp_subscript, ReQJSMatch_getitem      },
    { 0,               0                       }, /* sentinel */
};


static PyType_Spec match_type_spec = {
    .name = "reqjs.Match",
    .basicsize = sizeof(ReQJSMatch),
    .itemsize = sizeof(int[2]),
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_DISALLOW_INSTANTIATION
             | Py_TPFLAGS_HAVE_GC,
    .slots = match_type_slots,
};


static uint8_t *
cesu8_encode(PyObject *str, size_t *buf_len)
{
    /* Encodes a Python string (not checked) into an allocated buffer with the
       CESU-8 variant of UTF-8. The length of the buffer is reported in
       buf_len. The buffer must be deallocated with PyMem_Free.

       Returns NULL with an exception set on error.
    */
    uint8_t *buf;
    size_t _buf_len = 0;
    Py_ssize_t i;
    Py_UCS4 *str_data;
    Py_ssize_t str_length;
    uint8_t *p;

    str_data = PyUnicode_4BYTE_DATA(str);
    str_length = PyUnicode_GET_LENGTH(str);

    // Calculate the required buffer size
    for (i = 0; i < str_length; i++) {
        Py_UCS4 kar = str_data[i];
        size_t inc;

        if (kar < 0x10000) {
            inc = utf8_encode_len(kar);
        }
        else if (kar < 0x110000) {
            // Non-BMP, 3 bytes per surrogate code unit
            inc = 6;
        }
        else {
            PyErr_SetString(PyExc_ValueError, "Invalid character in string");
            return NULL;
        }
        if (_buf_len > SIZE_MAX - inc) {
            PyErr_SetString(PyExc_ValueError, "String too long");
            return NULL;
        }
        _buf_len += inc;
    }

    // allocate the buffer
    if (_buf_len == SIZE_MAX) {
        PyErr_SetString(PyExc_ValueError, "String too long");
        return NULL;
    }
    buf = PyMem_Malloc(_buf_len + 1);
    if (buf == NULL) {
        PyErr_NoMemory();
        return NULL;
    }

    // encode the string into the buffer
    p = buf;
    for (i = 0; i < str_length; i++) {
        Py_UCS4 kar = str_data[i];
        if (kar < 0x10000) {
            // BMP character - regular UTF-8 encode
            p += utf8_encode(p, kar);
        }
        else {
            // Non-BMP character - UTF-8 encode the surrogate pair
            p += utf8_encode(p, get_hi_surrogate(kar));
            p += utf8_encode(p, get_lo_surrogate(kar));
        }
    }
    *p = '\0';  // Add terminating zero

    *buf_len = _buf_len;
    return buf;
}


static PyObject *
ReQJSPattern_new(PyTypeObject *subtype, PyObject *args, PyObject *kwds)
{
    int flags;
    PyObject *pattern_str;
    ReQJSPattern *pattern;
    char error_msg[64];
    const char *buf;
    uint8_t *tmp_buf;
    size_t buf_len;
    const char *group_names;

    if (!PyArg_ParseTuple(args, "Oi", &pattern_str, &flags)) {
        return NULL;
    }
    if (!PyUnicode_Check(pattern_str)) {
        PyErr_SetString(PyExc_TypeError, "Pattern must be a string");
        return NULL;
    }
    flags &= ~LRE_FLAG_NAMED_GROUPS;  // Should not be set by caller

    if ((flags & LRE_FLAG_UNICODE_SETS) && (flags & LRE_FLAG_UNICODE)) {
        PyErr_SetString(PyExc_ValueError, "Invalid regular expression flags");
        return NULL;
    }

    /* Peculiarity of libregexp:

    The pattern to compile must be encoded as a zero terminated UTF-8 string,
    BUT if no unicode flags are set it must be encoded using the
    CESU-8 variant (https://en.wikipedia.org/wiki/CESU-8).

    This is different from regular UTF-8 only for non-BMP characters, i.e. for
    Python strings that are of the 4 byte kind.

    */
    if (PyUnicode_KIND(pattern_str) == PyUnicode_4BYTE_KIND
        && !(flags & (LRE_FLAG_UNICODE | LRE_FLAG_UNICODE_SETS))) {
        // The peculiar case

        tmp_buf = cesu8_encode(pattern_str, &buf_len);
        if (tmp_buf == NULL) {
            return NULL;
        }
        buf = (char *)tmp_buf;
    }
    else {
        // No special treatment required, just use the Python encoder
        buf = PyUnicode_AsUTF8AndSize(pattern_str, (Py_ssize_t *)&buf_len);
        if (buf == NULL) {
            return NULL;
        }
        tmp_buf = NULL;
    }

    // Allocate pattern
    pattern = (ReQJSPattern *)subtype->tp_alloc(subtype, 0);
    if (pattern == NULL) {
        goto error;
    }

    pattern->pattern = Py_NewRef(pattern_str);

    // Compile pattern
    int byte_code_len;
    pattern->byte_code = lre_compile(&byte_code_len, error_msg,
                                     sizeof(error_msg), buf, buf_len, flags,
                                     NULL);
    if (pattern->byte_code == NULL) {
        PyErr_SetString(PyExc_ValueError, error_msg);
        goto error;
    }

    // Get group names
    group_names = _pattern_groupnames(pattern);
    if (group_names) {
        pattern->groupindex = PyDict_New();
        if (pattern->groupindex == NULL) {
            goto error;
        }
        int capture_count = _pattern_capture_count(pattern);
        if (capture_count < 1) {
            PyErr_SetString(PyExc_ValueError, "Invalid capture_count");
            goto error;
        }
        for (int i = 1; i < capture_count; i++) {
            size_t group_len = strlen(group_names);
            if (group_len) {
                PyObject *idx = PyLong_FromLong(i);
                if (idx == NULL) {
                    goto error;
                }
                int success = PyDict_SetItemString(pattern->groupindex,
                                                   group_names, idx);
                Py_DECREF(idx);
                if (success == -1) {
                    goto error;
                }
            }
            group_names += (group_len + LRE_GROUP_NAME_TRAILER_LEN);
        }
    }

    goto done;
error:
    Py_CLEAR(pattern);
done:
    PyMem_Free(tmp_buf);
    return (PyObject *)pattern;
}


static PyObject *
ReQJSPattern_test(ReQJSPattern *self,
                  PyTypeObject *defining_class,
                  PyObject *const *args,
                  Py_ssize_t nargs,
                  PyObject *kwnames)
{
    ReQJSMatch *match;
    int result;

    match = _match_new(defining_class, 0);
    if (match == NULL) {
        return NULL;
    }
    if (_match_init_from_args(self, match, args, PyVectorcall_NARGS(nargs))
        < 0) {
        Py_DECREF(match);
        return NULL;
    }
    result = _match_exec(match);
    Py_DECREF(match);
    if (result == 1) {
        Py_RETURN_TRUE;
    }
    if (result == 0) {
        Py_RETURN_FALSE;
    }
    return NULL;
}


static PyObject *
ReQJSPattern_search(ReQJSPattern *self,
                    PyTypeObject *defining_class,
                    PyObject *const *args,
                    Py_ssize_t nargs,
                    PyObject *kwnames)
{
    ReQJSMatch *match;
    PyObject *result;

    // allocate match
    match = _match_new(defining_class, _pattern_capture_count(self));
    if (match == NULL) {
        return NULL;
    }

    // initialize match from arguments
    if (_match_init_from_args(self, match, args, PyVectorcall_NARGS(nargs))
        < 0) {
        Py_DECREF(match);
        return NULL;
    }

    // execute the match and return the result
    result = _match_exec_match(match);
    Py_DECREF(match);
    return result;
}


static PyObject *
ReQJSPattern_flags(ReQJSPattern *self, void *unused)
{
    return PyLong_FromLong(_pattern_flags(self));
}


static PyObject *
ReQJSPattern_groups(ReQJSPattern *self, void *unused)
{
    return PyLong_FromLong(_pattern_capture_count(self) - 1);
}


static PyObject *
ReQJSPattern_groupindex(ReQJSPattern *self, void *unused)
{
    if (self->groupindex == NULL) {
        return PyDict_New();
    }
    return PyDictProxy_New(self->groupindex);
}


static int
ReQJSPattern_traverse(ReQJSPattern *self, visitproc visit, void *arg)
{
    Py_VISIT(self->pattern);
    Py_VISIT(self->groupindex);
    return 0;
}


int
ReQJSPattern_clear(ReQJSPattern *self)
{
    Py_CLEAR(self->pattern);
    Py_CLEAR(self->groupindex);
    PyMem_RawFree(self->byte_code);
    self->byte_code = NULL;
    return 0;
}


static PyObject *
ReQJSPattern_richcompare(ReQJSPattern *self, PyObject *other_obj, int op)
{
    ReQJSPattern *other;
    int cmp;

    if (op != Py_EQ && op != Py_NE) {
        Py_RETURN_NOTIMPLEMENTED;
    }

    if ((PyObject *)self == other_obj) {
        return PyBool_FromLong(op == Py_EQ);
    }

    PyObject *mod = PyType_GetModuleByDef(Py_TYPE(self), &reqjs_module);
    if (mod == NULL) {
        return NULL;
    }
    ReQJS_state *state = PyModule_GetState(mod);
    if (state == NULL) {
        return NULL;
    }
    if (!PyObject_IsInstance(other_obj, state->ReQJSPattern_Type)) {
        Py_RETURN_NOTIMPLEMENTED;
    }
    other = (ReQJSPattern *)other_obj;

    cmp = _pattern_flags(self) == _pattern_flags(other);

    if (cmp) {
#if PY_VERSION_HEX < 0x030D0000
        int ucmp = PyUnicode_Compare(self->pattern, other->pattern);
        if (ucmp == -1 && PyErr_Occurred()) {
            return NULL;
        }
        cmp = ucmp == 0;
#else
        cmp = PyUnicode_Equal(self->pattern, other->pattern);
        if (cmp == -1) {
            return NULL;
        }
#endif
    }

    if (op == Py_NE) {
        cmp = !cmp;
    }
    return PyBool_FromLong(cmp);
}


static Py_hash_t
ReQJSPattern_hash(ReQJSPattern *self)
{
    Py_hash_t hash = PyObject_Hash(self->pattern);
    if (hash == -1) {
        return -1;
    }
    hash ^= (Py_hash_t)_pattern_flags(self);
    if (hash == -1) {
        hash = -2;
    }
    return hash;
}


static PyMemberDef ReQJSPattern_members[] = {
    { "pattern", Py_T_OBJECT_EX, offsetof(ReQJSPattern, pattern), Py_READONLY,
     NULL },
    { NULL }
};


static PyGetSetDef ReQJSPattern_getset[] = {
    { "flags", (getter)ReQJSPattern_flags, NULL, NULL, NULL },
    { "groups", (getter)ReQJSPattern_groups, NULL, NULL, NULL },
    { "groupindex", (getter)ReQJSPattern_groupindex, NULL, NULL, NULL },
    { NULL }
};


static PyMethodDef ReQJSPattern_methods[] = {
    { "search", (PyCFunction)ReQJSPattern_search,
     METH_METHOD | METH_FASTCALL | METH_KEYWORDS, NULL },
    { "test", (PyCFunction)ReQJSPattern_test,
     METH_METHOD | METH_FASTCALL | METH_KEYWORDS, NULL },
    { NULL }
};


static PyType_Slot pattern_type_slots[] = {
    { Py_tp_doc, PyDoc_STR("Compiled regular expression object.") },
    { Py_tp_new, ReQJSPattern_new },
    { Py_tp_members, ReQJSPattern_members },
    { Py_tp_getset, ReQJSPattern_getset },
    { Py_tp_methods, ReQJSPattern_methods },
    { Py_tp_richcompare, ReQJSPattern_richcompare },
    { Py_tp_hash, ReQJSPattern_hash },
    { Py_tp_traverse, ReQJSPattern_traverse },
    { Py_tp_clear, ReQJSPattern_clear },
    { Py_tp_dealloc, ReQJS_dealloc },
    { 0 },
};


static PyType_Spec pattern_type_spec = {
    .name = "reqjs.Pattern",
    .basicsize = sizeof(ReQJSPattern),
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC | Py_TPFLAGS_BASETYPE,
    .slots = pattern_type_slots,
};


/* Module implementation */

static int
reqjs_mod_exec(PyObject *m)
{
    ReQJS_state *state = PyModule_GetState(m);

    state->Error_Type = PyErr_NewException("reqjs.PatternError", NULL, NULL);
    if (state->Error_Type == NULL) {
        return -1;
    }
    if (PyModule_AddType(m, (PyTypeObject *)state->Error_Type) < 0) {
        return -1;
    }

    state->ReQJSPattern_Type =
        PyType_FromModuleAndSpec(m, &pattern_type_spec, NULL);
    if (state->ReQJSPattern_Type == NULL) {
        return -1;
    }
    if (PyModule_AddType(m, (PyTypeObject *)state->ReQJSPattern_Type) < 0) {
        return -1;
    }
    state->ReQJSMatch_Type =
        PyType_FromModuleAndSpec(m, &match_type_spec, NULL);
    if (state->ReQJSMatch_Type == NULL) {
        return -1;
    }
    if (PyModule_AddType(m, (PyTypeObject *)state->ReQJSMatch_Type) < 0) {
        return -1;
    }

    if (PyModule_AddIntConstant(m, "IGNORECASE", LRE_FLAG_IGNORECASE) < 0) {
        return -1;
    }
    if (PyModule_AddIntConstant(m, "MULTILINE", LRE_FLAG_MULTILINE) < 0) {
        return -1;
    }
    if (PyModule_AddIntConstant(m, "DOTALL", LRE_FLAG_DOTALL) < 0) {
        return -1;
    }
    if (PyModule_AddIntConstant(m, "UNICODE", LRE_FLAG_UNICODE) < 0) {
        return -1;
    }
    if (PyModule_AddIntConstant(m, "STICKY", LRE_FLAG_STICKY) < 0) {
        return -1;
    }
    if (PyModule_AddIntConstant(m, "NAMED_GROUPS", LRE_FLAG_NAMED_GROUPS)
        < 0) {
        return -1;
    }
    if (PyModule_AddIntConstant(m, "UNICODE_SETS", LRE_FLAG_UNICODE_SETS)
        < 0) {
        return -1;
    }
    return 0;
}


static int
reqjs_traverse(PyObject *module, visitproc visit, void *arg)
{
    ReQJS_state *state = PyModule_GetState(module);
    Py_VISIT(state->Error_Type);
    Py_VISIT(state->ReQJSPattern_Type);
    return 0;
}


static int
reqjs_clear(PyObject *module)
{
    ReQJS_state *state = PyModule_GetState(module);
    Py_CLEAR(state->Error_Type);
    Py_CLEAR(state->ReQJSPattern_Type);
    return 0;
}


static void
reqjs_free(void *module)
{
    reqjs_clear((PyObject *)module);
}


static PyModuleDef_Slot reqjs_slots[] = {
    { Py_mod_exec, reqjs_mod_exec },
    { 0,           NULL           }
};


PyDoc_STRVAR(
    reqjs_doc,
    "A python module that exposes the QuickJS regular expression engine.");


static struct PyModuleDef reqjs_module = {
    PyModuleDef_HEAD_INIT,  .m_name = "reqjs._reqjs",
    .m_doc = reqjs_doc,     .m_size = sizeof(ReQJS_state),
    .m_slots = reqjs_slots, .m_traverse = reqjs_traverse,
    .m_clear = reqjs_clear, .m_free = reqjs_free
};


PyMODINIT_FUNC
PyInit__reqjs(void)
{
    return PyModuleDef_Init(&reqjs_module);
}
