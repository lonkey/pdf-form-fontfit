# PDF Form Font Fit

A small command line tool that adjusts the font size of AcroForm text fields in
a PDF form so that entered content always fits. Many forms hard code a font size
in each field, which clips or overflows longer values. This tool rewrites that
size so the viewer can either size the text automatically or apply a fixed size
that you choose.

## Requirements

The minimum supported version is Python 3.9, which is the floor required by the
pinned pypdf release in `requirements.txt`. The tool was developed and tested on
Python 3.14, so any version from 3.9 up to the one you run should work.

The dependencies are declared in `requirements.txt`. pypdf reads and rewrites
the PDF, and cryptography is needed so that pypdf can open forms that use AES
encryption. Both are installed in the setup step below.

## Setup

Create and activate a virtual environment, then install the dependencies.

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

On Windows PowerShell, replace the activation line with `.venv\Scripts\Activate.ps1`.

## Usage

Run the tool with the path to a PDF form. When no output path is given, the
input name is reused with an underscore and a suffix inserted before the
extension.

```bash
python main.py my-awesome-form.pdf
```

The command above writes `my-awesome-form_fix.pdf` with automatic
sizing enabled, which lets the viewer pick a size that fits each field.

To pin every field to a fixed size in points, pass the size explicitly.

```bash
python main.py my-awesome-form.pdf --size 8
```

To choose the output path yourself, use the output option.

```bash
python main.py my-awesome-form.pdf --output ../output/path/my-awesome-form.pdf
```

The text used for the default output name can be changed with the suffix option.

```bash
python main.py my-awesome-form.pdf --suffix autosize
```

## How it works

The font size of an AcroForm field lives in its Default Appearance string,
stored under the key /DA, for example `/Helv 12 Tf 0 g`. The number in front of
the Tf operator is the font size in points. A value of 0 is a special case
defined by the PDF specification that tells the viewer to compute a size that
fits the field rectangle. The tool rewrites that value across every field and
also sets NeedAppearances to true, which asks the viewer to rebuild each field
appearance from the updated string.

## Notes on encrypted forms

Official forms are often encrypted with an empty user password as a permissions
wrapper rather than as real content protection. The tool relies on the
cryptography package so that pypdf can open such files automatically. The output
is written without encryption, which is convenient for filling the form
afterward.

## Notes on automatic sizing

Automatic sizing is resolved by the viewer at display time. Adobe Reader honors
it reliably. Some other viewers support it only partially, and a few ignore it
when printing. If you need a guaranteed baked appearance, pass an explicit fixed
size and fill the form with a tool that regenerates appearance streams.
