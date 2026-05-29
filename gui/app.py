"""
gui/app.py — NarraAI Desktop GUI
═══════════════════════════════════════════════════════════════════════════════

PURPOSE:
    The main desktop interface for NarraAI. Built with CustomTkinter, it wires
    together all the core modules (pdf_extractor, text_cleaner, converter) into
    a user-friendly windowed application.

TAB DESCRIPTIONS:
    ✏ Editor       — Type or paste any text, add emotion tags (whisper, shout,
                     etc.), clean it, preview it with a voice, then convert it
                     to audio. This is the main workspace for short texts.

    📑 Chapters    — After loading a PDF, this tab shows all auto-detected
                     chapters. Each chapter can be individually approved (✓) or
                     rejected (✗) before converting. Shows word count and
                     estimated spoken duration per chapter.

    📄 Page Range  — Convert any specific page range from a loaded PDF as a
                     single audio file.

    🎤 Voice Tester — Test and compare any Edge-TTS voice side by side. Type
                     a sample sentence and click Test on any voice.

    🌍 Languages   — Convert text or upload a PDF/TXT in any supported language.
                     Includes optional machine translation (via deep-translator)
                     so you can translate English text into the target language
                     before converting to audio.

    🧒 Kids Section — Dedicated storytelling section for children. Includes:
                     • Built-in stories + upload your own PDF/TXT
                     • Language selector (same as Languages tab) so stories
                       can be read in ANY language
                     • Optional translation: translate a story into another
                       language then read it aloud
                     • Kids-friendly voice selector (warm, expressive voices)

    ⚡ Templates   — Quick-load preset sample texts into the Editor tab.

    📋 Log         — Timestamped record of all app activity.

TRANSLATION FEATURE:
    Uses the 'deep-translator' package (pip install deep-translator).
    Uses GoogleTranslator — no API key required, free to use.
    Supports 100+ languages. If not installed, the Translate button is
    disabled and a clear message explains how to enable it.

NEW LANGUAGES:
    Filipino: fil-PH-BlessicaNeural (F), fil-PH-AngeloNeural (M)
    Tigrinya: Edge-TTS has no native Tigrinya voice. The app adds Tigrinya
              as a language option that auto-translates text to Tigrinya (via
              deep-translator) then reads it with an Amharic voice (same Ge'ez
              script). Install deep-translator to enable: pip install deep-translator

OUTPUT FILENAME FORMAT:
    VoiceName__DocumentTitle__01_ChapterTitle.mp3
    Previous files are NEVER deleted or overwritten.

DEPENDENCIES:
    customtkinter      pip install customtkinter
    deep-translator    pip install deep-translator  (optional, for translation)
    core.converter, core.pdf_extractor, core.text_cleaner
═══════════════════════════════════════════════════════════════════════════════
"""

import sys
import os
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import customtkinter as ctk

from core.converter     import AudiobookConverter, VOICES, KIDS_VOICES, voice_short_name
from core.pdf_extractor import PDFExtractor, extract_short_story, estimate_duration
from core.text_cleaner  import TextCleaner

# ── ElevenLabs integration ───────────────────────────────────────────────────
try:
    from core.elevenlabs_tts import (
        fetch_voices as el_fetch_voices,
        clone_voice  as el_clone_voice,
        ElevenLabsConverter,
        ELEVENLABS_SDK,
        REQUESTS_AVAILABLE as EL_REQUESTS,
    )
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    ELEVENLABS_SDK       = False

# ── Check deep-translator availability ───────────────────────────────────────
try:
    from deep_translator import GoogleTranslator
    TRANSLATION_AVAILABLE = True
except ImportError:
    TRANSLATION_AVAILABLE = False

# ── Theme ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

ACCENT   = "#c97af2"
ACCENT2  = "#7af2d4"
SURFACE  = "#16131f"
SURFACE2 = "#1e1a2e"
TEXT2    = "#9d98b8"
COL_OK   = "#2a6858"
COL_BAD  = "#6a2020"

# ── Language → Voice catalogue ───────────────────────────────────────────────
# Used by both the Languages tab and the Kids Section tab.
# Key format: "FLAG LANGUAGE_NAME"
# Value: list of (edge_tts_voice_id, human_label) tuples

MULTILANG_VOICES = {
    "\U0001f1f8\U0001f1e6 Arabic":    [
        ("ar-SA-ZariyahNeural",  "Zariyah \u2014 Saudi Arabia, F"),
        ("ar-SA-HamedNeural",    "Hamed \u2014 Saudi Arabia, M"),
        ("ar-EG-SalmaNeural",    "Salma \u2014 Egypt, F"),
        ("ar-EG-ShakirNeural",   "Shakir \u2014 Egypt, M"),
        ("ar-AE-FatimaNeural",   "Fatima \u2014 UAE, F"),
        ("ar-AE-HamdanNeural",   "Hamdan \u2014 UAE, M"),
    ],
    "\U0001f1ef\U0001f1f5 Japanese":  [
        ("ja-JP-NanamiNeural",   "Nanami, F"),
        ("ja-JP-KeitaNeural",    "Keita, M"),
    ],
    "\U0001f1e8\U0001f1f3 Chinese":   [
        ("zh-CN-XiaoxiaoNeural", "Xiaoxiao (CN), F"),
        ("zh-CN-YunxiNeural",    "Yunxi (CN), M"),
        ("zh-TW-HsiaoChenNeural","HsiaoChen (TW), F"),
    ],
    "\U0001f1eb\U0001f1f7 French":    [
        ("fr-FR-DeniseNeural",   "Denise, F"),
        ("fr-FR-HenriNeural",    "Henri, M"),
    ],
    "\U0001f1e9\U0001f1ea German":    [
        ("de-DE-KatjaNeural",    "Katja, F"),
        ("de-DE-ConradNeural",   "Conrad, M"),
    ],
    "\U0001f1ea\U0001f1f8 Spanish":   [
        ("es-ES-ElviraNeural",   "Elvira \u2014 Spain, F"),
        ("es-MX-DaliaNeural",    "Dalia \u2014 Mexico, F"),
        ("es-MX-JorgeNeural",    "Jorge \u2014 Mexico, M"),
    ],
    "\U0001f1f7\U0001f1fa Russian":   [
        ("ru-RU-SvetlanaNeural", "Svetlana, F"),
        ("ru-RU-DmitryNeural",   "Dmitry, M"),
    ],
    "\U0001f1f0\U0001f1f7 Korean":    [
        ("ko-KR-SunHiNeural",    "Sun-Hi, F"),
        ("ko-KR-InJoonNeural",   "InJoon, M"),
    ],
    "\U0001f1ee\U0001f1f3 Hindi":     [
        ("hi-IN-SwaraNeural",    "Swara, F"),
        ("hi-IN-MadhurNeural",   "Madhur, M"),
    ],
    "\U0001f1f9\U0001f1f7 Turkish":   [
        ("tr-TR-EmelNeural",     "Emel, F"),
        ("tr-TR-AhmetNeural",    "Ahmet, M"),
    ],
    "\U0001f1f8\U0001f1f0 Slovak":    [
        ("sk-SK-ViktoriaNeural", "Viktoria, F"),
        ("sk-SK-LukasNeural",    "Lukas, M"),
    ],
    "\U0001f1f0\U0001f1ea Swahili":   [
        ("sw-KE-ZuriNeural",     "Zuri \u2014 Kenya, F"),
        ("sw-KE-RafikiNeural",   "Rafiki \u2014 Kenya, M"),
        ("sw-TZ-RehemaNeural",   "Rehema \u2014 Tanzania, F"),
        ("sw-TZ-DaudiNeural",    "Daudi \u2014 Tanzania, M"),
    ],
    "\U0001f1ea\U0001f1f9 Amharic":   [
        ("am-ET-MekdesNeural",   "Mekdes \u2014 Ethiopia, F"),
        ("am-ET-AmehaNeural",    "Ameha \u2014 Ethiopia, M"),
    ],
    "\U0001f1f5\U0001f1ed Filipino":  [
        ("fil-PH-BlessicaNeural","Blessica, F"),
        ("fil-PH-AngeloNeural",  "Angelo, M"),
    ],
    # Tigrinya (ti-ET/ti-ER) is not natively in Edge-TTS.
    # Amharic voices read Geʼez script (shared with Tigrinya) well.
    "🇪🇷 Tigrinya":   [
        ("am-ET-MekdesNeural",   "Mekdes (Geʼez script, F)"),
        ("am-ET-AmehaNeural",    "Ameha (Geʼez script, M)"),
    ],
}

# deep-translator language codes mapped to our MULTILANG_VOICES keys.
# Used by the Translate button in Languages and Kids tabs.
LANG_TO_TRANSLATE_CODE = {
    "\U0001f1f8\U0001f1e6 Arabic":    "ar",
    "\U0001f1ef\U0001f1f5 Japanese":  "ja",
    "\U0001f1e8\U0001f1f3 Chinese":   "zh-CN",
    "\U0001f1eb\U0001f1f7 French":    "fr",
    "\U0001f1e9\U0001f1ea German":    "de",
    "\U0001f1ea\U0001f1f8 Spanish":   "es",
    "\U0001f1f7\U0001f1fa Russian":   "ru",
    "\U0001f1f0\U0001f1f7 Korean":    "ko",
    "\U0001f1ee\U0001f1f3 Hindi":     "hi",
    "\U0001f1f9\U0001f1f7 Turkish":   "tr",
    "\U0001f1f8\U0001f1f0 Slovak":    "sk",
    "\U0001f1f0\U0001f1ea Swahili":   "sw",
    "\U0001f1ea\U0001f1f9 Amharic":   "am",
    "\U0001f1f5\U0001f1ed Filipino":  "tl",
        "🇪🇷 Tigrinya":   "ti",
}

