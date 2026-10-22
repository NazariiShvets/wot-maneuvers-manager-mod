# -*- coding: utf-8 -*-
"""Compile gettext .po catalogs under a directory into sibling .mo files."""
import os
import struct
import sys


def _unescape(value):
    return (
        value.replace('\\n', '\n')
        .replace('\\t', '\t')
        .replace('\\"', '"')
        .replace('\\\\', '\\')
    )


def parse_po(text):
    messages = {}
    msgid = None
    msgstr = None
    mode = None

    def finish():
        if msgid is not None and msgstr is not None:
            messages[msgid] = msgstr

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('msgid '):
            finish()
            msgid = _unescape(line[len('msgid '):].strip()[1:-1])
            msgstr = None
            mode = 'id'
        elif line.startswith('msgstr '):
            msgstr = _unescape(line[len('msgstr '):].strip()[1:-1])
            mode = 'str'
        elif line.startswith('"') and line.endswith('"'):
            chunk = _unescape(line[1:-1])
            if mode == 'id':
                msgid += chunk
            elif mode == 'str':
                msgstr += chunk
        else:
            raise ValueError('unsupported po line: %s' % raw)
    finish()
    if '' not in messages:
        raise ValueError('po catalog is missing the empty msgid header')
    return messages


def write_mo(path, messages):
    items = sorted(messages.items())
    ids = [item[0].encode('utf-8') for item in items]
    strs = [item[1].encode('utf-8') for item in items]
    count = len(items)
    key_start = 7 * 4
    val_start = key_start + count * 8
    body_start = val_start + count * 8
    output = []
    output.append(struct.pack('<7I', 0x950412DE, 0, count, key_start, val_start, 0, 0))
    offset = body_start
    key_table = []
    for text in ids:
        key_table.append(struct.pack('<II', len(text), offset))
        offset += len(text) + 1
    val_table = []
    for text in strs:
        val_table.append(struct.pack('<II', len(text), offset))
        offset += len(text) + 1
    output.extend(key_table)
    output.extend(val_table)
    for text in ids:
        output.append(text + b'\x00')
    for text in strs:
        output.append(text + b'\x00')
    with open(path, 'wb') as handle:
        handle.write(b''.join(output))


def main():
    root = sys.argv[1]
    wrote = 0
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if not name.endswith('.po'):
                continue
            source = os.path.join(dirpath, name)
            with open(source, 'r', encoding='utf-8') as handle:
                messages = parse_po(handle.read())
            target = source[:-3] + '.mo'
            write_mo(target, messages)
            wrote += 1
            print('compiled %s (%d messages)' % (target, len(messages)))
    if wrote == 0:
        print('no po catalogs under %s' % root)
    return 0


if __name__ == '__main__':
    sys.exit(main())
