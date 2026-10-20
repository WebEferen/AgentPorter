import sys
rust={}
for line in open(sys.argv[1]):
    u,l,up=line.rstrip("\n").split("\t"); rust[int(u,16)]=(l,up)
h=lambda s:",".join(f"{ord(c):x}" for c in s)
low,upp=[],[]
for u in range(0x110000):
    if 0xD800<=u<=0xDFFF: continue
    c=chr(u); rl,ru=rust.get(u,(f"{u:x}",f"{u:x}"))
    if h(c.lower())!=rl: low.append((u,c.lower()))
    if h(c.upper())!=ru: upp.append((u,c.upper()))
def rs(rows):
    return "\n".join("    ('\\u{%x}', \"%s\")," % (u, "".join("\\u{%x}" % ord(x) for x in py)) for u,py in rows)
print(len(low),len(upp),file=sys.stderr)
print("/// Characters whose `str.lower()` in CPython 3.14 differs from std's `char::to_lowercase`, with CPython's result.")
print("pub(crate) static LOWER_MAP_PY: &[(char, &str)] = &[\n"+rs(low)+"\n];\n")
print("/// Characters whose `str.upper()` in CPython 3.14 differs from std's `char::to_uppercase`, with CPython's result.")
print("pub(crate) static UPPER_MAP_PY: &[(char, &str)] = &[\n"+rs(upp)+"\n];")