LANG_SAMPLES = {
    "\U0001f1f8\U0001f1e6 Arabic":    "\u0645\u0631\u062d\u0628\u0627\u064b \u0628\u0643\u0645 \u0641\u064a \u062a\u0637\u0628\u064a\u0642 \u0646\u0627\u0631\u0627 \u0644\u0644\u0643\u062a\u0628 \u0627\u0644\u0635\u0648\u062a\u064a\u0629.\n\u064a\u0645\u0643\u0646\u0643 \u0627\u0644\u0622\u0646 \u062a\u062d\u0648\u064a\u0644 \u0623\u064a \u0646\u0635 \u0625\u0644\u0649 \u0635\u0648\u062a \u0637\u0628\u064a\u0639\u064a \u0639\u0627\u0644\u064a \u0627\u0644\u062c\u0648\u062f\u0629.",
    "\U0001f1ef\U0001f1f5 Japanese":  "\u30ca\u30ec\u30fcAI\u3078\u3088\u3046\u3053\u305d\u3002\n\u9ad8\u54c1\u8cea\u306a\u97f3\u58f0\u3067\u3001\u3042\u3089\u3086\u308b\u30c6\u30ad\u30b9\u30c8\u3092\u8aad\u307f\u4e0a\u3052\u307e\u3059\u3002",
    "\U0001f1e8\U0001f1f3 Chinese":   "\u6b22\u8fce\u4f7f\u7528NarraAI\u6709\u58f0\u4e66\u5de5\u4f5c\u5ba4\u3002\n\u6211\u4eec\u652f\u6301\u591a\u79cd\u8bed\u8a00\u7684\u9ad8\u8d28\u91cf\u8bed\u97f3\u5408\u6210\u3002",
    "\U0001f1eb\U0001f1f7 French":    "Bienvenue dans NarraAI, votre studio d'audiolivres.\nConvertissez n'importe quel texte en audio naturel.",
    "\U0001f1e9\U0001f1ea German":    "Willkommen bei NarraAI, Ihrem H\u00f6rbuch-Studio.\nWandeln Sie beliebigen Text in nat\u00fcrliche Sprache um.",
    "\U0001f1ea\U0001f1f8 Spanish":   "Bienvenido a NarraAI, tu estudio de audiolibros.\nConvierte cualquier texto en audio natural de alta calidad.",
    "\U0001f1f7\U0001f1fa Russian":   "\u0414\u043e\u0431\u0440\u043e \u043f\u043e\u0436\u0430\u043b\u043e\u0432\u0430\u0442\u044c \u0432 NarraAI.\n\u041f\u0440\u0435\u043e\u0431\u0440\u0430\u0437\u0443\u0439\u0442\u0435 \u043b\u044e\u0431\u043e\u0439 \u0442\u0435\u043a\u0441\u0442 \u0432 \u0435\u0441\u0442\u0435\u0441\u0442\u0432\u0435\u043d\u043d\u044b\u0439 \u0433\u043e\u043b\u043e\u0441.",
    "\U0001f1f0\U0001f1f7 Korean":    "NarraAI \uc624\ub514\uc624\ubd81 \uc2a4\ud29c\ub514\uc624\uc5d0 \uc624\uc2e0 \uac83\uc744 \ud658\uc601\ud569\ub2c8\ub2e4.\n\uc790\uc5f0\uc2a4\ub7ec\uc6b4 \uc74c\uc131\uc73c\ub85c \ud14d\uc2a4\ud2b8\ub97c \ubcc0\ud658\ud558\uc138\uc694.",
    "\U0001f1ee\U0001f1f3 Hindi":     "NarraAI \u0911\u0921\u093f\u092f\u094b\u092c\u0941\u0915 \u0938\u094d\u091f\u0942\u0921\u093f\u092f\u094b \u092e\u0947\u0902 \u0906\u092a\u0915\u093e \u0938\u094d\u0935\u093e\u0917\u0924 \u0939\u0948\u0964\n\u0915\u093f\u0938\u0940 \u092d\u0940 \u092a\u093e\u0920 \u0915\u094b \u092a\u094d\u0930\u093e\u0915\u0943\u0924\u093f\u0915 \u0906\u0935\u093e\u091c\u093c \u092e\u0947\u0902 \u092c\u0926\u0932\u0947\u0902\u0964",
    "\U0001f1f9\U0001f1f7 Turkish":   "NarraAI sesli kitap st\u00fcdy osuna ho\u015f geldiniz.\nHerhangi bir metni do\u011fal sese d\u00f6n\u00fc\u015ft\u00fcr\u00fcn.",
    "\U0001f1f8\U0001f1f0 Slovak":    "Vitajte v NarraAI, va\u0161om \u0161t\u00fadi\u00f3 audiokn\u00edh.\nPremena ak\u00e9hoko\u013evek textu na prirodzen\u00fd hlas.",
    "\U0001f1f0\U0001f1ea Swahili":   "Karibu kwenye NarraAI, studio yako ya vitabu vya sauti.\nTunaweza kubadilisha maandishi yoyote kuwa sauti ya hali ya juu.",
    "\U0001f1ea\U0001f1f9 Amharic":   "\u12c8\u12f0 NarraAI \u12d5\u1209\u12a5\u1295 \u12f0\u1205\u1293 \u1218\u1328\u1271\u1362\n\u121b\u1295\u12db\u1293\u1295\u121d \u1338\u1211\u1349\u1355 \u12c8\u12f0 \u12a8\u1348\u1270\u129b \u1325\u122b\u1275 \u12f5\u121d\u1345 \u1218\u1240\u12e8\u122d \u12f0\u1295\u127b\u1209\u1362",
    "\U0001f1f5\U0001f1ed Filipino":  "Maligayang pagdating sa NarraAI, ang iyong audiobook studio.\nMaaari mong i-convert ang anumang teksto sa natural na boses.",
    "🇪🇷 Tigrinya":   "ወደ NarraAI እዘይ ተሰዘቡ. ማንዛናንም ተኰኳይ ድምፅ እንደግሩ ይተርጉማሉ.",
}

# ── Kids Section built-in stories ────────────────────────────────────────────
KIDS_STORIES = {
    "The Brave Little Fox": (
        "Once upon a time in a great green forest, there lived a little fox named Felix.\n\n"
        "Felix was small, but his heart was as big as the tallest oak tree.\n\n"
        "One morning, Felix heard a tiny voice calling from the river. It was a baby duck, "
        "stuck between two rocks, unable to get free.\n\n"
        "Without a moment of hesitation, Felix leaped into the shallow water, "
        "carefully nudged the rocks apart, and set the little duck free.\n\n"
        "The duck looked up with big, grateful eyes. \"Thank you, brave fox!\"\n\n"
        "Felix smiled. \"That's what friends are for,\" he said.\n\n"
        "And from that day on, the fox and the duck were the very best of friends."
    ),
    "The Star That Fell": (
        "High above the clouds, there was a little star named Lumi.\n\n"
        "Every night, Lumi shone as brightly as she could, lighting the way for ships "
        "and dreamers below.\n\n"
        "But one windy night, a great gust blew Lumi right out of the sky!\n\n"
        "She tumbled and twirled and landed softly in a meadow full of fireflies.\n\n"
        "\"Where am I?\" asked Lumi.\n\n"
        "\"You're with us!\" said the fireflies. \"We've always wanted to meet a real star.\"\n\n"
        "Together they danced and glowed until the sun rose and carried Lumi gently "
        "back to her place in the sky, her heart full of new friends and happy memories."
    ),
    "The Dragon Who Was Afraid of Fire": (
        "In the land of Embervale lived a dragon named Pip.\n\n"
        "Pip had shiny purple scales, enormous wings, and absolutely no fire whatsoever.\n\n"
        "Every time Pip tried to breathe fire, he sneezed out bubbles instead.\n\n"
        "The other dragons would laugh, and Pip would hide behind the waterfall.\n\n"
        "One day, the village below Embervale needed light — their lanterns had all gone out.\n\n"
        "Pip flew down and blew his biggest bubble breath. The bubbles floated into every "
        "window, each one glowing softly with rainbow light.\n\n"
        "The villagers cheered. The children danced.\n\n"
        "From that day on, Pip was known as the most magical dragon in all the land. "
        "Not because of fire, but because of who he truly was."
    ),
}

TEMPLATES = {
    "Fantasy": (
        '(whisper) The old wizard raised his trembling hand toward the sky. '
        '(pause) "You dare challenge me?" (shout) His voice cracked the air like thunder.\n\n'
        '(excited) Lightning arced between his fingers. (sad) She had never seen him like this.'
    ),
    "Horror": (
        '(whisper) She heard it again \u2014 beneath the floorboards. (pause) '
        'Slow. Deliberate.\n\n(dramatic) The candle went out. '
        '(shout) "Who\'s there?!" Her voice echoed... and something answered.'
    ),
    "Children": (
        '(gentle) Once upon a time, in a forest where the trees hummed lullabies, '
        'there lived a small bear named Tobias.\n\n'
        '(excited) Every morning he raced to the meadow! "Good morning, world!" he called.'
    ),
    "News": (
        "Breaking: Global leaders convened today for an emergency summit. "
        "(pause) Scientists warn that tipping points could be reached within the decade. "
        "Negotiations, while tense, are showing signs of progress."
    ),
}


