import argparse
from pathlib import Path

from vas2font.charsets import CHARACTER_SETS, get_character_set
from vas2font.extract import extract_handwriting
from vas2font.font import build_font
from vas2font.pdf import render_template_pdf
from vas2font.template import build_template, write_manifest
from vas2font.vas import load_notebook


def add_charset_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--charset",
        choices=sorted({identifier for identifier, _ in CHARACTER_SETS}),
        required=True,
    )
    command.add_argument("--version", type=int, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vas2font")
    commands = parser.add_subparsers(dest="command", required=True)
    generate_template = commands.add_parser("generate-template")
    add_charset_arguments(generate_template)
    generate_template.add_argument("--output-dir", type=Path, default=Path("build"))
    generate_font = commands.add_parser("generate-font")
    add_charset_arguments(generate_font)
    generate_font.add_argument("--notebook", type=Path, required=True)
    generate_font.add_argument("--output", type=Path, required=True)
    generate_font.add_argument("--ttf-output", type=Path)
    generate_font.add_argument("--font-family", default="VAS Handwriting")
    return parser


def main() -> None:
    parser = build_parser()
    arguments = parser.parse_args()
    try:
        character_set = get_character_set(arguments.charset, arguments.version)
        template = build_template(character_set)
        if arguments.command == "generate-template":
            arguments.output_dir.mkdir(parents=True, exist_ok=True)
            basename = f"{character_set.identifier}-v{character_set.version}"
            pdf_path = arguments.output_dir / f"{basename}.pdf"
            manifest_path = arguments.output_dir / f"{basename}.json"
            render_template_pdf(template, pdf_path)
            write_manifest(template, manifest_path)
            print(pdf_path)
            print(manifest_path)
            return
        notebook = load_notebook(arguments.notebook)
        extraction = extract_handwriting(notebook, template)
        result = build_font(
            extraction,
            arguments.output,
            arguments.font_family,
            arguments.ttf_output,
        )
    except (TypeError, ValueError, RuntimeError) as error:
        parser.error(str(error))
    print(f"Glyphs: {result.glyph_count}")
    print(f"Mapped characters: {result.mapped_character_count}")
    print(f"Outline points: {result.outline_point_count}")
    print(f"Overflow strokes: {extraction.overflow_strokes}")
    print(f"Missing characters: {''.join(extraction.missing_characters) or 'none'}")
    print(result.path)
    if result.ttf_path is not None:
        print(result.ttf_path)
