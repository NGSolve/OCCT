# Redirects libm calls (std::sin, ::sin, sin, ...) in OCCT sources to OccMath::.
# usage: rewrite_calls.py <occt root>
import re, sys, pathlib
root = pathlib.Path(sys.argv[1]) / "src"
FUNCS = ["sin", "cos", "tan", "asin", "acos", "atan", "atan2", "exp", "expm1", "log", "log1p",
         "log10", "pow", "sinh", "cosh", "tanh", "asinh", "acosh", "atanh", "cbrt"]
pat = re.compile(r"(?<![\w.>~])(?:std::|::)?(" + "|".join(FUNCS) + r")\s*\(")
SKIP = {"OccMath"}
nfiles = ncalls = 0
for p in sorted(root.rglob("*")):
    if p.suffix not in (".cxx", ".hxx", ".lxx", ".pxx", ".gxx") or p.parent.name in SKIP:
        continue
    if "GTests" in p.parts:
        continue
    text = p.read_text(encoding="utf-8", errors="surrogateescape")
    out = []
    n = 0
    in_comment = False
    for line in text.split("\n"):
        s = line.lstrip()
        if in_comment or s.startswith("//") or s.startswith("#"):
            if "*/" in line: in_comment = False
            out.append(line); continue
        if "/*" in line and "*/" not in line:
            in_comment = True
        # keep trailing // comments
        idx = line.find("//")
        head, tail = (line[:idx], line[idx:]) if idx >= 0 else (line, "")
        def repl(m):
            if p.parent.name == "Units" and m.group(1) == "pow":
                return m.group(0)  # Units has own pow overloads
            pre = head[:m.start()].rstrip()
            w = re.search(r"(\w+)$", pre)
            if w and w.group(1) not in ("return", "else", "case", "throw", "co_return"):
                return m.group(0)  # declaration "Type name(...)"
            return "OccMath::" + m.group(1) + "("
        new = pat.sub(repl, head)
        if new != head:
            n += new.count("OccMath::") - head.count("OccMath::")
        out.append(new + tail)
    # .lxx/.pxx/.gxx are included by .cxx/.hxx files which get the include
    if n and p.suffix in (".cxx", ".hxx"):
        for i, l in enumerate(out):
            if l.startswith("#include"):
                out.insert(i, "#include <OccMath.hxx>")
                break
        else:
            print("no include line in", p)
    if n:
        p.write_text("\n".join(out), encoding="utf-8", errors="surrogateescape")
        nfiles += 1
        ncalls += n
print(f"rewrote {ncalls} calls in {nfiles} files")
