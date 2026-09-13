from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from kkciv_vintage.h11.pipeline import _manifest_entry, _read_csv, _sha256

# Renders the figure data as PGFPlots sources and compiles them with pdflatex. The
# manuscript is an Elsevier LaTeX document, so a vector figure that shares the document
# font beats a raster image, and the data stays readable inside the figure source.
SERIES_STYLE = {
    "B0": "mark=*, mark size=1.6pt, color=black, thick",
    "B1": "mark=square*, mark size=1.6pt, color=black!70, thick, dashed",
    "B2": "mark=triangle*, mark size=2pt, color=black!45, thick, dotted",
    "B3": "mark=diamond*, mark size=2pt, color=black, thick, dashdotted",
    "permintaan resmi": "fill=black!25",
    "permintaan sintetis": "fill=black!70",
}
# Bars need fills, not the line styles the other figures use.
BAR_STYLE = {
    "B0": "fill=black!12",
    "B1": "fill=black!35",
    "B2": "fill=black!60",
    "B3": "fill=black!85",
    "permintaan resmi": "fill=black!25",
    "permintaan sintetis": "fill=black!70",
}
AXIS_LABEL = {
    "sel direvisi": "Sel yang direvisi",
    "perlakuan": "Perlakuan",
    "skala beban": "Skala beban",
    "detik": "Detik",
    "byte": "Byte",
    "sel dievaluasi": "Sel yang dievaluasi",
    "rasio": "Rasio",
}
PREAMBLE = r"""% Dibentuk oleh kkciv_vintage.h15.render dari results/processed/h15-figure-data.csv.
% Jangan disunting langsung; jalankan make h15-figures untuk membentuk ulang.
\documentclass[border=2pt]{standalone}
\usepackage[T1]{fontenc}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\pgfplotsset{/pgf/number format/.cd, use comma, 1000 sep={.}}
\usepgfplotslibrary{groupplots}
\ifdefined\pdfvariable
  \pdfvariable suppressoptionalinfo \numexpr 1+2+4+8+16+32+64+128+256+512\relax
\fi
"""


def _label(name: str) -> str:
    return AXIS_LABEL.get(name, name)


def _line_figure(figure: dict[str, str], points: list[dict[str, str]]) -> str:
    series = sorted({row["series"] for row in points})
    xticks = sorted({int(row["x"]) for row in points})
    log = "\n  ymode=log," if figure["scale"] == "log" else ""
    body = [
        PREAMBLE,
        r"\begin{document}",
        r"\begin{tikzpicture}",
        r"\begin{axis}[",
        f"  xlabel={{{_label(figure['x_axis'])}}},",
        f"  ylabel={{{_label(figure['y_axis'])}}},",
        f"  xtick={{{','.join(str(value) for value in xticks)}}},",
        "  xmin=0, xmax=40,",
        "  width=0.92\\linewidth, height=6.2cm,",
        "  legend style={font=\\small, at={(0.5,1.03)}, anchor=south, legend columns=4,"
        " draw=none, /tikz/every even column/.append style={column sep=8pt}},",
        "  grid=both, grid style={line width=0.2pt, draw=gray!25},",
        f"  tick label style={{font=\\footnotesize}}, label style={{font=\\small}},{log}",
        "]",
    ]
    for name in series:
        selected = sorted(
            (row for row in points if row["series"] == name), key=lambda row: int(row["x"])
        )
        body.append(f"\\addplot[{SERIES_STYLE.get(name, 'thick')}, error bars/.cd,")
        body.append("  y dir=both, y explicit]")
        body.append("table[row sep=\\\\, y error plus index=2, y error minus index=3] {")
        body.append("x y eplus eminus \\\\")
        for row in selected:
            plus = float(row["y_max"]) - float(row["y"])
            minus = float(row["y"]) - float(row["y_min"])
            body.append(f"{row['x']} {row['y']} {plus:.6f} {minus:.6f} \\\\")
        body.append("};")
        body.append(f"\\addlegendentry{{{name}}}")
    body += [r"\end{axis}", r"\end{tikzpicture}", r"\end{document}", ""]
    return "\n".join(body)


