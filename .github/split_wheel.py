# Splits the combined netgen_occt wheels into netgen_occt (runtime libraries) and
# netgen_occt_devel (headers, cmake files, import libraries), so OCCT is built only once.
# usage: split_wheel.py <wheelhouse>
import base64, hashlib, pathlib, re, sys, zipfile

NAME = "netgen_occt"
DEVEL_NAME = "netgen_occt_devel"
DEVEL_SUMMARY = "Open CASCADE Technology libraries, used by Netgen Mesher (development files)"


def is_devel(path):
    # path relative to the .data/data directory
    return path.startswith("include/") or path.endswith((".cmake", ".lib"))


def record_line(name, data):
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return f"{name},sha256={digest},{len(data)}"


def devel_metadata(metadata, version):
    head, sep, body = metadata.partition("\n\n")
    lines = []
    for line in head.split("\n"):
        if line.startswith("Name:"):
            line = f"Name: {DEVEL_NAME}"
        elif line.startswith("Summary:"):
            line = f"Summary: {DEVEL_SUMMARY}"
        elif line.startswith("Provides-Extra:") or (line.startswith("Requires-Dist:") and "extra ==" in line):
            continue
        lines.append(line)
        if line.startswith("Requires-Python:"):
            lines.append(f"Requires-Dist: netgen-occt=={version}")
    return "\n".join(lines) + sep + body


def write_wheel(path, prefix, files, dist_info):
    # files: list of (ZipInfo, data) with names relative to the wheel root, without dist-info
    record = []
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for info, data in files + dist_info:
            z.writestr(info, data)
            record.append(record_line(info.filename, data))
        record.append(f"{prefix}.dist-info/RECORD,,")
        z.writestr(f"{prefix}.dist-info/RECORD", "\n".join(record) + "\n")


def split(wheel):
    m = re.fullmatch(rf"{NAME}-([^-]+)-(.+)\.whl", wheel.name)
    version, tags = m.group(1), m.group(2)
    prefix = f"{NAME}-{version}"
    devel_prefix = f"{DEVEL_NAME}-{version}"
    data_dir = f"{prefix}.data/data/"

    runtime, devel, runtime_info, devel_info = [], [], [], []
    with zipfile.ZipFile(wheel) as z:
        for info in z.infolist():
            name = info.filename
            if info.is_dir() or name == f"{prefix}.dist-info/RECORD":
                continue
            data = z.read(info)
            if name.startswith(f"{prefix}.dist-info/"):
                runtime_info.append((info, data))
                info2 = zipfile.ZipInfo(devel_prefix + name[len(prefix):], info.date_time)
                info2.external_attr = info.external_attr
                info2.compress_type = zipfile.ZIP_DEFLATED
                if name.endswith("/METADATA"):
                    data = devel_metadata(data.decode(), version).encode()
                devel_info.append((info2, data))
            elif name.startswith(data_dir) and is_devel(name[len(data_dir):]):
                info2 = zipfile.ZipInfo(devel_prefix + name[len(prefix):], info.date_time)
                info2.external_attr = info.external_attr
                info2.compress_type = zipfile.ZIP_DEFLATED
                devel.append((info2, data))
            else:
                runtime.append((info, data))

    wheel.unlink()
    write_wheel(wheel, prefix, runtime, runtime_info)
    write_wheel(wheel.with_name(f"{devel_prefix}-{tags}.whl"), devel_prefix, devel, devel_info)
    print(f"{wheel.name}: {len(runtime)} runtime files, {len(devel)} devel files")


for wheel in sorted(pathlib.Path(sys.argv[1]).glob(f"{NAME}-*.whl")):
    split(wheel)
