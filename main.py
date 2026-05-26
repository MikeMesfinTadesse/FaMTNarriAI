#!/usr/bin/env python3
"""
NarraAI — Audiobook Studio
Entry point. Run this file to launch the desktop GUI.
  python main.py          # GUI mode
  python main.py --cli    # CLI / batch mode
"""

import sys
import argparse


def launch_gui():
    try:
        import customtkinter  # noqa: F401
    except ImportError:
        print("customtkinter not found. Install with:  pip install customtkinter")
        sys.exit(1)
    from gui.app import NarraApp
    app = NarraApp()
    app.mainloop()


def launch_cli(args):
    from core.converter import AudiobookConverter
    from core.pdf_extractor import PDFExtractor
    from core.text_cleaner import TextCleaner

    print(f"\n🎙  NarraAI CLI — converting: {args.input}\n")

    # 1. Extract text
    if args.input.endswith(".pdf"):
        extractor = PDFExtractor(args.input)
        chapters = extractor.extract_chapters()
    else:
        with open(args.input, encoding="utf-8") as f:
            raw = f.read()
        chapters = [{"title": "Full Text", "text": raw}]

    # 2. Clean text
    cleaner = TextCleaner()
    for ch in chapters:
        ch["text"] = cleaner.clean(ch["text"])

    # 3. Convert
    converter = AudiobookConverter(
        voice=args.voice,
        speed=args.speed,
        output_dir=args.output,
    )
    converter.convert_chapters(chapters, playlist=args.playlist)
    print("\n✅  Done! Check your output folder.\n")


def main():
    parser = argparse.ArgumentParser(description="NarraAI Audiobook Studio")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode")
    parser.add_argument("--input", "-i", type=str, help="Input PDF or TXT file")
    parser.add_argument("--output", "-o", type=str, default="output", help="Output directory")
    parser.add_argument("--voice", "-v", type=str, default="en-US-AriaNeural")
    parser.add_argument("--speed", "-s", type=float, default=1.0, help="Speed multiplier (0.5–2.0)")
    parser.add_argument("--playlist", "-p", action="store_true", default=True, help="Generate .m3u playlist")

    args = parser.parse_args()

    if args.cli:
        if not args.input:
            parser.error("--cli requires --input")
        launch_cli(args)
    else:
        launch_gui()


if __name__ == "__main__":
    main()