def _bar_figure(figure: dict[str, str], points: list[dict[str, str]]) -> str:
    series = sorted({row["series"] for row in points})
    categories = sorted({row["x"] for row in points})
    body = [
        PREAMBLE,
        r"\begin{document}",
        r"\begin{tikzpicture}",
        r"\begin{axis}[",
        "  ybar, bar width=9pt, enlarge x limits=0.45,",
        f"  xlabel={{{_label(figure['x_axis'])}}},",
        f"  ylabel={{{_label(figure['y_axis'])}}},",
        f"  symbolic x coords={{{','.join(categories)}}},",
        "  xtick=data, ymin=0, ymax=1.08,",
        "  width=0.92\\linewidth, height=6.2cm,",
        "  nodes near coords={\\pgfmathprintnumber[fixed, fixed zerofill, precision=2]{\\pgfplotspointmeta}},",
        "  nodes near coords style={font=\\scriptsize},",
        "  legend style={font=\\small, at={(0.5,1.03)}, anchor=south, legend columns=4,"
        " draw=none, /tikz/every even column/.append style={column sep=8pt}},",
        "  grid=major, grid style={line width=0.2pt, draw=gray!25},",
        "  tick label style={font=\\small}, label style={font=\\small},",
        "]",
    ]
    for name in series:
        selected = {row["x"]: row["y"] for row in points if row["series"] == name}
        coordinates = " ".join(
            f"({category},{selected[category]})" for category in categories if category in selected
        )
        body.append(
            f"\\addplot[draw=black, mark=none, {BAR_STYLE.get(name, 'fill=black!40')}] "
            f"coordinates {{{coordinates}}};"
        )
        body.append(f"\\addlegendentry{{{name}}}")
    body += [r"\end{axis}", r"\end{tikzpicture}", r"\end{document}", ""]
    return "\n".join(body)


def render(
    *,
    data_path: Path,
    inventory_path: Path,
    output_dir: Path,
    manifest_output: Path,
    compile_pdf: bool = True,
) -> dict[str, Any]:
    points = _read_csv(data_path)
    inventory = _read_csv(inventory_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, Any]] = []
    compiled: list[str] = []

    for figure in inventory:
        figure_id = figure["figure_id"]
        selected = [row for row in points if row["figure_id"] == figure_id]
        if not selected:
            raise ValueError(f"figure {figure_id} has no data points")
        builder = _bar_figure if figure["x_axis"] in {"perlakuan", "skala beban"} else _line_figure
        source = output_dir / f"{figure_id.lower()}.tex"
        source.write_text(builder(figure, selected), encoding="utf-8")
        written.append(_manifest_entry(source))

        if not compile_pdf:
            continue
        environment = {
            **os.environ,
            # A fixed epoch keeps the compiled PDF byte-identical between runs.
            "SOURCE_DATE_EPOCH": "1757721600",
            "FORCE_SOURCE_DATE": "1",
        }
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", source.name],
            cwd=output_dir,
            env=environment,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise ValueError(
                f"pdflatex failed for {figure_id}:\n{result.stdout[-2000:]}"
            )
        pdf = output_dir / f"{figure_id.lower()}.pdf"
        if not pdf.exists():
            raise ValueError(f"pdflatex produced no PDF for {figure_id}")
        written.append(_manifest_entry(pdf))
        compiled.append(figure_id)
        for suffix in (".aux", ".log"):
            leftover = output_dir / f"{figure_id.lower()}{suffix}"
            if leftover.exists():
                leftover.unlink()

    manifest = {
        "stage": "H15",
        "track": "AC",
        "artifact": "figures",
        "render_status": "rendered" if compile_pdf else "sources_only",
        "renderer": "pgfplots via pdflatex, reproducible with a fixed SOURCE_DATE_EPOCH",
        "figures": [figure["figure_id"] for figure in inventory],
        "compiled": compiled,
        "inputs": [_manifest_entry(data_path), _manifest_entry(inventory_path)],
        "outputs": written,
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "figures": len(inventory),
        "sources": sum(1 for item in written if item["path"].endswith(".tex")),
        "compiled": len(compiled),
        "outputs": len(written),
        "status": "rendered" if compile_pdf else "sources_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="KK-CIV H15 figure rendering")
    parser.add_argument("--data", type=Path, default=Path("results/processed/h15-figure-data.csv"))
    parser.add_argument(
        "--inventory", type=Path, default=Path("results/processed/h15-figure-inventory.csv")
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("papers/vintage_reconciliation/manuscript/figures")
    )
    parser.add_argument("--manifest-output", type=Path, default=Path("data/manifests/h15-figures.json"))
    parser.add_argument("--sources-only", action="store_true")
    args = parser.parse_args()
    result = render(
        data_path=args.data,
        inventory_path=args.inventory,
        output_dir=args.output_dir,
        manifest_output=args.manifest_output,
        compile_pdf=not args.sources_only,
    )
    print(
        f"H15 rendered {result['sources']} figure sources and compiled {result['compiled']} of them "
        f"into {args.output_dir}"
    )
    print(
        "H15F_VERIFY|"
        + "|".join(
            [
                str(result["figures"]),
                str(result["sources"]),
                str(result["compiled"]),
                str(result["outputs"]),
                result["status"],
            ]
        )
    )
    print(f"Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
