"""Small lossless-value S-expression reader for the checked-in KiCad sources."""
import json
import re


class Quoted(str):
    pass


def parse(text):
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', text)
    stack = []
    result = None
    for token in tokens:
        if token == '(':
            item = []
            if stack:
                stack[-1].append(item)
            stack.append(item)
        elif token == ')':
            result = stack.pop()
        else:
            stack[-1].append(Quoted(json.loads(token)) if token.startswith('"') else token)
    if stack or result is None:
        raise ValueError('Unbalanced S-expression')
    return result


def dump(item, level=0):
    if not isinstance(item, list):
        return json.dumps(str(item), ensure_ascii=False) if isinstance(item, Quoted) else str(item)
    if all(not isinstance(v, list) for v in item):
        return '(' + ' '.join(dump(v) for v in item) + ')'
    parts = []
    for v in item:
        if isinstance(v, list):
            parts.append('\n' + '  ' * (level + 1) + dump(v, level + 1))
        else:
            parts.append((' ' if parts else '') + dump(v))
    return '(' + ''.join(parts) + ')'


def children(node, tag):
    return [v for v in node if isinstance(v, list) and v and v[0] == tag]


def child(node, tag):
    values = children(node, tag)
    return values[0] if values else None


def prop(node, key):
    return next((p for p in children(node, 'property') if p[1] == key), None)


def walk(node):
    if isinstance(node, list):
        yield node
        for value in node:
            yield from walk(value)
