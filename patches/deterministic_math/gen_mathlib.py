# Adds the needed OpenLibm (FreeBSD msun / FDLIBM) double functions as TKernel package
# OccMath. Symbols are renamed to OccMath_*, so they never clash with the platform libm.
# usage: gen_mathlib.py <occt root>
import re, sys, pathlib
src = pathlib.Path(__file__).resolve().parent / "openlibm" / "src"
tkernel = pathlib.Path(sys.argv[1]) / "src" / "FoundationClasses" / "TKernel"
out = tkernel / "OccMath"
out.mkdir(parents=True, exist_ok=True)

FILES = ["k_sin", "k_cos", "k_tan", "k_rem_pio2", "e_rem_pio2", "s_sin", "s_cos", "s_tan",
         "e_asin", "e_acos", "s_atan", "e_atan2", "e_exp", "k_exp", "s_expm1", "e_log",
         "s_log1p", "e_log10", "e_pow", "e_sinh", "e_cosh", "s_tanh", "s_asinh", "e_acosh",
         "e_atanh", "s_cbrt"]
FUNCS1 = ["sin", "cos", "tan", "asin", "acos", "atan", "exp", "expm1", "log", "log1p", "log10",
          "sinh", "cosh", "tanh", "asinh", "acosh", "atanh", "cbrt"]
FUNCS2 = ["atan2", "pow"]

math_private = (src / "math_private.h").read_text()
m = re.search(r"(/\* Get two 32 bit ints from a double\.  \*/.*?)/\*\s*\n \* A union which permits us to convert between a float", math_private, re.S)
word_macros = m.group(1)

license = """/*
 * Generated from OpenLibm (https://github.com/JuliaMath/openlibm), which derives from
 * FreeBSD msun and FDLIBM 5.3.
 *
 * Copyright (C) 1993-2004 by Sun Microsystems, Inc. All rights reserved.
 * Developed at SunSoft, a Sun Microsystems, Inc. business.
 * Permission to use, copy, modify, and distribute this
 * software is freely granted, provided that this notice
 * is preserved.
 *
 * Copyright (c) 2011-14 The Julia Project (MIT license).
 * Copyright (c) 2004-2011 David Schultz, Bruce D. Evans, Steven G. Kargl (BSD 2-clause).
 * See the license notices in the individual sections below.
 */
"""

priv = license + """
/* Pure double arithmetic, bitwise reproducible on IEEE 754 platforms when compiled
   without FMA contraction and without x87 extended precision. */

#ifndef OccMath_private_HeaderFile
#define OccMath_private_HeaderFile

#ifdef _MSC_VER
  #pragma fp_contract(off)
  #pragma float_control(precise, on)
#elif defined(__clang__)
  #pragma STDC FP_CONTRACT OFF
#elif defined(__GNUC__)
  #pragma GCC optimize("fp-contract=off")
#endif

#include <float.h>
#include <stdint.h>
#include <math.h>

#if defined(_WIN32) && !defined(OCCT_STATIC_BUILD) && !defined(HAVE_NO_DLL)
  #define OLM_DLLEXPORT __declspec(dllexport)
#else
  #define OLM_DLLEXPORT
#endif

typedef uint32_t u_int32_t;
typedef uint64_t u_int64_t;

/* all supported targets are little endian */
typedef union
{
  double value;
  struct { u_int32_t lsw; u_int32_t msw; } parts;
  struct { u_int64_t w; } xparts;
} ieee_double_shape_type;

""" + word_macros + """
#define STRICT_ASSIGN(type, lval, rval) ((lval) = (rval))
#define openlibm_weak_reference(sym, alias)
#define __inline
#define irint(x) ((int)rint(x))

"""
priv += "".join(f"#define {f} OccMath_{f}\n#define __ieee754_{f} OccMath_{f}\n" for f in FUNCS1 + FUNCS2)
priv += """#define __ieee754_rem_pio2 OccMath_rem_pio2
#define __kernel_sin OccMath_kernel_sin
#define __kernel_cos OccMath_kernel_cos
#define __kernel_tan OccMath_kernel_tan
#define __kernel_rem_pio2 OccMath_kernel_rem_pio2
#define __ldexp_exp OccMath_ldexp_exp
#define __frexp_exp OccMath_frexp_exp
#define __ieee754_sqrt sqrt

"""
priv += "".join(f"OLM_DLLEXPORT double {f}(double);\n" for f in FUNCS1)
priv += "".join(f"OLM_DLLEXPORT double {f}(double, double);\n" for f in FUNCS2)
priv += """int __ieee754_rem_pio2(double, double *);
double __kernel_sin(double, double, int);
double __kernel_cos(double, double);
double __kernel_tan(double, double, int);
int __kernel_rem_pio2(double *, double *, int, int, int);
double __ldexp_exp(double, int);

#endif
"""
(out / "OccMath_private.h").write_text(priv)

