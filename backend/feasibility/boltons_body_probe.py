"""Free check (no model, no sandbox): the boltons #301 patch extracts a function body by parsing source lines.
This runs that exact logic on four functions to show where it breaks. Run: python -m feasibility.boltons_body_probe"""

import inspect, textwrap

def extract(func):  # the patch's logic, verbatim
    source_lines = inspect.getsource(func).splitlines()
    body_lines = []
    in_function = False
    for line in source_lines:
        if line.strip().startswith('def ') or line.strip().startswith('lambda ') or line.strip().startswith('class '):
            in_function = True
            continue
        if in_function:
            if line.strip() and not line.startswith(' '):
                break
            body_lines.append(line.rstrip())
    return '\n'.join(body_lines)

def simple(a, b=2):
    return a / b

def multiline_signature(
    a,
    b=2,
):
    return a / b

def nested(a):
    def inner(x):
        return x + 1
    return inner(a)

def with_class(a):
    class K:
        v = 1
    return a + K.v

def run(f):  # compiles the extracted body the way FunctionBuilder would
    try:
        body = extract(f)
        code = "def g(*args, **kw):\n" + textwrap.indent(textwrap.dedent(body), "    ") if body.strip() else None
        ns = {}
        exec(compile(code, "<t>", "exec"), ns)
        return ("compiles", body.replace("\n", " | ")[:70])
    except Exception as e:
        return ("FAILS", type(e).__name__, str(e)[:60])

if __name__ == "__main__":
  for f in (simple, multiline_signature, nested, with_class):
    print(f.__name__, run(f))