# ════════════════════════════════════════════════════════════════════════════
class NarraApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("NarraAI \u2014 Audiobook Studio")
        self.geometry("1360x860")
        self.minsize(980, 700)

        self._pdf_path:      Optional[str] = None
        self._doc_title:     str           = "Untitled"
        self._chapters:      list[dict]    = []
        self._output_dir:    str           = str(Path.home() / "NarraAI_Output")
        self._is_converting: bool          = False
        self._char_rows:     list[dict]    = []
        self._lang_pdf_path: Optional[str] = None
        self._kids_pdf_path: Optional[str] = None
        self._el_api_key:    str           = os.environ.get('ELEVENLABS_API_KEY', '')
        self._el_voices:     list[dict]    = []   # [{voice_id, name, category}]
        self._el_voice_map:  dict[str,str] = {}   # label -> voice_id

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()
        self._build_status_bar()

    # ════════════════════════════════════════════════════════════════════════
    # SIDEBAR
    # ════════════════════════════════════════════════════════════════════════

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=252, corner_radius=0, fg_color=SURFACE)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_rowconfigure(10, weight=1)

        ctk.CTkLabel(sb, text="\U0001f399 NarraAI",
                     font=ctk.CTkFont("Georgia", 22, "bold"),
                     text_color=ACCENT).grid(row=0, column=0, padx=20, pady=(18,4), sticky="w")
        ctk.CTkLabel(sb, text="Audiobook Studio", text_color=TEXT2,
                     font=ctk.CTkFont(size=11)).grid(row=1, column=0, padx=20, pady=(0,14), sticky="w")

        ctk.CTkButton(sb, text="\U0001f4c4  Load PDF / TXT", command=self._load_file,
                      fg_color=SURFACE2, hover_color="#2a2540",
                      border_color=ACCENT, border_width=1, text_color=ACCENT, height=36,
                      ).grid(row=2, column=0, padx=14, pady=(0,6), sticky="ew")

        self._file_label = ctk.CTkLabel(sb, text="No file loaded", text_color=TEXT2,
                                         font=ctk.CTkFont(size=11), wraplength=215, justify="left")
        self._file_label.grid(row=3, column=0, padx=14, pady=(0,12), sticky="w")

        self._sep(sb, 4)

        ctk.CTkLabel(sb, text="VOICE  (Editor & Chapters)", text_color=TEXT2,
                     font=ctk.CTkFont(size=10)).grid(row=5, column=0, padx=14, pady=(10,2), sticky="w")
        self._voice_var = ctk.StringVar(value=list(VOICES.values())[0])
        ctk.CTkOptionMenu(sb, values=list(VOICES.values()), variable=self._voice_var,
                          command=self._on_voice_change,
                          fg_color=SURFACE2, button_color="#3a3060",
                          button_hover_color="#4a4080",
                          ).grid(row=6, column=0, padx=14, pady=(0,10), sticky="ew")

        ctk.CTkLabel(sb, text="SPEED", text_color=TEXT2,
                     font=ctk.CTkFont(size=10)).grid(row=7, column=0, padx=14, pady=(0,2), sticky="w")
        self._speed_label = ctk.CTkLabel(sb, text="1.0x", text_color=ACCENT,
                                          font=ctk.CTkFont(size=11, weight="bold"))
        self._speed_label.grid(row=7, column=0, padx=14, pady=(0,2), sticky="e")
        self._speed_var = ctk.DoubleVar(value=1.0)
        ctk.CTkSlider(sb, from_=0.5, to=2.0, variable=self._speed_var,
                      command=self._on_speed_change,
                      button_color=ACCENT, button_hover_color="#d990ff",
                      progress_color=ACCENT,
                      ).grid(row=8, column=0, padx=14, pady=(0,12), sticky="ew")

        self._sep(sb, 9)

        ctk.CTkButton(sb, text="\U0001f4c1  Set Output Folder", command=self._choose_output_dir,
                      fg_color="transparent", hover_color=SURFACE2, text_color=TEXT2, height=30,
                      ).grid(row=11, column=0, padx=14, pady=(10,2), sticky="ew")
        self._out_label = ctk.CTkLabel(sb, text=self._output_dir[-32:], text_color=TEXT2,
                                        font=ctk.CTkFont(size=10), wraplength=215)
        self._out_label.grid(row=12, column=0, padx=14, sticky="w")

        self._theme_btn = ctk.CTkButton(sb, text="\u2600  Light Mode", command=self._toggle_theme,
                                         fg_color="transparent", hover_color=SURFACE2,
                                         text_color=TEXT2, height=28)
        self._theme_btn.grid(row=13, column=0, padx=14, pady=(16,12), sticky="ew")

    # ════════════════════════════════════════════════════════════════════════
    # MAIN TABVIEW
    # ════════════════════════════════════════════════════════════════════════

    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=1)

        self._tabview = ctk.CTkTabview(
            main, fg_color=SURFACE,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color="#d990ff",
            segmented_button_unselected_color=SURFACE2,
        )
        self._tabview.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10,0))

        self._build_tab_editor()
        self._build_tab_chapters()
        self._build_tab_page_range()
        self._build_tab_voice_tester()
        self._build_tab_languages()
        self._build_tab_kids()
        self._build_tab_elevenlabs()
        self._build_tab_templates()
        self._build_tab_log()

    # ════════════════════════════════════════════════════════════════════════
    # TAB: EDITOR
    # ════════════════════════════════════════════════════════════════════════

    def _build_tab_editor(self):
        tab = self._tabview.add("\u270f Editor")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(tab, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0,6))

        ctk.CTkLabel(toolbar, text="Emotion tags:", text_color=TEXT2,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0,6))
        for tag, color, border in [
            ("(whisper)",  "#7ab2f2","#3a6080"),("(excited)","#f2c87a","#806030"),
            ("(sad)",      "#7a9af2","#3a3880"),("(shout)",  "#f27a7a","#803030"),
            ("(dramatic)", ACCENT,   "#6a3080"),("(gentle)", ACCENT2, "#2a6858"),
            ("(pause)",    "#888888","#444444"),
        ]:
            ctk.CTkButton(toolbar, text=tag, width=78, height=26,
                          fg_color=SURFACE2, hover_color="#2a2540",
                          text_color=color, border_width=1, border_color=border,
                          font=ctk.CTkFont(size=11),
                          command=lambda t=tag: self._insert_tag(t),
                          ).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="\U0001f9f9 Clean", width=70, height=26,
                      command=self._clean_text,
                      fg_color=SURFACE2, hover_color="#2a2540", text_color=TEXT2,
                      ).pack(side="right", padx=2)

        self._editor = ctk.CTkTextbox(tab, font=ctk.CTkFont("Georgia", 14),
                                       fg_color=SURFACE, border_color="#2a2540", border_width=1)
        self._editor.grid(row=1, column=0, sticky="nsew")
        self._editor.insert("end", TEMPLATES["Fantasy"])

        btn_row = ctk.CTkFrame(tab, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", pady=(8,0))
        ctk.CTkButton(btn_row, text="\u25b6  Preview Voice", width=150, command=self._preview,
                      fg_color=SURFACE2, hover_color="#2a2540",
                      border_color=ACCENT2, border_width=1, text_color=ACCENT2,
                      ).pack(side="left", padx=(0,8))
        ctk.CTkButton(btn_row, text="\U0001f399  Convert to Audio", width=180,
                      command=self._start_convert_editor,
                      fg_color="#7c3aed", hover_color="#9333ea",
                      ).pack(side="left")
        self._progress_bar = ctk.CTkProgressBar(btn_row, mode="determinate",
                                                  progress_color=ACCENT)
        self._progress_bar.set(0)
        self._progress_bar.pack(side="right", padx=(8,0), fill="x", expand=True)

    # ════════════════════════════════════════════════════════════════════════
    # TAB: CHAPTERS
    # ════════════════════════════════════════════════════════════════════════

    def _build_tab_chapters(self):
        tab = self._tabview.add("\U0001f4d1 Chapters")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0,6))
        ctk.CTkButton(top, text="\U0001f50d Auto-detect", width=160,
                      command=self._detect_chapters,
                      fg_color=SURFACE2, hover_color="#2a2540",
                      border_color=ACCENT, border_width=1, text_color=ACCENT,
                      ).pack(side="left", padx=(0,8))
        ctk.CTkButton(top, text="\u2713 Approve All", width=110,
                      command=self._approve_all,
                      fg_color=COL_OK, hover_color="#3a8070", text_color="#a0ffe8",
                      ).pack(side="left", padx=(0,4))
        ctk.CTkButton(top, text="\u2717 Reject All", width=110,
                      command=self._reject_all,
                      fg_color=COL_BAD, hover_color="#8a3030", text_color="#ffaaaa",
                      ).pack(side="left", padx=(0,12))
        self._ch_summary = ctk.CTkLabel(top, text="", text_color=TEXT2,
                                         font=ctk.CTkFont(size=11))
        self._ch_summary.pack(side="left")

        self._chapter_list = ctk.CTkScrollableFrame(tab, fg_color=SURFACE)
        self._chapter_list.grid(row=1, column=0, sticky="nsew")
        self._chapter_list.grid_columnconfigure(0, weight=1)

        bot = ctk.CTkFrame(tab, fg_color="transparent")
        bot.grid(row=2, column=0, sticky="ew", pady=(8,0))
        ctk.CTkButton(bot, text="\U0001f399  Convert Approved",
                      command=self._start_convert_chapters,
                      fg_color="#7c3aed", hover_color="#9333ea",
                      ).pack(side="left")
        self._ch_progress = ctk.CTkProgressBar(bot, mode="determinate",
                                                progress_color=ACCENT)
        self._ch_progress.set(0)
        self._ch_progress.pack(side="right", padx=(8,0), fill="x", expand=True)

    # ════════════════════════════════════════════════════════════════════════
    # TAB: PAGE RANGE
    # ════════════════════════════════════════════════════════════════════════

    def _build_tab_page_range(self):
        tab = self._tabview.add("\U0001f4c4 Page Range")
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(tab, text="Convert a specific page range from the loaded PDF as a single audio file.",
                     text_color=TEXT2, font=ctk.CTkFont(size=12),
                     ).grid(row=0, column=0, sticky="w", pady=(0,14))

        row_frame = ctk.CTkFrame(tab, fg_color="transparent")
        row_frame.grid(row=1, column=0, sticky="w")
        ctk.CTkLabel(row_frame, text="From page:", text_color=TEXT2).pack(side="left", padx=(0,6))
        self._page_from = ctk.CTkEntry(row_frame, width=70, placeholder_text="1")
        self._page_from.pack(side="left", padx=(0,14))
        ctk.CTkLabel(row_frame, text="To page:", text_color=TEXT2).pack(side="left", padx=(0,6))
        self._page_to = ctk.CTkEntry(row_frame, width=70, placeholder_text="end")
        self._page_to.pack(side="left", padx=(0,14))
        ctk.CTkLabel(row_frame, text="Title:", text_color=TEXT2).pack(side="left", padx=(0,6))
        self._page_range_title = ctk.CTkEntry(row_frame, width=200, placeholder_text="Custom Chapter")
        self._page_range_title.pack(side="left")

        self._page_info_label = ctk.CTkLabel(tab, text="Load a PDF first.",
                                              text_color=TEXT2, font=ctk.CTkFont(size=11))
        self._page_info_label.grid(row=2, column=0, sticky="w", pady=(10,0))

        pf = ctk.CTkFrame(tab, fg_color="transparent")
        pf.grid(row=3, column=0, sticky="w", pady=(10,0))
        ctk.CTkButton(pf, text="\U0001f441  Preview Text", width=130,
                      command=self._preview_page_range,
                      fg_color=SURFACE2, hover_color="#2a2540",
                      border_color=ACCENT2, border_width=1, text_color=ACCENT2,
                      ).pack(side="left", padx=(0,8))
        ctk.CTkButton(pf, text="\U0001f399  Convert Range", width=150,
                      command=self._convert_page_range,
                      fg_color="#7c3aed", hover_color="#9333ea",
                      ).pack(side="left")

        self._page_range_preview = ctk.CTkTextbox(tab, height=200,
                                                   font=ctk.CTkFont("Georgia", 13),
                                                   fg_color=SURFACE, border_color="#2a2540",
                                                   border_width=1, state="disabled")
        self._page_range_preview.grid(row=4, column=0, sticky="ew", pady=(12,0))

    # ════════════════════════════════════════════════════════════════════════
    # TAB: VOICE TESTER
    # Type a sentence, click Test on any voice, hear it instantly.
    # ════════════════════════════════════════════════════════════════════════

    def _build_tab_voice_tester(self):
        tab = self._tabview.add("\U0001f3a4 Voice Tester")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(tab,
                     text="Type a sentence below, then click Test on any voice to hear it immediately.\n"
                          "Compare as many voices as you like before choosing one for conversion.",
                     text_color=TEXT2, font=ctk.CTkFont(size=12), justify="left",
                     ).grid(row=0, column=0, sticky="w", pady=(0,10))

        sample_row = ctk.CTkFrame(tab, fg_color="transparent")
        sample_row.grid(row=1, column=0, sticky="ew", pady=(0,10))
        sample_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(sample_row, text="Test sentence:", text_color=TEXT2,
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w")
        self._tester_text = ctk.CTkEntry(sample_row,
                                          placeholder_text='e.g. "Once upon a time..."',
                                          font=ctk.CTkFont(size=13), height=36)
        self._tester_text.grid(row=1, column=0, sticky="ew", pady=(4,0))
        self._tester_text.insert(0, "Hello! I am your audiobook narrator. How do I sound?")

        ctk.CTkLabel(tab, text="Click Test on any voice to preview it:",
                     text_color=TEXT2, font=ctk.CTkFont(size=11),
                     ).grid(row=2, column=0, sticky="w", pady=(0,4))

        voice_scroll = ctk.CTkScrollableFrame(tab, fg_color=SURFACE)
        voice_scroll.grid(row=3, column=0, sticky="nsew")
        voice_scroll.grid_columnconfigure(1, weight=1)
        self._tester_status_labels = {}

        for row_idx, (vid, vlabel) in enumerate(VOICES.items()):
            ctk.CTkLabel(voice_scroll, text=vlabel, font=ctk.CTkFont(size=12),
                         anchor="w").grid(row=row_idx, column=0, padx=(8,12), pady=3, sticky="w")
            status_lbl = ctk.CTkLabel(voice_scroll, text="", text_color=TEXT2,
                                       font=ctk.CTkFont(size=10), width=80)
            status_lbl.grid(row=row_idx, column=1, padx=4)
            self._tester_status_labels[vid] = status_lbl
            ctk.CTkButton(voice_scroll, text="\u25b6 Test", width=70, height=26,
                          fg_color=SURFACE2, hover_color="#2a2540",
                          border_color=ACCENT2, border_width=1, text_color=ACCENT2,
                          command=lambda v=vid, l=vlabel: self._test_single_voice(v, l),
                          ).grid(row=row_idx, column=2, padx=8, pady=3)

    # ════════════════════════════════════════════════════════════════════════
    # TAB: LANGUAGES
    # Convert text or upload PDF/TXT in any supported language.
    # Includes optional translation via deep-translator (no API key needed).
    # ════════════════════════════════════════════════════════════════════════

    def _build_tab_languages(self):
        tab = self._tabview.add("\U0001f30d Languages")
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(3, weight=1)

        # Left: language selector panel
        lang_frame = ctk.CTkFrame(tab, fg_color=SURFACE, width=195)
        lang_frame.grid(row=0, column=0, rowspan=6, sticky="nsew", padx=(0,10))
        lang_frame.grid_propagate(False)
        ctk.CTkLabel(lang_frame, text="LANGUAGE", text_color=TEXT2,
                     font=ctk.CTkFont(size=10)).pack(padx=10, pady=(10,4), anchor="w")

        self._lang_var      = ctk.StringVar(value=list(MULTILANG_VOICES.keys())[0])
        self._lang_btn_refs = {}
        for lang in MULTILANG_VOICES:
            btn = ctk.CTkButton(
                lang_frame, text=lang, anchor="w", height=28,
                fg_color="transparent", hover_color=SURFACE2,
                text_color=TEXT2, font=ctk.CTkFont(size=11),
                command=lambda l=lang: self._select_language(l),
            )
            btn.pack(fill="x", padx=6, pady=1)
            self._lang_btn_refs[lang] = btn

        # Right: voice + upload row
        top_row = ctk.CTkFrame(tab, fg_color="transparent")
        top_row.grid(row=0, column=1, sticky="ew", pady=(0,6))
        top_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(top_row, text="Voice:", text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0,8))
        self._lang_voice_var  = ctk.StringVar()
        self._lang_voice_menu = ctk.CTkOptionMenu(
            top_row, variable=self._lang_voice_var, values=["—"],
            fg_color=SURFACE2, button_color="#3a3060", button_hover_color="#4a4080",
        )
        self._lang_voice_menu.grid(row=0, column=1, sticky="ew", padx=(0,8))
        ctk.CTkButton(top_row, text="\u25b6 Test", width=80,
                      command=self._test_lang_voice,
                      fg_color=SURFACE2, hover_color="#2a2540",
                      border_color=ACCENT2, border_width=1, text_color=ACCENT2,
                      ).grid(row=0, column=2, padx=(0,8))
        ctk.CTkButton(top_row, text="\U0001f4c2 Upload File", width=120,
                      command=self._lang_upload_file,
                      fg_color=SURFACE2, hover_color="#2a2540",
                      border_color=ACCENT, border_width=1, text_color=ACCENT,
                      ).grid(row=0, column=3)

        # File info
        self._lang_file_label = ctk.CTkLabel(tab, text="No file uploaded \u2014 or type/paste below",
                                              text_color=TEXT2, font=ctk.CTkFont(size=11))
        self._lang_file_label.grid(row=1, column=1, sticky="w", pady=(0,4))

        # Translation row
        trans_row = ctk.CTkFrame(tab, fg_color="transparent")
        trans_row.grid(row=2, column=1, sticky="ew", pady=(0,6))
        if TRANSLATION_AVAILABLE:
            ctk.CTkLabel(trans_row,
                         text="Translate text into the selected language before converting:",
                         text_color=TEXT2, font=ctk.CTkFont(size=11)).pack(side="left", padx=(0,10))
            ctk.CTkButton(trans_row, text="\U0001f310 Translate Now", width=150,
                          command=self._lang_translate,
                          fg_color=SURFACE2, hover_color="#2a2540",
                          border_color="#7ab2f2", border_width=1, text_color="#7ab2f2",
                          ).pack(side="left")
        else:
            ctk.CTkLabel(trans_row,
                         text="Translation disabled. Install: pip install deep-translator",
                         text_color="#f27a7a", font=ctk.CTkFont(size=11)).pack(side="left")

        # Text editor
        self._lang_editor = ctk.CTkTextbox(tab, font=ctk.CTkFont(size=14),
                                            fg_color=SURFACE, border_color="#2a2540", border_width=1)
        self._lang_editor.grid(row=3, column=1, sticky="nsew")

        # Bottom row
        bot = ctk.CTkFrame(tab, fg_color="transparent")
        bot.grid(row=4, column=1, sticky="ew", pady=(8,0))
        ctk.CTkLabel(bot, text="Title:", text_color=TEXT2,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0,6))
        self._lang_title = ctk.CTkEntry(bot, width=180, placeholder_text="My Chapter")
        self._lang_title.pack(side="left", padx=(0,12))
        ctk.CTkButton(bot, text="\U0001f399  Convert", width=140,
                      command=self._convert_lang,
                      fg_color="#7c3aed", hover_color="#9333ea",
                      ).pack(side="left")
        self._lang_progress = ctk.CTkProgressBar(bot, mode="determinate",
                                                   progress_color=ACCENT)
        self._lang_progress.set(0)
        self._lang_progress.pack(side="right", padx=(8,0), fill="x", expand=True)

        self._select_language(list(MULTILANG_VOICES.keys())[0])

    # ════════════════════════════════════════════════════════════════════════
    # TAB: KIDS SECTION
    # Stories for children — with language selector, optional translation,
    # upload your own story, kids-friendly voices.
    # ════════════════════════════════════════════════════════════════════════

    def _build_tab_kids(self):
        tab = self._tabview.add("\U0001f9d2 Kids Section")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(tab,
                     text="\U0001f4da Kids Storyteller  \u2014  Stories for children in any language",
                     font=ctk.CTkFont("Georgia", 15, "bold"), text_color=ACCENT,
                     ).grid(row=0, column=0, sticky="w", pady=(0,4))
        ctk.CTkLabel(tab,
                     text="Pick a story or upload your own. Choose language and voice, optionally translate, then convert.\n"
                          "Includes English (Kids) warm voices, all multilingual voices, and Tigrinya via translation.",
                     text_color=TEXT2, font=ctk.CTkFont(size=12), justify="left",
                     ).grid(row=1, column=0, sticky="w", pady=(0,8))

        # ── Row 1: Story + Upload ──────────────────────────────────────────
        r1 = ctk.CTkFrame(tab, fg_color="transparent")
        r1.grid(row=2, column=0, sticky="ew", pady=(0,6))

        ctk.CTkLabel(r1, text="Story:", text_color=TEXT2,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0,6))
        self._kids_story_var = ctk.StringVar(value=list(KIDS_STORIES.keys())[0])
        ctk.CTkOptionMenu(r1, values=list(KIDS_STORIES.keys()),
                          variable=self._kids_story_var,
                          command=self._kids_load_story,
                          fg_color=SURFACE2, button_color="#3a3060", width=200,
                          ).pack(side="left", padx=(0,10))

        ctk.CTkButton(r1, text="\U0001f4c2 Upload Story", width=130,
                      command=self._kids_upload_file,
                      fg_color=SURFACE2, hover_color="#2a2540",
                      border_color=ACCENT, border_width=1, text_color=ACCENT,
                      ).pack(side="left", padx=(0,20))

        self._kids_file_label = ctk.CTkLabel(r1, text="Using built-in story",
                                              text_color=TEXT2, font=ctk.CTkFont(size=11))
        self._kids_file_label.pack(side="left")

        # ── Row 2: Language + Voice + Test ────────────────────────────────
        r2 = ctk.CTkFrame(tab, fg_color="transparent")
        r2.grid(row=3, column=0, sticky="ew", pady=(0,6))

        ctk.CTkLabel(r2, text="Language:", text_color=TEXT2,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0,6))
        lang_keys = ["🇬🇧 English"] + list(MULTILANG_VOICES.keys())
        self._kids_lang_var = ctk.StringVar(value=lang_keys[0])
        ctk.CTkOptionMenu(r2,
                          values=lang_keys,
                          variable=self._kids_lang_var,
                          command=self._kids_on_lang_change,
                          fg_color=SURFACE2, button_color="#3a3060", width=200,
                          ).pack(side="left", padx=(0,10))

        ctk.CTkLabel(r2, text="Voice:", text_color=TEXT2,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0,6))
        self._kids_voice_var  = ctk.StringVar()
        self._kids_voice_menu = ctk.CTkOptionMenu(
            r2, variable=self._kids_voice_var, values=["—"],
            fg_color=SURFACE2, button_color="#3a3060", width=200,
        )
        self._kids_voice_menu.pack(side="left", padx=(0,8))

        ctk.CTkButton(r2, text="\u25b6 Test", width=80,
                      command=self._kids_test_voice,
                      fg_color=SURFACE2, hover_color="#2a2540",
                      border_color=ACCENT2, border_width=1, text_color=ACCENT2,
                      ).pack(side="left", padx=(0,16))

        # Translation button
        if TRANSLATION_AVAILABLE:
            ctk.CTkButton(r2, text="\U0001f310 Translate Story", width=150,
                          command=self._kids_translate,
                          fg_color=SURFACE2, hover_color="#2a2540",
                          border_color="#7ab2f2", border_width=1, text_color="#7ab2f2",
                          ).pack(side="left")
        else:
            ctk.CTkLabel(r2, text="pip install deep-translator  to enable translation",
                         text_color="#f27a7a", font=ctk.CTkFont(size=10)).pack(side="left")

        # ── Story editor ──────────────────────────────────────────────────
        self._kids_editor = ctk.CTkTextbox(tab, font=ctk.CTkFont("Georgia", 14),
                                            fg_color=SURFACE, border_color="#2a2540", border_width=1)
        self._kids_editor.grid(row=4, column=0, sticky="nsew", pady=(0,8))

        # ── Bottom: title + convert ───────────────────────────────────────
        bot = ctk.CTkFrame(tab, fg_color="transparent")
        bot.grid(row=5, column=0, sticky="ew")
        ctk.CTkLabel(bot, text="Output title:", text_color=TEXT2,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0,6))
        self._kids_title = ctk.CTkEntry(bot, width=180, placeholder_text="My Story")
        self._kids_title.pack(side="left", padx=(0,12))
        ctk.CTkButton(bot, text="\U0001f399  Convert Story", width=160,
                      command=self._kids_convert,
                      fg_color="#7c3aed", hover_color="#9333ea",
                      ).pack(side="left")
        self._kids_progress = ctk.CTkProgressBar(bot, mode="determinate",
                                                   progress_color=ACCENT)
        self._kids_progress.set(0)
        self._kids_progress.pack(side="right", padx=(8,0), fill="x", expand=True)

        # Init: English is first option, load first built-in story
        self._kids_on_lang_change("🇬🇧 English")
        self._kids_load_story(list(KIDS_STORIES.keys())[0])

    # ════════════════════════════════════════════════════════════════════════
    # TAB: TEMPLATES
    # ════════════════════════════════════════════════════════════════════════


    # ════════════════════════════════════════════════════════════════════════
    # TAB: ELEVENLABS
    # ════════════════════════════════════════════════════════════════════════

    def _build_tab_elevenlabs(self):
        tab = self._tabview.add("\U0001f3a7 ElevenLabs")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(5, weight=1)

        # Header
        ctk.CTkLabel(tab,
                     text="ElevenLabs Voice Studio",
                     font=ctk.CTkFont("Georgia", 15, "bold"), text_color=ACCENT,
                     ).grid(row=0, column=0, sticky="w", pady=(0,2))
        ctk.CTkLabel(tab,
                     text="Premium AI voices with voice cloning. Requires an ElevenLabs API key (elevenlabs.io).",
                     text_color=TEXT2, font=ctk.CTkFont(size=11), justify="left",
                     ).grid(row=1, column=0, sticky="w", pady=(0,8))

        # Row A: API key
        row_a = ctk.CTkFrame(tab, fg_color="transparent")
        row_a.grid(row=2, column=0, sticky="ew", pady=(0,6))
        row_a.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row_a, text="API Key:", text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0,8))
        self._el_key_entry = ctk.CTkEntry(
            row_a,
            placeholder_text="Paste your ElevenLabs API key here  (Profile → API Key)",
            show="*", font=ctk.CTkFont(size=12))
        self._el_key_entry.grid(row=0, column=1, sticky="ew", padx=(0,8))
        if self._el_api_key:
            self._el_key_entry.insert(0, self._el_api_key)
        ctk.CTkButton(row_a, text="\U0001f504 Load Voices", width=130,
                      command=self._el_load_voices,
                      fg_color=SURFACE2, hover_color="#2a2540",
                      border_color=ACCENT, border_width=1, text_color=ACCENT,
                      ).grid(row=0, column=2)

        # Row B: Voice + model + preview
        row_b = ctk.CTkFrame(tab, fg_color="transparent")
        row_b.grid(row=3, column=0, sticky="ew", pady=(0,6))
        row_b.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row_b, text="Voice:", text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0,8))
        self._el_voice_var  = ctk.StringVar(value="— load voices first —")
        self._el_voice_menu = ctk.CTkOptionMenu(
            row_b, variable=self._el_voice_var, values=["— load voices first —"],
            fg_color=SURFACE2, button_color="#3a3060", button_hover_color="#4a4080",
        )
        self._el_voice_menu.grid(row=0, column=1, sticky="ew", padx=(0,8))
        ctk.CTkLabel(row_b, text="Model:", text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).grid(row=0, column=2, padx=(0,8))
        self._el_model_var = ctk.StringVar(value="eleven_multilingual_v2")
        ctk.CTkOptionMenu(
            row_b, variable=self._el_model_var, width=230,
            values=["eleven_multilingual_v2", "eleven_monolingual_v1",
                    "eleven_turbo_v2", "eleven_turbo_v2_5"],
            fg_color=SURFACE2, button_color="#3a3060",
        ).grid(row=0, column=3, padx=(0,8))
        ctk.CTkButton(row_b, text="\u25b6 Preview", width=90,
                      command=self._el_preview,
                      fg_color=SURFACE2, hover_color="#2a2540",
                      border_color=ACCENT2, border_width=1, text_color=ACCENT2,
                      ).grid(row=0, column=4)

        # Row C: Sliders + clone button
        row_c = ctk.CTkFrame(tab, fg_color="transparent")
        row_c.grid(row=4, column=0, sticky="ew", pady=(0,6))
        ctk.CTkLabel(row_c, text="Stability:", text_color=TEXT2,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0,4))
        self._el_stab_label = ctk.CTkLabel(row_c, text="0.50", text_color=ACCENT,
                                            font=ctk.CTkFont(size=11, weight="bold"), width=38)
        self._el_stab_label.pack(side="left", padx=(0,4))
        self._el_stab_var = ctk.DoubleVar(value=0.5)
        ctk.CTkSlider(row_c, from_=0.0, to=1.0, variable=self._el_stab_var,
                      command=lambda v: self._el_stab_label.configure(text=f"{float(v):.2f}"),
                      button_color=ACCENT, progress_color=ACCENT, width=160,
                      ).pack(side="left", padx=(0,20))
        ctk.CTkLabel(row_c, text="Similarity:", text_color=TEXT2,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0,4))
        self._el_sim_label = ctk.CTkLabel(row_c, text="0.75", text_color=ACCENT,
                                           font=ctk.CTkFont(size=11, weight="bold"), width=38)
        self._el_sim_label.pack(side="left", padx=(0,4))
        self._el_sim_var = ctk.DoubleVar(value=0.75)
        ctk.CTkSlider(row_c, from_=0.0, to=1.0, variable=self._el_sim_var,
                      command=lambda v: self._el_sim_label.configure(text=f"{float(v):.2f}"),
                      button_color=ACCENT, progress_color=ACCENT, width=160,
                      ).pack(side="left", padx=(0,20))
        ctk.CTkButton(row_c, text="\U0001f3a4 Clone a Voice", width=140,
                      command=self._el_open_clone_dialog,
                      fg_color=SURFACE2, hover_color="#2a2540",
                      border_color="#f2c87a", border_width=1, text_color="#f2c87a",
                      ).pack(side="right")

        # Text editor
        self._el_editor = ctk.CTkTextbox(tab, font=ctk.CTkFont("Georgia", 14),
                                          fg_color=SURFACE, border_color="#2a2540", border_width=1)
        self._el_editor.grid(row=5, column=0, sticky="nsew", pady=(0,8))
        self._el_editor.insert("end",
            "Type or paste text here, or use \'Load from PDF/TXT\' below.\n\n"
            "eleven_multilingual_v2 supports 29+ languages — just type in any language.")

        # Bottom bar
        bot = ctk.CTkFrame(tab, fg_color="transparent")
        bot.grid(row=6, column=0, sticky="ew")
        ctk.CTkLabel(bot, text="Title:", text_color=TEXT2,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0,6))
        self._el_title = ctk.CTkEntry(bot, width=180, placeholder_text="Chapter title")
        self._el_title.pack(side="left", padx=(0,10))
        ctk.CTkButton(bot, text="\U0001f4c2 Load PDF/TXT", width=140,
                      command=self._el_load_file,
                      fg_color=SURFACE2, hover_color="#2a2540",
                      border_color=ACCENT, border_width=1, text_color=ACCENT,
                      ).pack(side="left", padx=(0,10))
        ctk.CTkButton(bot, text="\U0001f399  Convert with ElevenLabs", width=200,
                      command=self._el_convert,
                      fg_color="#7c3aed", hover_color="#9333ea",
                      ).pack(side="left")
        self._el_progress = ctk.CTkProgressBar(bot, mode="determinate", progress_color=ACCENT)
        self._el_progress.set(0)
        self._el_progress.pack(side="right", padx=(8,0), fill="x", expand=True)

        # Status label
        self._el_status_label = ctk.CTkLabel(tab, text="", text_color=TEXT2,
                                              font=ctk.CTkFont(size=11))
        self._el_status_label.grid(row=7, column=0, sticky="w", pady=(4,0))

    # ════════════════════════════════════════════════════════════════════════
    # ELEVENLABS: Callbacks
    # ════════════════════════════════════════════════════════════════════════

    def _el_api_key_value(self) -> str:
        key = self._el_key_entry.get().strip()
        if key:
            self._el_api_key = key
        return self._el_api_key

    def _el_load_voices(self):
        key = self._el_api_key_value()
        if not key:
            messagebox.showinfo("API Key",
                                "Enter your ElevenLabs API key first.\n"
                                "Get it at: elevenlabs.io → Profile → API Key")
            return
        self._el_status_label.configure(text="Loading voices...", text_color=ACCENT2)
        self._log("ElevenLabs: loading voices...", "info")

        def run():
            try:
                if not ELEVENLABS_AVAILABLE:
                    raise RuntimeError(
                        "ElevenLabs SDK not installed.\n"
                        "Run:  pip install elevenlabs")
                voices = el_fetch_voices(key)
                self.after(0, lambda v=voices: self._el_on_voices_loaded(v))
            except Exception as exc:
                self.after(0, lambda e=exc: self._el_on_error(str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _el_on_voices_loaded(self, voices: list):
        self._el_voices = voices
        self._el_voice_map = {}
        labels = []
        for v in voices:
            cat   = v.get("category", "premade")
            tag   = "\U0001f3a4" if "cloned" in cat else "\u2728"
            label = f"{tag} {v['name']}"
            self._el_voice_map[label] = v["voice_id"]
            labels.append(label)
        if not labels:
            labels = ["No voices found"]
        self._el_voice_menu.configure(values=labels)
        self._el_voice_var.set(labels[0])
        msg = f"{len(voices)} voice(s) loaded"
        self._el_status_label.configure(text=msg, text_color=ACCENT2)
        self._log(f"ElevenLabs: {msg}", "ok")

    def _el_on_error(self, msg: str):
        self._el_status_label.configure(text=f"Error: {msg[:80]}", text_color="#f27a7a")
        self._el_progress.set(0)
        self._log(f"ElevenLabs error: {msg}", "error")
        messagebox.showerror("ElevenLabs Error", msg)

    def _el_get_voice_id(self) -> str:
        return self._el_voice_map.get(self._el_voice_var.get(), "")

    def _el_get_voice_name(self) -> str:
        label = self._el_voice_var.get()
        return label.lstrip("\u2728\U0001f3a4 ").strip()

    def _el_make_converter(self, doc_title: str = ""):
        return ElevenLabsConverter(
            api_key=self._el_api_key_value(),
            voice_id=self._el_get_voice_id(),
            voice_name=self._el_get_voice_name(),
            model_id=self._el_model_var.get(),
            stability=round(self._el_stab_var.get(), 2),
            similarity_boost=round(self._el_sim_var.get(), 2),
            output_dir=self._output_dir,
            document_title=doc_title or self._doc_title or "Untitled",
            on_log=lambda m, l: self.after(0, lambda msg=m, lv=l: self._log(msg, lv)),
            on_status=lambda m, l: self.after(0, lambda msg=m, lv=l:
                self._el_status_label.configure(
                    text=msg,
                    text_color=ACCENT2 if lv != "error" else "#f27a7a")),
            on_progress=lambda cur, tot, ttl: self.after(
                0, lambda c=cur, t=tot: self._el_progress.set(c / t if t else 0)),
        )

    def _el_preview(self):
        if not self._el_api_key_value():
            messagebox.showinfo("API Key", "Enter your ElevenLabs API key first.")
            return
        if not self._el_get_voice_id():
            messagebox.showinfo("No voice", "Click 'Load Voices' and select one first.")
            return
        text = self._el_editor.get("1.0", "end-1c")[:600]
        self._el_status_label.configure(text="Generating preview...", text_color=ACCENT2)
        self._log(f"ElevenLabs preview: {self._el_get_voice_name()}", "info")

        def run():
            try:
                out = self._el_make_converter().preview(text)
                self.after(0, lambda o=out: self._log(f"ElevenLabs preview: {o.name}", "ok"))
                self._open_path(out)
            except Exception as exc:
                self.after(0, lambda e=exc: self._el_on_error(str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _el_load_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Documents", "*.pdf *.txt"), ("PDF", "*.pdf"), ("Text", "*.txt")])
        if not path:
            return
        p = Path(path)
        try:
            if p.suffix.lower() == ".pdf":
                from core.pdf_extractor import PDFExtractor
                text = PDFExtractor(path).extract_raw()
            else:
                text = open(path, encoding="utf-8", errors="replace").read()
            self._el_editor.delete("1.0", "end")
            self._el_editor.insert("end", text)
            self._el_title.delete(0, "end")
            self._el_title.insert(0, p.stem)
            self._log(f"ElevenLabs tab: loaded {p.name}", "ok")
        except Exception as exc:
            self._log(f"ElevenLabs load error: {exc}", "error")

    def _el_convert(self):
        if self._is_converting:
            messagebox.showinfo("Busy", "A conversion is already running.")
            return
        if not self._el_api_key_value():
            messagebox.showinfo("API Key", "Enter your ElevenLabs API key first.")
            return
        if not self._el_get_voice_id():
            messagebox.showinfo("No voice", "Load voices and select one first.")
            return
        text = self._el_editor.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showinfo("Empty", "Add text or load a file first.")
            return
        title = self._el_title.get().strip() or "Chapter"
        self._is_converting = True
        self._el_progress.set(0)
        self._log(f"ElevenLabs: converting with {self._el_get_voice_name()}", "info")
        self._status_var.set(f"ElevenLabs converting: {title}...")

        def run():
            try:
                conv  = self._el_make_converter(doc_title=title)
                files = conv.convert_chapters(
                    [{"title": title, "text": text, "word_count": len(text.split())}])
                self.after(0, lambda f=files: self._on_done(f, self._el_progress))
            except Exception as exc:
                self.after(0, lambda e=exc: (
                    self._el_on_error(str(e)),
                    setattr(self, "_is_converting", False),
                ))

        threading.Thread(target=run, daemon=True).start()

    def _el_open_clone_dialog(self):
        if not self._el_api_key_value():
            messagebox.showinfo("API Key",
                                "Enter your ElevenLabs API key first.\n"
                                "Voice cloning requires a Creator plan or above.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Clone a Voice — ElevenLabs")
        dialog.geometry("520x320")
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="\U0001f3a4  Clone a Voice",
                     font=ctk.CTkFont(size=16, weight="bold"), text_color=ACCENT,
                     ).pack(pady=(18,4))
        ctk.CTkLabel(dialog,
                     text="Upload 1-5 clean audio samples (MP3/WAV). Minimum ~1 minute total.\n"
                          "Requires ElevenLabs Creator plan or above.",
                     text_color=TEXT2, font=ctk.CTkFont(size=11), justify="center",
                     ).pack(pady=(0,12))

        name_row = ctk.CTkFrame(dialog, fg_color="transparent")
        name_row.pack(fill="x", padx=24, pady=(0,8))
        ctk.CTkLabel(name_row, text="Voice name:", text_color=TEXT2,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0,8))
        clone_name_entry = ctk.CTkEntry(name_row, placeholder_text="My Custom Voice", width=260)
        clone_name_entry.pack(side="left")

        files_label = ctk.CTkLabel(dialog, text="No files selected",
                                    text_color=TEXT2, font=ctk.CTkFont(size=11))
        files_label.pack(pady=(0,6))
        selected_files = []

        def pick_files():
            paths = filedialog.askopenfilenames(
                filetypes=[("Audio", "*.mp3 *.wav *.m4a"), ("MP3", "*.mp3"), ("WAV", "*.wav")])
            if paths:
                selected_files.clear()
                selected_files.extend(paths)
                names = ", ".join(Path(p).name for p in paths)
                files_label.configure(text=f"{len(paths)} file(s): {names[:60]}")

        ctk.CTkButton(dialog, text="\U0001f4c2 Select Audio Files",
                      command=pick_files,
                      fg_color=SURFACE2, hover_color="#2a2540",
                      border_color=ACCENT, border_width=1, text_color=ACCENT,
                      ).pack(pady=(0,8))

        progress_bar = ctk.CTkProgressBar(dialog, mode="indeterminate",
                                           progress_color=ACCENT)

        def do_clone():
            name = clone_name_entry.get().strip()
            if not name:
                messagebox.showinfo("Name required", "Enter a name for the voice.", parent=dialog)
                return
            if not selected_files:
                messagebox.showinfo("No files", "Select at least one audio file.", parent=dialog)
                return
            progress_bar.pack(pady=(4,0), padx=24, fill="x")
            progress_bar.start()
            self._log(f"ElevenLabs: cloning voice '{name}'...", "info")
            key = self._el_api_key_value()

            def run():
                try:
                    result    = el_clone_voice(key, name, selected_files)
                    new_voice = {
                        "voice_id": result.get("voice_id", ""),
                        "name":     name,
                        "category": "cloned",
                        "labels":   {},
                    }
                    def on_done():
                        self._el_voices.insert(0, new_voice)
                        self._el_on_voices_loaded(self._el_voices)
                        self._log(f"Voice cloned: {name}", "ok")
                        dialog.destroy()
                        messagebox.showinfo("Done!",
                            f"Voice '{name}' cloned!\nIt now appears at the top of the voice list.")
                    self.after(0, on_done)
                except Exception as exc:
                    def on_err(e=exc):
                        progress_bar.stop()
                        messagebox.showerror("Clone Failed", str(e), parent=dialog)
                        self._log(f"Clone error: {e}", "error")
                    self.after(0, on_err)

            threading.Thread(target=run, daemon=True).start()

        ctk.CTkButton(dialog, text="\U0001f399  Clone Voice",
                      command=do_clone,
                      fg_color="#7c3aed", hover_color="#9333ea",
                      ).pack(pady=(0,8))

    def _build_tab_templates(self):
        tab = self._tabview.add("\u26a1 Templates")
        tab.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(tab, text="Click any template to load it into the Editor tab.",
                     text_color=TEXT2, font=ctk.CTkFont(size=12),
                     ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,10))
        icons = {"Fantasy":"\U0001f9d9","Horror":"\U0001f47b","Children":"\U0001f43b","News":"\U0001f4f0"}
        for i, (name, text) in enumerate(TEMPLATES.items()):
            card = ctk.CTkFrame(tab, fg_color=SURFACE2, corner_radius=10,
                                border_color="#2a2540", border_width=1)
            card.grid(row=(i//2)+1, column=i%2, padx=8, pady=8, sticky="nsew")
            ctk.CTkLabel(card, text=icons.get(name,"\U0001f4c4"),
                         font=ctk.CTkFont(size=28)).pack(pady=(14,4))
            ctk.CTkLabel(card, text=name,
                         font=ctk.CTkFont(size=14, weight="bold")).pack()
            ctk.CTkButton(card, text="Load into Editor", height=30,
                          command=lambda t=text: self._load_template(t),
                          fg_color="#7c3aed", hover_color="#9333ea",
                          ).pack(pady=(10,14), padx=16, fill="x")

    # ════════════════════════════════════════════════════════════════════════
    # TAB: LOG
    # ════════════════════════════════════════════════════════════════════════

    def _build_tab_log(self):
        tab = self._tabview.add("\U0001f4cb Log")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(tab, text="All activity \u2014 file loads, conversions, voice tests, errors.",
                     text_color=TEXT2, font=ctk.CTkFont(size=11),
                     ).grid(row=0, column=0, sticky="nw", pady=(0,4))
        self._log_box = ctk.CTkTextbox(tab, font=ctk.CTkFont("Courier New", 11),
                                        fg_color=SURFACE, state="disabled")
        self._log_box.grid(row=1, column=0, sticky="nsew")
        ctk.CTkButton(tab, text="Clear Log", command=self._clear_log,
                      fg_color=SURFACE2, hover_color="#2a2540", text_color=TEXT2, height=28,
                      ).grid(row=2, column=0, sticky="e", pady=(6,0))

    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color=SURFACE)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        trans_note = " \u00b7 Translation: ready" if TRANSLATION_AVAILABLE else " \u00b7 Translation: pip install deep-translator"
        self._status_var = ctk.StringVar(value="Ready \u00b7 Edge-TTS connected \u00b7 50+ voices" + trans_note)
        ctk.CTkLabel(bar, textvariable=self._status_var,
                     text_color=TEXT2, font=ctk.CTkFont(size=11)).pack(side="left", padx=14, pady=4)

    # ════════════════════════════════════════════════════════════════════════
    # FILE LOADING
    # ════════════════════════════════════════════════════════════════════════

    def _load_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Documents","*.pdf *.txt"),("PDF","*.pdf"),("Text","*.txt")])
        if not path: return
        p = Path(path)
        self._pdf_path = path
        self._doc_title = p.stem
        self._file_label.configure(text=p.name)
        self._log(f"Loaded: {p.name}", "info")

        if p.suffix.lower() == ".pdf":
            try:
                extractor   = PDFExtractor(path)
                total_pages = extractor.page_count()
                self._page_info_label.configure(text=f"PDF: {total_pages} pages.")
                self._page_to.delete(0,"end")
                self._page_to.insert(0, str(total_pages))
                short = extract_short_story(path)
                if short:
                    self._chapters = [short]
                    self._editor.delete("1.0","end")
                    self._editor.insert("end", short["text"])
                    self._log("Short story \u2014 no split needed","info")
                else:
                    self._chapters = extractor.extract_chapters()
                    for ch in self._chapters: ch["approved"] = True
                    self._log(f"{len(self._chapters)} chapter(s) detected","ok")
                    self._refresh_chapter_list()
                    self._tabview.set("\U0001f4d1 Chapters")
            except ImportError:
                messagebox.showwarning("PyMuPDF missing","pip install pymupdf")
            except Exception as exc:
                self._log(f"Load error: {exc}","error")
        else:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            self._chapters = [{"title":p.stem,"text":text,
                                "word_count":len(text.split()),"approved":True}]
            self._editor.delete("1.0","end")
            self._editor.insert("end", text)
            self._log("Text file loaded","ok")
        self._status_var.set(f"{p.name}  \u00b7  {len(self._chapters)} chapter(s)")

    # ════════════════════════════════════════════════════════════════════════
    # CHAPTER LIST
    # ════════════════════════════════════════════════════════════════════════

    def _refresh_chapter_list(self):
        for w in self._chapter_list.winfo_children(): w.destroy()
        approved = sum(1 for c in self._chapters if c.get("approved",True))
        total    = len(self._chapters)
        self._ch_summary.configure(
            text=f"{approved}/{total} approved  \u00b7  "
                 f"{sum(c.get('word_count',0) for c in self._chapters if c.get('approved',True)):,} words")

        for i, ch in enumerate(self._chapters):
            is_ok = ch.get("approved", True)
            card  = ctk.CTkFrame(self._chapter_list,
                                 fg_color=COL_OK if is_ok else COL_BAD,
                                 corner_radius=8, border_color="#2a2540", border_width=1)
            card.grid(row=i, column=0, sticky="ew", padx=4, pady=3)
            card.grid_columnconfigure(3, weight=1)

            ctk.CTkLabel(card, text=f"Ch.{i+1:02d}", font=ctk.CTkFont(size=11),
                         text_color=TEXT2, width=42).grid(row=0,column=0,padx=(8,4),pady=6)
            ctk.CTkButton(card, text="\u2713", width=32, height=26,
                          fg_color="#1a5040" if is_ok else SURFACE2,
                          hover_color="#2a7060", text_color="#7af2d4",
                          command=lambda idx=i: self._set_chapter_approved(idx,True),
                          ).grid(row=0,column=1,padx=(0,2),pady=4)
            ctk.CTkButton(card, text="\u2717", width=32, height=26,
                          fg_color="#501010" if not is_ok else SURFACE2,
                          hover_color="#702020", text_color="#f27a7a",
                          command=lambda idx=i: self._set_chapter_approved(idx,False),
                          ).grid(row=0,column=2,padx=(0,6),pady=4,sticky="w")
            ctk.CTkLabel(card, text=ch.get("title","Untitled"),
                         font=ctk.CTkFont(size=13,weight="bold"),
                         anchor="w").grid(row=0,column=3,sticky="ew",padx=4)
            dur = estimate_duration(ch.get("text",""))
            wc  = ch.get("word_count", len(ch.get("text","").split()))
            pg  = ch.get("start_page","?")
            ctk.CTkLabel(card, text=f"p.{pg}  \u00b7  {wc:,} words  \u00b7  ~{dur}",
                         text_color=TEXT2, font=ctk.CTkFont(size=11), anchor="w").grid(
                row=1,column=1,columnspan=4,sticky="ew",padx=6,pady=(0,6))
            ctk.CTkButton(card, text="Edit", width=44, height=24,
                          fg_color="transparent", text_color=ACCENT,
                          command=lambda c=ch: self._edit_chapter(c),
                          ).grid(row=0,column=4,padx=8)

    def _set_chapter_approved(self, idx, value):
        self._chapters[idx]["approved"] = value
        self._refresh_chapter_list()

    def _approve_all(self):
        for ch in self._chapters: ch["approved"] = True
        self._refresh_chapter_list()

    def _reject_all(self):
        for ch in self._chapters: ch["approved"] = False
        self._refresh_chapter_list()

    def _detect_chapters(self):
        if not self._pdf_path:
            messagebox.showinfo("No PDF","Load a PDF file first.")
            return
        try:
            extractor = PDFExtractor(self._pdf_path)
            self._chapters = extractor.extract_chapters()
            for ch in self._chapters: ch["approved"] = True
            self._log(f"Detected {len(self._chapters)} chapter(s)","ok")
            self._refresh_chapter_list()
        except Exception as exc:
            self._log(f"Detection error: {exc}","error")

    def _edit_chapter(self, chapter):
        self._editor.delete("1.0","end")
        self._editor.insert("end", chapter.get("text",""))
        self._tabview.set("\u270f Editor")

    # ════════════════════════════════════════════════════════════════════════
    # PAGE RANGE
    # ════════════════════════════════════════════════════════════════════════

    def _get_page_range_inputs(self):
        if not self._pdf_path:
            messagebox.showinfo("No PDF","Load a PDF first.")
            return None,None,None
        try:
            extractor = PDFExtractor(self._pdf_path)
            total     = extractor.page_count()
            fv        = self._page_from.get().strip()
            tv        = self._page_to.get().strip()
            start     = int(fv) if fv.isdigit() else 1
            end       = int(tv) if tv.isdigit() else total
            title     = self._page_range_title.get().strip() or f"Pages {start}-{end}"
            return start,end,title
        except Exception as exc:
            self._log(f"Page range error: {exc}","error")
            return None,None,None

    def _preview_page_range(self):
        start,end,title = self._get_page_range_inputs()
        if start is None: return
        try:
            text = PDFExtractor(self._pdf_path).extract_page_range(start,end)
            dur  = estimate_duration(text)
            wc   = len(text.split())
            self._page_range_preview.configure(state="normal")
            self._page_range_preview.delete("1.0","end")
            self._page_range_preview.insert("end",
                f"[Pages {start}-{end}  \u00b7  {wc:,} words  \u00b7  ~{dur}]\n\n{text[:2000]}...")
            self._page_range_preview.configure(state="disabled")
            self._log(f"Range preview: pages {start}-{end}, {wc} words, ~{dur}","info")
        except Exception as exc:
            self._log(f"Preview error: {exc}","error")

    def _convert_page_range(self):
        start,end,title = self._get_page_range_inputs()
        if start is None: return
        try:
            text = PDFExtractor(self._pdf_path).extract_page_range(start,end)
            self._run_conversion(
                [{"title":title,"text":text,"word_count":len(text.split()),"approved":True}],
                self._progress_bar)
        except Exception as exc:
            self._log(f"Conversion error: {exc}","error")

    # ════════════════════════════════════════════════════════════════════════
    # VOICE TESTER callbacks
    # ════════════════════════════════════════════════════════════════════════

    def _test_single_voice(self, voice_id, voice_label):
        text = self._tester_text.get().strip() or "Hello! How do I sound?"
        lbl  = self._tester_status_labels.get(voice_id)
        if lbl: lbl.configure(text="Playing...", text_color=ACCENT2)
        self._log(f"Testing: {voice_label}","info")
        def run():
            try:
                conv = AudiobookConverter(voice=voice_id,
                                          speed=round(self._speed_var.get(),2),
                                          output_dir=self._output_dir,
                                          document_title="voice_test",
                                          on_log=lambda m,l: self.after(0, lambda msg=m,lv=l: self._log(msg,lv)))
                out = conv.preview(text, voice=voice_id)
                self.after(0, lambda: lbl.configure(text="Ready",text_color=ACCENT2) if lbl else None)
                self.after(0, lambda: self._log(f"Preview: {out.name}","ok"))
                self._open_path(out)
            except Exception as exc:
                self.after(0, lambda e=exc: self._log(f"Test failed: {e}","error"))
                self.after(0, lambda: lbl.configure(text="Failed",text_color="#f27a7a") if lbl else None)
        threading.Thread(target=run, daemon=True).start()

    # ════════════════════════════════════════════════════════════════════════
    # LANGUAGES tab callbacks
    # ════════════════════════════════════════════════════════════════════════

    def _select_language(self, lang):
        self._lang_var.set(lang)
        for l, btn in self._lang_btn_refs.items():
            btn.configure(text_color=ACCENT if l==lang else TEXT2,
                          fg_color=SURFACE2 if l==lang else "transparent")
        voices = MULTILANG_VOICES.get(lang, [])
        labels = [label for _,label in voices]
        self._lang_voice_menu.configure(values=labels if labels else ["—"])
        if labels: self._lang_voice_var.set(labels[0])
        sample = LANG_SAMPLES.get(lang, "Enter text here...")
        self._lang_editor.delete("1.0","end")
        self._lang_editor.insert("end", sample)
        self._lang_file_label.configure(text="No file uploaded \u2014 or type/paste below")
        self._lang_pdf_path = None

    def _lang_upload_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Documents","*.pdf *.txt"),("PDF","*.pdf"),("Text","*.txt")])
        if not path: return
        p = Path(path)
        self._lang_pdf_path = path
        self._lang_file_label.configure(text=f"File: {p.name}")
        self._log(f"Languages tab: loaded {p.name}","info")
        try:
            text = PDFExtractor(path).extract_raw() if p.suffix.lower()==".pdf" else \
                   open(path, encoding="utf-8", errors="replace").read()
            self._lang_editor.delete("1.0","end")
            self._lang_editor.insert("end", text)
            self._lang_title.delete(0,"end")
            self._lang_title.insert(0, p.stem)
            self._log(f"Languages tab: {len(text.split()):,} words","ok")
        except Exception as exc:
            self._log(f"Upload error: {exc}","error")

    def _get_lang_voice_id(self):
        lang  = self._lang_var.get()
        label = self._lang_voice_var.get()
        for vid,vlabel in MULTILANG_VOICES.get(lang,[]):
            if vlabel == label: return vid
        return "en-US-AriaNeural"

    def _test_lang_voice(self):
        voice = self._get_lang_voice_id()
        text  = self._lang_editor.get("1.0","end-1c")[:300]
        self._log(f"Testing language voice: {voice}","info")
        def run():
            try:
                conv = AudiobookConverter(voice=voice,
                                          speed=round(self._speed_var.get(),2),
                                          output_dir=self._output_dir,
                                          document_title="lang_preview",
                                          on_log=lambda m,l: self.after(0, lambda msg=m,lv=l: self._log(msg,lv)))
                out = conv.preview(text, voice=voice)
                self.after(0, lambda: self._log(f"Preview: {out.name}","ok"))
                self._open_path(out)
            except Exception as exc:
                self.after(0, lambda e=exc: self._log(f"Test failed: {e}","error"))
        threading.Thread(target=run, daemon=True).start()

    def _lang_translate(self):
        """Translate the text in the Languages editor into the selected language."""
        if not TRANSLATION_AVAILABLE:
            messagebox.showinfo("Translation unavailable","pip install deep-translator")
            return
        lang   = self._lang_var.get()
        target = LANG_TO_TRANSLATE_CODE.get(lang)
        if not target:
            messagebox.showinfo("Not supported",
                                f"Auto-translation to {lang} is not available.\n"
                                "You can type or paste text in that language directly.")
            return
        text = self._lang_editor.get("1.0","end-1c").strip()
        if not text:
            messagebox.showinfo("Empty","No text to translate.")
            return
        self._log(f"Translating to {lang}...","info")
        self._status_var.set(f"Translating to {lang}...")
        def run():
            try:
                translated = GoogleTranslator(source="auto", target=target).translate(text)
                self.after(0, lambda: self._lang_editor.delete("1.0","end"))
                self.after(0, lambda: self._lang_editor.insert("end", translated))
                self.after(0, lambda: self._log(f"Translation to {lang} done","ok"))
                self.after(0, lambda: self._status_var.set("Translation complete"))
            except Exception as exc:
                self.after(0, lambda e=exc: self._log(f"Translation error: {e}","error"))
                self.after(0, lambda: self._status_var.set("Translation failed"))
        threading.Thread(target=run, daemon=True).start()

    def _convert_lang(self):
        text  = self._lang_editor.get("1.0","end-1c").strip()
        voice = self._get_lang_voice_id()
        title = self._lang_title.get().strip() or "Chapter"
        if not text:
            messagebox.showinfo("Empty","Add text or upload a file first.")
            return
        self._run_conversion(
            [{"title":title,"text":text,"word_count":len(text.split()),"approved":True}],
            self._lang_progress, voice_override=voice, doc_title=title)

    # ════════════════════════════════════════════════════════════════════════
    # KIDS SECTION callbacks
    # ════════════════════════════════════════════════════════════════════════

    def _kids_load_story(self, story_name):
        text = KIDS_STORIES.get(story_name,"")
        self._kids_editor.delete("1.0","end")
        self._kids_editor.insert("end", text)
        self._kids_title.delete(0,"end")
        self._kids_title.insert(0, story_name)
        self._kids_file_label.configure(text=f"Built-in: {story_name}")
        self._kids_pdf_path = None

    def _kids_upload_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Documents","*.pdf *.txt"),("PDF","*.pdf"),("Text","*.txt")])
        if not path: return
        p = Path(path)
        self._kids_pdf_path = path
        self._kids_file_label.configure(text=f"File: {p.name}")
        self._log(f"Kids section: loaded {p.name}","info")
        try:
            text = PDFExtractor(path).extract_raw() if p.suffix.lower()==".pdf" else \
                   open(path, encoding="utf-8", errors="replace").read()
            self._kids_editor.delete("1.0","end")
            self._kids_editor.insert("end", text)
            self._kids_title.delete(0,"end")
            self._kids_title.insert(0, p.stem)
            self._log(f"Kids: {len(text.split()):,} words","ok")
        except Exception as exc:
            self._log(f"Kids upload error: {exc}","error")

    def _kids_on_lang_change(self, lang):
        """Update the Kids voice dropdown when a language is selected.
        English shows the curated kids-friendly voices.
        All other languages show the voices from MULTILANG_VOICES.
        """
        self._kids_lang_var.set(lang)
        if lang == "🇬🇧 English":
            labels = list(KIDS_VOICES.values())
        else:
            voices = MULTILANG_VOICES.get(lang, [])
            labels = [label for _, label in voices]
            if not labels:
                labels = list(KIDS_VOICES.values())
        self._kids_voice_menu.configure(values=labels)
        self._kids_voice_var.set(labels[0])

    def _kids_get_voice_id(self):
        lang  = self._kids_lang_var.get()
        label = self._kids_voice_var.get()
        # English: look up in KIDS_VOICES
        if lang == "🇬🇧 English":
            for vid, vlabel in KIDS_VOICES.items():
                if vlabel == label: return vid
            return "en-US-AriaNeural"
        # Other languages: look up in MULTILANG_VOICES
        for vid, vlabel in MULTILANG_VOICES.get(lang, []):
            if vlabel == label: return vid
        # Final fallback
        for vid, vlabel in KIDS_VOICES.items():
            if vlabel == label: return vid
        return "en-US-AriaNeural"

    def _kids_test_voice(self):
        voice = self._kids_get_voice_id()
        text  = self._kids_editor.get("1.0","end-1c")[:300]
        self._log(f"Kids voice test: {voice}","info")
        def run():
            try:
                conv = AudiobookConverter(voice=voice,
                                          speed=round(self._speed_var.get(),2),
                                          output_dir=self._output_dir,
                                          document_title="kids_preview",
                                          on_log=lambda m,l: self.after(0, lambda msg=m,lv=l: self._log(msg,lv)))
                out = conv.preview(text, voice=voice)
                self.after(0, lambda: self._log(f"Kids preview: {out.name}","ok"))
                self._open_path(out)
            except Exception as exc:
                self.after(0, lambda e=exc: self._log(f"Kids test failed: {e}","error"))
        threading.Thread(target=run, daemon=True).start()

    def _kids_translate(self):
        """Translate the kids story into the selected language."""
        if not TRANSLATION_AVAILABLE:
            messagebox.showinfo("Translation unavailable","pip install deep-translator")
            return
        lang   = self._kids_lang_var.get()
        target = LANG_TO_TRANSLATE_CODE.get(lang)
        if not target:
            messagebox.showinfo("Not supported",
                                f"Auto-translation to {lang} is not yet supported.\n"
                                "Paste the translated text directly into the editor.")
            return
        text = self._kids_editor.get("1.0","end-1c").strip()
        if not text:
            messagebox.showinfo("Empty","Load or type a story first.")
            return
        self._log(f"Kids: translating story to {lang}...","info")
        self._status_var.set(f"Translating story to {lang}...")
        def run():
            try:
                translated = GoogleTranslator(source="auto", target=target).translate(text)
                self.after(0, lambda: self._kids_editor.delete("1.0","end"))
                self.after(0, lambda: self._kids_editor.insert("end", translated))
                self.after(0, lambda: self._log(f"Kids story translated to {lang}","ok"))
                self.after(0, lambda: self._status_var.set("Translation complete"))
            except Exception as exc:
                self.after(0, lambda e=exc: self._log(f"Kids translation error: {e}","error"))
                self.after(0, lambda: self._status_var.set("Translation failed"))
        threading.Thread(target=run, daemon=True).start()

    def _kids_convert(self):
        text  = self._kids_editor.get("1.0","end-1c").strip()
        voice = self._kids_get_voice_id()
        title = self._kids_title.get().strip() or "Kids Story"
        if not text:
            messagebox.showinfo("Empty","Load a story or type one first.")
            return
        self._run_conversion(
            [{"title":title,"text":text,"word_count":len(text.split()),"approved":True}],
            self._kids_progress, voice_override=voice, doc_title=title)

    # ════════════════════════════════════════════════════════════════════════
    # CONVERSION ENGINE
    # ════════════════════════════════════════════════════════════════════════

    def _start_convert_editor(self):
        text = self._editor.get("1.0","end-1c").strip()
        if not text:
            messagebox.showinfo("Empty","Add text in the editor first.")
            return
        self._run_conversion(
            [{"title":self._doc_title or "Audiobook","text":text,
              "word_count":len(text.split()),"approved":True}],
            self._progress_bar)

    def _start_convert_chapters(self):
        approved = [ch for ch in self._chapters if ch.get("approved",True)]
        if not approved:
            messagebox.showinfo("None approved","Mark at least one chapter as approved first.")
            return
        self._run_conversion(approved, self._ch_progress)

    def _run_conversion(self, chapters, progress_bar,
                        voice_override=None, doc_title=None):
        if self._is_converting:
            messagebox.showinfo("Busy","A conversion is already running.")
            return
        self._is_converting = True
        progress_bar.set(0)
        total = len(chapters)
        self._log(f"Starting: {total} chapter(s)","info")
        self._status_var.set("Validating voice...")

        voice = voice_override or self._label_to_voice_name(self._voice_var.get())
        speed = round(self._speed_var.get(), 2)
        doc   = doc_title or self._doc_title or "Untitled"
        char_voices = {r["name"].get(): self._label_to_voice_name(r["voice"].get())
                       for r in self._char_rows if r["name"].get()}

        def on_progress(current, tot, title):
            pct = current/tot if tot else 0
            self.after(0, lambda: progress_bar.set(pct))
            self.after(0, lambda: self._status_var.set(f"Converting {current}/{tot}: {title}"))

        def on_status(msg, level):
            self.after(0, lambda m=msg,lv=level: self._handle_status(m,lv))

        def run():
            try:
                conv = AudiobookConverter(
                    voice=voice, speed=speed, output_dir=self._output_dir,
                    document_title=doc, character_voices=char_voices,
                    on_progress=on_progress,
                    on_log=lambda m,l: self.after(0, lambda msg=m,lv=l: self._log(msg,lv)),
                    on_status=on_status,
                )
                files = conv.convert_chapters(chapters, playlist=True)
                self.after(0, lambda: self._on_done(files, progress_bar))
            except Exception as exc:
                self.after(0, lambda e=exc: self._on_error(e, progress_bar))

        threading.Thread(target=run, daemon=True).start()

    def _on_done(self, files, progress_bar):
        self._is_converting = False
        progress_bar.set(1.0)
        self._status_var.set(f"Done! {len(files)} file(s) saved.")
        self._log(f"Complete: {len(files)} audio file(s)","ok")
        if messagebox.askyesno("Done!",f"{len(files)} file(s) converted.\nOpen output folder?"):
            self._open_path(self._output_dir)

    def _on_error(self, exc, progress_bar):
        self._is_converting = False
        self._status_var.set("Conversion failed \u2014 see Log tab")
        self._log(f"ERROR: {exc}","error")
        msg = str(exc)
        if "voice" in msg.lower() or "not available" in msg.lower():
            messagebox.showerror("Voice Not Working",f"{msg}\n\nPlease select a different voice.")
        else:
            messagebox.showerror("Conversion Failed", msg)

    def _handle_status(self, msg, level):
        self._log(msg, level)
        self._status_var.set(msg)
        if level=="error" and ("not working" in msg.lower() or "unavailable" in msg.lower()):
            messagebox.showerror("Voice Not Available",
                                 msg+"\n\nPlease choose a different voice.")

    def _preview(self):
        text  = self._editor.get("1.0","end-1c")[:600]
        voice = self._label_to_voice_name(self._voice_var.get())
        speed = round(self._speed_var.get(),2)
        short = voice_short_name(voice)
        self._log(f"Preview: {short}...","info")
        self._status_var.set(f"Generating preview \u2014 {short}...")
        def on_status(msg, level):
            self.after(0, lambda m=msg,lv=level: self._handle_status(m,lv))
        def run():
            try:
                conv = AudiobookConverter(voice=voice, speed=speed,
                                          output_dir=self._output_dir,
                                          document_title=self._doc_title or "preview",
                                          on_log=lambda m,l: self.after(0, lambda msg=m,lv=l: self._log(msg,lv)),
                                          on_status=on_status)
                out = conv.preview(text, voice=voice)
                self.after(0, lambda o=out: self._log(f"Preview ready: {o.name}","ok"))
                self._open_path(out)
            except Exception as exc:
                self.after(0, lambda e=exc: self._on_preview_error(e))
        threading.Thread(target=run, daemon=True).start()

    def _on_preview_error(self, exc):
        msg = str(exc)
        self._log(f"Preview error: {msg}","error")
        self._status_var.set("Preview failed")
        messagebox.showerror("Preview Failed", f"{msg}\n\nTry a different voice.")

    # ════════════════════════════════════════════════════════════════════════
    # MISC
    # ════════════════════════════════════════════════════════════════════════

    def _insert_tag(self, tag):
        self._editor.insert("insert",f"{tag} ")
        self._editor.focus()

    def _clean_text(self):
        text = self._editor.get("1.0","end-1c")
        self._editor.delete("1.0","end")
        self._editor.insert("end", TextCleaner().clean(text))
        self._log("Text cleaned","ok")

    def _load_template(self, text):
        self._editor.delete("1.0","end")
        self._editor.insert("end", text)
        self._tabview.set("\u270f Editor")
        self._log("Template loaded","info")

    def _on_voice_change(self, _):
        self._log(f"Voice: {self._voice_var.get()}","info")

    def _on_speed_change(self, val):
        self._speed_label.configure(text=f"{float(val):.1f}x")

    def _choose_output_dir(self):
        d = filedialog.askdirectory(initialdir=self._output_dir)
        if d:
            self._output_dir = d
            self._out_label.configure(text=d[-32:])

    def _toggle_theme(self):
        new = "light" if ctk.get_appearance_mode()=="Dark" else "dark"
        ctk.set_appearance_mode(new)
        self._theme_btn.configure(text="\U0001f319  Dark Mode" if new=="light" else "\u2600  Light Mode")

    def _clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0","end")
        self._log_box.configure(state="disabled")

    def _log(self, message, level="info"):
        icons = {"ok":"\u2713","info":"\u2139","warn":"\u26a0","error":"\u2717"}
        line  = f"[{time.strftime('%H:%M:%S')}] {icons.get(level,'.')} {message}\n"
        self._log_box.configure(state="normal")
        self._log_box.insert("end", line)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    @staticmethod
    def _label_to_voice_name(label):
        for k,v in VOICES.items():
            if v==label: return k
        return "en-US-AriaNeural"

    @staticmethod
    def _open_path(path):
        import subprocess
        p = str(path)
        if sys.platform=="darwin":    subprocess.Popen(["open",p])
        elif sys.platform=="win32":   os.startfile(p)
        else:                         subprocess.Popen(["xdg-open",p])

    @staticmethod
    def _sep(parent, row):
        ctk.CTkFrame(parent, height=1, fg_color="#2a2540").grid(
            row=row, column=0, padx=14, pady=4, sticky="ew")
