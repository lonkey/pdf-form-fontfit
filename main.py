#!/usr/bin/env python3
"""Adjust the font size of AcroForm text fields in a PDF form.

Many government and enterprise PDF forms hard code a font size in each field.
When an entered value is longer than the form author anticipated, the text is
clipped or overflows because the size is fixed. This tool rewrites the font
size so that entered content fits.

The relevant setting lives in the Default Appearance string of each field. It
is stored under the key /DA in the field dictionary and, as a fallback, in the
AcroForm dictionary of the document catalog. A /DA string looks like this.

    /Helv 12 Tf 0 g

The value in front of the Tf operator is the font size in points. According to
the PDF specification (ISO 32000) a size of 0 is a special value that instructs
the viewer to compute a size that makes the text fit the field rectangle. That
behavior is what Acrobat exposes as the Auto option. Passing a positive value
instead pins the affected fields to that fixed size.

Setting /NeedAppearances to true asks conforming viewers to regenerate the
visual appearance of each field from the /DA string rather than displaying a
cached appearance that still reflects the old size.

Note on automatic sizing. A size of 0 is resolved by the viewer at display
time. Adobe Reader honors /NeedAppearances reliably. Some other viewers support
it only partially, and a few ignore it when printing. If you need a guaranteed
baked appearance, pass an explicit fixed size and fill the form with a tool that
regenerates appearance streams.

Note on encrypted input. Forms are frequently encrypted with an empty user
password as a permissions wrapper rather than as real content protection. pypdf
can derive the key with the empty password automatically, but it needs the
cryptography package to do so for the AES algorithm. The output written by this
tool is not encrypted, which is convenient for subsequent filling.
"""

import argparse
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import BooleanObject, NameObject, TextStringObject

# Text inserted before the file extension when the caller does not provide an
# explicit output path. The leading underscore is added during path
# construction, so the result is for example my-awesome-form_fix.pdf.
DEFAULT_SUFFIX = "fix"

# Font resource name used only when a /DA string contains no font operator at
# all and one has to be created. This resource is expected to exist in the
# AcroForm default resources under /DR. Helvetica is present in essentially
# every AcroForm, which makes it a safe default.
FALLBACK_FONT_RESOURCE = "/Helv"


def _set_font_size(default_appearance: str, size: float) -> str:
    """Return a copy of a /DA string with the font size operand replaced.

    The Default Appearance string is a small content stream. Tokens are
    separated by whitespace, and the numeric token that precedes the Tf
    operator is the font size in points. This function locates that operator
    and overwrites the preceding token with the requested size.

    When no Tf operator is present the string carries no font selection at all,
    so a minimal font selection is prepended using the fallback font resource.
    The size is formatted with the g presentation type, which drops a trailing
    decimal for whole numbers, so 0.0 becomes 0 and 8.0 becomes 8.
    """
    tokens = default_appearance.split()
    for index, token in enumerate(tokens):
        if token == "Tf" and index >= 1:
            # The operand immediately in front of Tf is the font size.
            tokens[index - 1] = f"{size:g}"
            return " ".join(tokens)

    # No font operator was found, so prepend a valid font selection.
    return f"{FALLBACK_FONT_RESOURCE} {size:g} Tf {default_appearance}".strip()


def set_field_font_size(src: Path, dst: Path, size: float = 0.0) -> None:
    """Rewrite every AcroForm field font size in src and write the result to dst.

    A size of 0.0 requests automatic sizing, where the viewer chooses a size
    that fits the field rectangle. Any positive value pins the affected fields
    to that fixed size in points.
    """
    # Clone the full object graph of the source document so that the original
    # file is never modified in place.
    writer = PdfWriter(clone_from=str(src))

    # The interactive form dictionary hangs off the document catalog, which is
    # the root object of the writer.
    acro_form = writer._root_object.get("/AcroForm")
    if acro_form is None:
        raise ValueError("the PDF contains no AcroForm and therefore no fillable fields")
    acro_form = acro_form.get_object()

    # Ask conforming viewers to rebuild field appearances from the /DA strings
    # instead of relying on any cached appearance streams.
    acro_form[NameObject("/NeedAppearances")] = BooleanObject(True)

    def patch_default_appearance(node) -> None:
        """Overwrite the /DA entry of a single dictionary when it has one."""
        node = node.get_object()
        current = node.get("/DA")
        if current is not None:
            updated = _set_font_size(str(current), size)
            node[NameObject("/DA")] = TextStringObject(updated)

    def walk(node) -> None:
        """Patch a field and then recurse into any child widgets it owns."""
        patch_default_appearance(node)
        for child in node.get_object().get("/Kids", []):
            walk(child)

    # Patch the form wide default first. This value applies to any field that
    # does not carry its own /DA entry.
    patch_default_appearance(acro_form)

    # Then patch every field and, recursively, every child widget. A single
    # logical field can own several widget annotations, each with its own /DA.
    for field in acro_form.get("/Fields", []):
        walk(field)

    # PdfWriter.write does not encrypt by default, so the output is a plain,
    # ready to fill PDF regardless of whether the input was encrypted.
    with open(dst, "wb") as handle:
        writer.write(handle)


def _font_size(raw: str) -> float:
    """Parse and validate the font size argument.

    Zero requests automatic sizing and any positive number is a fixed size. A
    negative value is rejected because it has no meaning as a font size.
    """
    value = float(raw)
    if value < 0:
        raise argparse.ArgumentTypeError("font size must be zero or a positive number")
    return value


def _build_parser() -> argparse.ArgumentParser:
    """Construct the command line argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Adjust the font size of AcroForm text fields in a PDF form so that "
            "entered content fits. A size of 0 enables automatic sizing."
        ),
    )
    parser.add_argument(
        "input",
        type=Path,
        help="path to the source PDF form",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "path to the output PDF. When omitted, the input name is reused with "
            "an underscore and a suffix inserted before the extension, for "
            "example my-awesome-form_fix.pdf"
        ),
    )
    parser.add_argument(
        "-s",
        "--size",
        type=_font_size,
        default=0.0,
        help="font size in points. 0 enables automatic sizing (default: 0)",
    )
    parser.add_argument(
        "--suffix",
        default=DEFAULT_SUFFIX,
        help=(
            "suffix used to build the default output name when no output path is "
            f"given (default: {DEFAULT_SUFFIX})"
        ),
    )
    return parser


def _derive_output_path(input_path: Path, suffix: str) -> Path:
    """Build a default output path by inserting an underscore and the suffix.

    The file extension of the input is preserved and the suffix is placed
    directly in front of it, so report.pdf with a suffix of fix becomes
    report_fix.pdf. The parent directory of the input is kept, so the output is
    written next to the source file.
    """
    return input_path.with_name(f"{input_path.stem}_{suffix}{input_path.suffix}")


def main() -> None:
    """Entry point for command line execution."""
    parser = _build_parser()
    args = parser.parse_args()

    input_path: Path = args.input
    if not input_path.is_file():
        parser.error(f"input file not found: {input_path}")

    output_path: Path = args.output or _derive_output_path(input_path, args.suffix)

    # Refuse to overwrite the source file, which protects the original from being
    # destroyed by an accidental identical output path.
    if output_path.resolve() == input_path.resolve():
        parser.error("the output path must be different from the input path")

    set_field_font_size(input_path, output_path, size=args.size)

    mode = "automatic sizing" if args.size == 0 else f"fixed size {args.size:g} pt"
    print(f"wrote {output_path} using {mode}")


if __name__ == "__main__":
    main()