files = ["OccMath.hxx", "OccMath_private.h"]
for f in FILES:
    t = (src / f"{f}.c").read_text()
    t = re.sub(r'^\s*#\s*include\s*[<"](cdefs-compat\.h|math_private\.h|openlibm_math\.h|float\.h)[>"].*\n', "", t, flags=re.M)
    t = t.replace('#include "k_log.h"', '#include "OccMath_k_log.h"')
    if f == "k_exp":
        t = t.replace("#include <openlibm_complex.h>\n", "")
        t = t[:t.index("OLM_DLLEXPORT double complex")]
    (out / f"OccMath_{f}.c").write_text('#include "OccMath_private.h"\n' + t)
    files.append(f"OccMath_{f}.c")
(out / "OccMath_k_log.h").write_text((src / "k_log.h").read_text().replace('#include "cdefs-compat.h"\n', ""))
files.append("OccMath_k_log.h")

decl = "".join(f"  Standard_EXPORT double OccMath_{f}(double);\n" for f in FUNCS1)
decl += "".join(f"  Standard_EXPORT double OccMath_{f}(double, double);\n" for f in FUNCS2)
api1 = "".join(f"""
  inline double {f}(double theX) {{ return OccMath_{f}(theX); }}
  inline float {f}(float theX) {{ return float(OccMath_{f}(theX)); }}
  template <class T, class = typename std::enable_if<std::is_integral<T>::value>::type>
  inline double {f}(T theX) {{ return OccMath_{f}(double(theX)); }}
""" for f in FUNCS1)
api2 = "".join(f"""
  inline double {f}(double theX, double theY) {{ return OccMath_{f}(theX, theY); }}
  inline float {f}(float theX, float theY) {{ return float(OccMath_{f}(theX, theY)); }}
  template <class T, class U,
            class = typename std::enable_if<std::is_arithmetic<T>::value && std::is_arithmetic<U>::value>::type>
  inline double {f}(T theX, U theY) {{ return OccMath_{f}(double(theX), double(theY)); }}
""" for f in FUNCS2)

(out / "OccMath.hxx").write_text(f"""// Copyright (c) 2026 OPEN CASCADE SAS
//
// This file is part of Open CASCADE Technology software library.
//
// This library is free software; you can redistribute it and/or modify it under
// the terms of the GNU Lesser General Public License version 2.1 as published
// by the Free Software Foundation, with special exception defined in the file
// OCCT_LGPL_EXCEPTION.txt. Consult the file LICENSE_LGPL_21.txt included in OCCT
// distribution for complete text of the license and disclaimer of any warranty.
//
// Alternatively, this file may be used under the terms of Open CASCADE
// commercial license or contractual agreement.

#ifndef _OccMath_HeaderFile
#define _OccMath_HeaderFile

#include <Standard_Macro.hxx>

#include <type_traits>

//! Elementary functions with bitwise identical results on all platforms
//! (FDLIBM based, independent of the C runtime libm).
extern "C"
{{
{decl}}}

namespace OccMath
{{{api1}{api2}}} // namespace OccMath

#endif
""")

(out / "FILES.cmake").write_text("""# Source files for OccMath package
set(OCCT_OccMath_FILES_LOCATION "${CMAKE_CURRENT_LIST_DIR}")

set(OCCT_OccMath_FILES
""" + "".join(f"  {f}\n" for f in files) + ")\n")

packages = tkernel / "PACKAGES.cmake"
t = packages.read_text()
if "  OccMath\n" not in t:
    packages.write_text(t.replace("  Standard\n", "  Standard\n  OccMath\n"))
