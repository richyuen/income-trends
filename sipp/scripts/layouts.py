"""Fixed-width layout parsers for SIPP 1996-2008 dictionaries.

Census dictionaries (2001-2008 core, longitudinal-weight files): lines "D NAME width position".
NBER Stata dictionaries (1996 core, sip96l1.dct): lines "_column(pos) type name %Wf".
Both return {NAME: (start0, width)}.
"""
import re


def census_layout(path, names=None):
    pos = {}
    for line in open(path, encoding="latin-1"):
        m = re.match(r"^D (\S+)\s+(\d+)\s+(\d+)", line)
        if m and m.group(1) not in pos and (names is None or m.group(1) in names):
            pos[m.group(1)] = (int(m.group(3)) - 1, int(m.group(2)))
    return pos


def nber_layout(path, names=None):
    pos = {}
    for line in open(path, encoding="latin-1"):
        m = re.match(r"^\s*_column\(\s*(\d+)\s*\)\s+\S+\s+(\S+)\s+%(\d+)", line)
        if m:
            n = m.group(2).upper()
            if n not in pos and (names is None or n in names):
                pos[n] = (int(m.group(1)) - 1, int(m.group(3)))
    return pos
