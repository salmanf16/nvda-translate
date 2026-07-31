# *-* coding: utf-8 *-*
import os, sys, codecs, re
import globalVars
import globalPluginHandler, logHandler, scriptHandler
import api
import ui, wx, gui
import config
import speech
from speech.types import SpeechSequence
from speech.priorities import Spri
import json
curDir = os.path.abspath(os.path.dirname(__file__))
logHandler.log.info("Importing modules from %s" % curDir)
sys.path.insert(0, curDir)
import mtranslate
import libretrans
import lingva
import deepl
import openai_api
import gemini_api
import bing_api
import openrouter_api
import addonHandler, languageHandler

addonHandler.initTranslation()

import threading

ENGINE_GOOGLE = "google"
ENGINE_LINGVA = "lingva"
ENGINE_LIBRETRANSLATE = "libretranslate"
ENGINE_DEEPL = "deepl"
ENGINE_OPENAI = "openai"
ENGINE_GEMINI = "gemini"
ENGINE_LOCAL = "local"
ENGINE_BING = "bing"
ENGINE_OPENROUTER = "openrouter"

config.conf.spec["translate"] = {
	"engine": 'string(default="google")',
	"lingvaUrl": 'string(default="https://lingva.ml")',
	"libretranslateUrl": 'string(default="https://libretranslate.com")',
	"libretranslateApiKey": 'string(default="")',
	"deeplApiKey": 'string(default="")',
	"openaiApiKey": 'string(default="")',
	"openaiModel": 'string(default="gpt-5.4-mini")',
	"openaiModelsList": 'string(default="gpt-5.4-mini,gpt-5.5-pro")',
	"geminiApiKey": 'string(default="")',
	"geminiModel": 'string(default="gemini-3.5-flash")',
	"geminiModelsList": 'string(default="gemini-3.5-flash,gemini-3.5-pro")',
	"bingApiKey": 'string(default="")',
	"bingRegion": 'string(default="")',
	"openrouterApiKey": 'string(default="")',
	"openrouterModel": 'string(default="deepseek/deepseek-chat")',
	"openrouterModelsList": 'string(default="deepseek/deepseek-chat,google/gemini-2.5-flash")',
	"localTargetLang": 'string(default="")',
	"localModelId": 'string(default="")',
	"localDevice": 'string(default="auto")',
	"modelsDrive": 'string(default="")',
	"localIdleTimeout": 'integer(default=5)',
	"localBeamSize": 'string(default="quality")',
}

_translationCache = {}
_cacheLock = threading.Lock()
_cacheModified = False

def update_cache(appTable, key, value):
        global _cacheModified, _cacheLock
        with _cacheLock:
                if appTable.get(key) != value:
                        appTable[key] = value
                        _cacheModified = True

_nvdaSpeak = None
_gpObject = None
_lastError = 0
_enableTranslation = False
_lastTranslatedText = None
_lastTranslatedTextTime = 0
_localTranslateWarningShown = False




def detect_source_lang(text):
	"""Cheap script based guess of the source language.

	This is only a hint, used to decide whether a line is already in the target language
	and may therefore be skipped. It must not be handed to the translation engine as the
	source language: a script does not identify a language. Han characters are shared by
	Chinese and Japanese, the Arabic script by Arabic, Persian and Urdu, Cyrillic by
	Russian, Ukrainian and Bulgarian. The engine's own auto detection is used instead.
	"""
	if not text:
		return "auto"
	# Japanese Hiragana and Katakana
	if re.search(r'[\u3040-\u30ff]', text):
		return "ja"
	# Korean Hangul
	if re.search(r'[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]', text):
		return "ko"
	# CJK Unified Ideographs with no kana present: Chinese is by far the most likely
	if re.search(r'[\u4e00-\u9fff]', text):
		return "zh"
	# Arabic Script (Arabic, Persian, Urdu)
	if re.search(r'[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]', text):
		return "ar"
	# Cyrillic Script (Russian, Ukrainian, Bulgarian, etc.)
	if re.search(r'[\u0400-\u04ff\u0500-\u052f]', text):
		return "ru"
	# Greek Script
	if re.search(r'[\u0370-\u03ff\u1f00-\u1fff]', text):
		return "el"
	# Hebrew Script
	if re.search(r'[\u0590-\u05ff]', text):
		return "he"
	# Thai Script
	if re.search(r'[\u0e00-\u0e7f]', text):
		return "th"
	# Devanagari Script (Hindi, Marathi, etc.)
	if re.search(r'[\u0900-\u097f]', text):
		return "hi"
	# Bengali Script
	if re.search(r'[\u0980-\u09ff]', text):
		return "bn"
	# Tamil Script
	if re.search(r'[\u0b80-\u0bff]', text):
		return "ta"
	# Telugu Script
	if re.search(r'[\u0c00-\u0c7f]', text):
		return "te"
	# Kannada Script
	if re.search(r'[\u0c80-\u0cff]', text):
		return "kn"
	# Malayalam Script
	if re.search(r'[\u0d00-\u0d7f]', text):
		return "ml"
	# Gujarati Script
	if re.search(r'[\u0a80-\u0aff]', text):
		return "gu"
	# Gurmukhi / Punjabi Script
	if re.search(r'[\u0a00-\u0a7f]', text):
		return "pa"

	# If the text is entirely ASCII and has alphabetic letters, return "en"
	try:
		if text.isascii() and any(c.isalpha() for c in text):
			return "en"
	except AttributeError:
		pass

	return "auto"


def _execute_engine_translation(text, source_lang="auto"):
        global _gpObject, _localTranslateWarningShown
        engine = config.conf["translate"]["engine"]
        target_lang = config.conf["translate"]["localTargetLang"]
        if not target_lang:
                target_lang = _gpObject.language

        # If source_lang was detected as "en" solely because the text is ASCII, convert to "auto"
        # so the translation engine can auto-detect Spanish, French, German, Italian, Portuguese, etc.
        if source_lang == "en":
                source_lang = "auto"

        if engine == ENGINE_LINGVA:
                url = config.conf["translate"]["lingvaUrl"]
                return lingva.translate(text, target_lang, source_language=source_lang, instance_url=url)
        elif engine == ENGINE_LIBRETRANSLATE:
                url = config.conf["translate"]["libretranslateUrl"]
                api_key = config.conf["translate"]["libretranslateApiKey"]
                return libretrans.translate(text, target_lang, source_language=source_lang, url=url, api_key=api_key)
        elif engine == ENGINE_DEEPL:
                api_key = config.conf["translate"]["deeplApiKey"]
                return deepl.translate(text, target_lang, api_key)
        elif engine == ENGINE_OPENAI:
                api_key = config.conf["translate"]["openaiApiKey"]
                model = config.conf["translate"]["openaiModel"]
                return openai_api.translate(text, target_lang, api_key, model=model)
        elif engine == ENGINE_GEMINI:
                api_key = config.conf["translate"]["geminiApiKey"]
                model = config.conf["translate"]["geminiModel"]
                return gemini_api.translate(text, target_lang, api_key, model=model)
        elif engine == ENGINE_BING:
                api_key = config.conf["translate"]["bingApiKey"]
                region = config.conf["translate"]["bingRegion"]
                return bing_api.translate(text, target_lang, api_key, region=region)
        elif engine == ENGINE_OPENROUTER:
                api_key = config.conf["translate"]["openrouterApiKey"]
                model = config.conf["translate"]["openrouterModel"]
                return openrouter_api.translate(text, target_lang, api_key, model=model)
        elif engine == ENGINE_LOCAL:
                return mtranslate.translate(text, target_lang, from_language=source_lang)
        else:
                return mtranslate.translate(text, target_lang, from_language=source_lang)


def normalize_placeholders(translated_text):
        if not translated_text:
                return translated_text
        import re
        # Match curly, square, or round brackets containing English, Arabic, or Persian digits
        pattern = r'([\{\[\(])\s*([0-9\u0660-\u0669\u06f0-\u06f9]+)\s*([\}\]\)])'
        
        digit_map = {
                '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4', '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
                '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۵': '5', '۶': '6', '۷': '7', '۸': '8', '٩': '9'
        }
        
        def replace_placeholder(match):
                digit_str = match.group(2)
                english_digit = "".join(digit_map.get(c, c) for c in digit_str)
                return "{" + english_digit + "}"
                
        normalized = re.sub(pattern, replace_placeholder, translated_text)
        normalized = re.sub(r'\{\s*(\d+)\s*\}', r'{\1}', normalized)
        return normalized


def _placeholders_survived(translated_template, count):
        """True if every {0}..{count-1} placeholder is still present in the translated template.

        Engines sometimes drop, merge or reorder the braces. When that happens safe_format()
        appends the numbers to the end of the sentence, which reads badly, so the caller
        falls back to translating the untouched line instead.
        """
        if not count:
                return True
        if not translated_template:
                return False
        for i in range(count):
                if ("{%d}" % i) not in translated_template:
                        return False
        return True


def safe_format(template_str, numbers):
        if not numbers:
                return template_str
        result = template_str
        for i, num in enumerate(numbers):
                placeholder = "{%d}" % i
                if placeholder in result:
                        result = result.replace(placeholder, num)
                else:
                        result += " (%s)" % num
        return result



def translate_single_line_core(line, appTable, target_lang):
        stripped_line = line.strip()
        if not stripped_line:
                return line



        # Rule 1: Skip translation entirely if the line contains no alphabetic characters.
        if not any(c.isalpha() for c in stripped_line):
                return line

        # Rule 2: Skip translation entirely if the line contains exactly one Latin character (e.g. isolated keys like "g" or "A").
        letters = [c for c in stripped_line if c.isalpha()]
        if len(letters) == 1 and letters[0].isascii():
                return line

        # Rule 3: Skip translation entirely if the line's detected language is already the target language.
        detected_lang = detect_source_lang(stripped_line)
        if detected_lang == target_lang[:2].lower():
                return line

        # Check exact RAM cache hit
        cached_line = appTable.get(line, None)
        if cached_line is not None:
                return cached_line

        # Number isolation logic to maximize cache hits and eliminate latency on dynamic numbers
        has_digits = any(c.isdigit() for c in stripped_line)
        if has_digits:
                import re
                numbers = re.findall(r'\d+(?:\.\d+)?', stripped_line)
                if numbers:
                        # Replace numbers with placeholders {0}, {1}, etc.
                        template_parts = []
                        last_idx = 0
                        for i, match in enumerate(re.finditer(r'\d+(?:\.\d+)?', stripped_line)):
                                template_parts.append(stripped_line[last_idx:match.start()])
                                template_parts.append("{%d}" % i)
                                last_idx = match.end()
                        template_parts.append(stripped_line[last_idx:])
                        line_template = "".join(template_parts)



                        # If template has no letters (e.g. "{0}"), format and return immediately
                        if not any(c.isalpha() for c in line_template):
                                return safe_format(line_template, numbers)

                        # Check template RAM cache hit
                        cached_template = appTable.get(line_template, None)
                        if cached_template is not None:
                                result = safe_format(cached_template, numbers)
                                update_cache(appTable, line, result)
                                return result

                        # Cache miss: translate the template, letting the engine detect the source language
                        try:
                                translated_template = _execute_engine_translation(line_template, source_lang="auto")
                                if translated_template and translated_template.strip():
                                        normalized = normalize_placeholders(translated_template)
                                        if _placeholders_survived(normalized, len(numbers)):
                                                update_cache(appTable, line_template, normalized)
                                                result = safe_format(normalized, numbers)
                                                update_cache(appTable, line, result)
                                                return result
                                        # The engine dropped or mangled a placeholder, so the template is
                                        # unusable. Translate the untouched line instead of appending the
                                        # numbers to the end of the sentence.
                                        literal = _execute_engine_translation(stripped_line, source_lang="auto")
                                        if literal and literal.strip():
                                                update_cache(appTable, line, literal)
                                                return literal
                                        result = safe_format(normalized, numbers)
                                        update_cache(appTable, line, result)
                                        return result
                                else:
                                        update_cache(appTable, line_template, line_template)
                                        result = safe_format(line_template, numbers)
                                        update_cache(appTable, line, result)
                                        return result
                        except Exception as e:
                                logHandler.log.error("Template translation failed: %s" % e)
                                return line

        # No digits: translate directly, letting the engine detect the source language
        try:
                translated_val = _execute_engine_translation(stripped_line, source_lang="auto")
                if translated_val and translated_val.strip():
                        update_cache(appTable, line, translated_val)
                        return translated_val
                else:
                        update_cache(appTable, line, line)
                        return line
        except Exception as e:
                logHandler.log.error("Direct translation failed: %s" % e)
                return line


def translate_single_line(line, appTable, target_lang):
        return translate_single_line_core(line, appTable, target_lang)



def translate(text):
        global _translationCache, _enableTranslation, _gpObject

        try:
                appName = globalVars.focusObject.appModule.appName
        except:
                appName = "__global__"
                
        if _gpObject is None or _enableTranslation is False:
                return text

        if not text or not text.strip():
                return text

        appTable = _translationCache.get(appName, None)
        if appTable is None:
                appTable = {}
                _translationCache[appName] = appTable

        target_lang = config.conf["translate"]["localTargetLang"]
        if not target_lang:
                target_lang = _gpObject.language

        # Split line by line for precise caching, zero repetition loops, and instant response times
        lines = text.splitlines()
        translated_lines = []
        import time
        t0 = time.time()
        
        # Globally swap execute helper during this call to track engine calls
        global _execute_engine_translation
        original_execute = _execute_engine_translation
        engine_calls = [0]
        
        def tracked_execute(*args, **kwargs):
                engine_calls[0] += 1
                return original_execute(*args, **kwargs)
                
        _execute_engine_translation = tracked_execute
        
        try:
                for line in lines:
                        translated_lines.append(translate_single_line(line, appTable, target_lang))
        finally:
                _execute_engine_translation = original_execute

        # Log total latency if we hit the engine
        if engine_calls[0] > 0:
                elapsed = (time.time() - t0) * 1000
                logHandler.log.info("SNELL: Translate call took %.1fms for text: %r" % (elapsed, text))

        if "\r\n" in text:
                return "\r\n".join(translated_lines)
        return "\n".join(translated_lines)





def speak(speechSequence, *args, **kwargs):
        global _enableTranslation, _lastTranslatedText

        if _enableTranslation is False:
                return _nvdaSpeak(speechSequence, *args, **kwargs)
        newSpeechSequence = []
        for val in speechSequence:
                if isinstance(val, str):
                        v = translate(val)
                        newSpeechSequence.append(v if v is not None else val)
                else:
                        newSpeechSequence.append(val)
        _lastTranslatedText = " ".join(x if isinstance(x, str) else ""        for x in newSpeechSequence)
        return _nvdaSpeak(SpeechSequence(newSpeechSequence), *args, **kwargs)

LANG_NAMES = {
	"af": "Afrikaans", "am": "Amharic", "ar": "Arabic", "as": "Assamese",
	"az": "Azerbaijani", "be": "Belarusian", "bg": "Bulgarian", "bn": "Bengali",
	"bo": "Tibetan", "bs": "Bosnian", "ca": "Catalan", "cs": "Czech",
	"cy": "Welsh", "da": "Danish", "de": "German", "el": "Greek",
	"en": "English", "eo": "Esperanto", "es": "Spanish", "et": "Estonian",
	"eu": "Basque", "fa": "Persian", "fi": "Finnish", "fr": "French",
	"ga": "Irish", "gl": "Galician", "gu": "Gujarati", "ha": "Hausa",
	"he": "Hebrew", "hi": "Hindi", "hr": "Croatian", "hu": "Hungarian",
	"hy": "Armenian", "id": "Indonesian", "ig": "Igbo", "is": "Icelandic",
	"it": "Italian", "ja": "Japanese", "jv": "Javanese", "ka": "Georgian",
	"kk": "Kazakh", "km": "Khmer", "kn": "Kannada", "ko": "Korean",
	"ku": "Kurdish", "ky": "Kyrgyz", "lo": "Lao", "lt": "Lithuanian",
	"lv": "Latvian", "mg": "Malagasy", "mk": "Macedonian", "ml": "Malayalam",
	"mn": "Mongolian", "mr": "Marathi", "ms": "Malay", "mt": "Maltese",
	"my": "Burmese", "nb": "Norwegian Bokmal", "ne": "Nepali", "nl": "Dutch",
	"nn": "Norwegian Nynorsk", "no": "Norwegian", "or": "Odia", "pa": "Punjabi",
	"pl": "Polish", "pt": "Portuguese", "ro": "Romanian", "ru": "Russian",
	"si": "Sinhala", "sk": "Slovak", "sl": "Slovenian", "so": "Somali",
	"sq": "Albanian", "sr": "Serbian", "su": "Sundanese", "sv": "Swedish",
	"sw": "Swahili", "ta": "Tamil", "te": "Telugu", "tg": "Tajik",
	"th": "Thai", "tl": "Filipino", "tr": "Turkish", "uk": "Ukrainian",
	"ur": "Urdu", "uz": "Uzbek", "vi": "Vietnamese", "xh": "Xhosa",
	"yo": "Yoruba", "zh": "Chinese", "zu": "Zulu",
}

def get_supported_languages():
	return sorted(LANG_NAMES.items(), key=lambda x: x[1])


class TranslateSettingsPanel(gui.settingsDialogs.SettingsPanel):
	title = _("Translate")

	_ENGINE_CHOICES = [
		(ENGINE_GOOGLE, "Google Translate"),
		(ENGINE_LINGVA, "Lingva Translate"),
		(ENGINE_LIBRETRANSLATE, "LibreTranslate"),
		(ENGINE_DEEPL, "DeepL Translate"),
		(ENGINE_BING, "Bing Translate"),
		(ENGINE_OPENAI, "OpenAI ChatGPT"),
		(ENGINE_GEMINI, "Google Gemini"),
		(ENGINE_OPENROUTER, "OpenRouter (DeepSeek/Other)"),
	]

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		self.engineChoice = sHelper.addLabeledControl(
			_("Translation &engine:"),
			wx.Choice,
			choices=[label for _id, label in self._ENGINE_CHOICES]
		)
		engine = config.conf["translate"]["engine"]
		idx = next((i for i, (eid, _) in enumerate(self._ENGINE_CHOICES) if eid == engine), 0)
		self.engineChoice.SetSelection(idx)
		self.engineChoice.Bind(wx.EVT_CHOICE, self.onEngineChange)

		self.lingvaUrl = sHelper.addLabeledControl(
			_("Lingva Translate &instance URL:"),
			wx.TextCtrl
		)
		self.lingvaUrl.SetValue(config.conf["translate"]["lingvaUrl"])

		self.libreTranslateUrl = sHelper.addLabeledControl(
			_("LibreTranslate &URL:"),
			wx.TextCtrl
		)
		self.libreTranslateUrl.SetValue(config.conf["translate"]["libretranslateUrl"])

		self.libreTranslateApiKey = sHelper.addLabeledControl(
			_("LibreTranslate API &key (optional):"),
			wx.TextCtrl
		)
		self.libreTranslateApiKey.SetValue(config.conf["translate"]["libretranslateApiKey"])

		# DeepL API Key
		self.deeplApiKey = sHelper.addLabeledControl(
			_("DeepL API &key:"),
			wx.TextCtrl
		)
		self.deeplApiKey.SetValue(config.conf["translate"]["deeplApiKey"])

		# OpenAI API Key
		self.openaiApiKey = sHelper.addLabeledControl(
			_("OpenAI API &key:"),
			wx.TextCtrl
		)
		self.openaiApiKey.SetValue(config.conf["translate"]["openaiApiKey"])

		# OpenAI Fetch Button and Choice
		self.openaiFetchBtn = wx.Button(self, label=_("Fetch OpenAI Models"))
		self.openaiFetchBtn.Bind(wx.EVT_BUTTON, self.onOpenAIFetch)
		sHelper.sizer.Add(self.openaiFetchBtn)

		self.openaiModelChoice = sHelper.addLabeledControl(
			_("OpenAI &model:"),
			wx.Choice,
			choices=[]
		)

		# Populate OpenAI models list from configuration
		openai_list = [x.strip() for x in config.conf["translate"]["openaiModelsList"].split(",") if x.strip()]
		if not openai_list:
			openai_list = ["gpt-5.4-mini", "gpt-5.5-pro"]
		self.openaiModelChoice.AppendItems(openai_list)
		saved_openai_model = config.conf["translate"]["openaiModel"]
		idx_openai = openai_list.index(saved_openai_model) if saved_openai_model in openai_list else 0
		self.openaiModelChoice.SetSelection(idx_openai)

		# Gemini API Key
		self.geminiApiKey = sHelper.addLabeledControl(
			_("Gemini API &key:"),
			wx.TextCtrl
		)
		self.geminiApiKey.SetValue(config.conf["translate"]["geminiApiKey"])

		# Gemini Fetch Button and Choice
		self.geminiFetchBtn = wx.Button(self, label=_("Fetch Gemini Models"))
		self.geminiFetchBtn.Bind(wx.EVT_BUTTON, self.onGeminiFetch)
		sHelper.sizer.Add(self.geminiFetchBtn)

		self.geminiModelChoice = sHelper.addLabeledControl(
			_("Gemini &model:"),
			wx.Choice,
			choices=[]
		)

		# Populate Gemini models list from configuration
		gemini_list = [x.strip() for x in config.conf["translate"]["geminiModelsList"].split(",") if x.strip()]
		if not gemini_list:
			gemini_list = ["gemini-3.5-flash", "gemini-3.5-pro"]
		self.geminiModelChoice.AppendItems(gemini_list)
		saved_gemini_model = config.conf["translate"]["geminiModel"]
		idx_gemini = gemini_list.index(saved_gemini_model) if saved_gemini_model in gemini_list else 0
		self.geminiModelChoice.SetSelection(idx_gemini)

		# Bing API Key & Region
		self.bingApiKey = sHelper.addLabeledControl(
			_("Bing API key:"),
			wx.TextCtrl
		)
		self.bingApiKey.SetValue(config.conf["translate"]["bingApiKey"])

		self.bingRegion = sHelper.addLabeledControl(
			_("Bing API region (optional):"),
			wx.TextCtrl
		)
		self.bingRegion.SetValue(config.conf["translate"]["bingRegion"])

		# OpenRouter API Key
		self.openrouterApiKey = sHelper.addLabeledControl(
			_("OpenRouter API key:"),
			wx.TextCtrl
		)
		self.openrouterApiKey.SetValue(config.conf["translate"]["openrouterApiKey"])

		# OpenRouter Fetch Button and Choice
		self.openrouterFetchBtn = wx.Button(self, label=_("Fetch OpenRouter Models"))
		self.openrouterFetchBtn.Bind(wx.EVT_BUTTON, self.onOpenRouterFetch)
		sHelper.sizer.Add(self.openrouterFetchBtn)

		self.openrouterModelChoice = sHelper.addLabeledControl(
			_("OpenRouter model:"),
			wx.Choice,
			choices=[]
		)

		# Populate OpenRouter models list from configuration
		openrouter_list = [x.strip() for x in config.conf["translate"]["openrouterModelsList"].split(",") if x.strip()]
		if not openrouter_list:
			openrouter_list = ["deepseek/deepseek-chat", "google/gemini-2.5-flash"]
		self.openrouterModelChoice.AppendItems(openrouter_list)
		saved_openrouter_model = config.conf["translate"]["openrouterModel"]
		idx_openrouter = openrouter_list.index(saved_openrouter_model) if saved_openrouter_model in openrouter_list else 0
		self.openrouterModelChoice.SetSelection(idx_openrouter)

		self._lang_codes = [""]  # empty = match NVDA language
		self._lang_labels = [_("Match NVDA language")]
		for code, name in get_supported_languages():
			self._lang_codes.append(code)
			self._lang_labels.append("{name} ({code})".format(name=name, code=code))

		self.targetLangChoice = sHelper.addLabeledControl(
			_("&Target language:"),
			wx.Choice,
			choices=self._lang_labels
		)
		saved_lang = config.conf["translate"]["localTargetLang"]
		if saved_lang in self._lang_codes:
			self.targetLangChoice.SetSelection(self._lang_codes.index(saved_lang))
		else:
			self.targetLangChoice.SetSelection(0)

		self._updateFieldsVisibility()

	def onEngineChange(self, evt):
		self._updateFieldsVisibility()

	def _updateFieldsVisibility(self):
		if not all(hasattr(self, attr) for attr in ("engineChoice", "lingvaUrl", "libreTranslateUrl", "libreTranslateApiKey", "targetLangChoice")):
			return
		engineId = self._ENGINE_CHOICES[self.engineChoice.GetSelection()][0]
		self.lingvaUrl.Enable(engineId == ENGINE_LINGVA)
		self.libreTranslateUrl.Enable(engineId == ENGINE_LIBRETRANSLATE)
		self.libreTranslateApiKey.Enable(engineId == ENGINE_LIBRETRANSLATE)
		
		# DeepL
		if hasattr(self, "deeplApiKey"):
			self.deeplApiKey.Enable(engineId == ENGINE_DEEPL)
			
		# OpenAI
		if hasattr(self, "openaiApiKey"):
			self.openaiApiKey.Enable(engineId == ENGINE_OPENAI)
			self.openaiFetchBtn.Enable(engineId == ENGINE_OPENAI)
			self.openaiModelChoice.Enable(engineId == ENGINE_OPENAI)
			
		# Gemini
		if hasattr(self, "geminiApiKey"):
			self.geminiApiKey.Enable(engineId == ENGINE_GEMINI)
			self.geminiFetchBtn.Enable(engineId == ENGINE_GEMINI)
			self.geminiModelChoice.Enable(engineId == ENGINE_GEMINI)
			
		# Bing
		if hasattr(self, "bingApiKey"):
			self.bingApiKey.Enable(engineId == ENGINE_BING)
			self.bingRegion.Enable(engineId == ENGINE_BING)
			
		# OpenRouter
		if hasattr(self, "openrouterApiKey"):
			self.openrouterApiKey.Enable(engineId == ENGINE_OPENROUTER)
			self.openrouterFetchBtn.Enable(engineId == ENGINE_OPENROUTER)
			self.openrouterModelChoice.Enable(engineId == ENGINE_OPENROUTER)
			
		self.targetLangChoice.Enable(True)

	def onOpenAIFetch(self, evt):
		api_key = self.openaiApiKey.GetValue().strip()
		if not api_key:
			gui.messageBox(
				_("Please enter an OpenAI API key first."),
				_("Error"),
				style=wx.OK | wx.ICON_ERROR
			)
			return
		self.openaiFetchBtn.Disable()
		self.openaiFetchBtn.SetLabel(_("Fetching..."))
		
		def run():
			try:
				models = openai_api.fetch_models(api_key)
				wx.CallAfter(self.onOpenAIFetchSuccess, models)
			except Exception as e:
				wx.CallAfter(self.onOpenAIFetchFail, str(e))
				
		threading.Thread(target=run, daemon=True).start()

	def onOpenAIFetchSuccess(self, models):
		self.openaiFetchBtn.Enable()
		self.openaiFetchBtn.SetLabel(_("Fetch OpenAI Models"))
		if not models:
			gui.messageBox(
				_("No compatible OpenAI models found."),
				_("Info"),
				style=wx.OK | wx.ICON_INFORMATION
			)
			return
		self.openaiModelChoice.Clear()
		self.openaiModelChoice.AppendItems(models)
		self.openaiModelChoice.SetSelection(0)
		self._openai_fetched_list = models
		gui.messageBox(
			_("Successfully fetched {count} OpenAI models!").format(count=len(models)),
			_("Success"),
			style=wx.OK | wx.ICON_INFORMATION
		)

	def onOpenAIFetchFail(self, err_msg):
		self.openaiFetchBtn.Enable()
		self.openaiFetchBtn.SetLabel(_("Fetch OpenAI Models"))
		gui.messageBox(
			_("Failed to fetch OpenAI models: {error}").format(error=err_msg),
			_("Error"),
			style=wx.OK | wx.ICON_ERROR
		)

	def onGeminiFetch(self, evt):
		api_key = self.geminiApiKey.GetValue().strip()
		if not api_key:
			gui.messageBox(
				_("Please enter a Gemini API key first."),
				_("Error"),
				style=wx.OK | wx.ICON_ERROR
			)
			return
		self.geminiFetchBtn.Disable()
		self.geminiFetchBtn.SetLabel(_("Fetching..."))
		
		def run():
			try:
				models = gemini_api.fetch_models(api_key)
				wx.CallAfter(self.onGeminiFetchSuccess, models)
			except Exception as e:
				wx.CallAfter(self.onGeminiFetchFail, str(e))
				
		threading.Thread(target=run, daemon=True).start()

	def onGeminiFetchSuccess(self, models):
		self.geminiFetchBtn.Enable()
		self.geminiFetchBtn.SetLabel(_("Fetch Gemini Models"))
		if not models:
			gui.messageBox(
				_("No compatible Gemini models found."),
				_("Info"),
				style=wx.OK | wx.ICON_INFORMATION
			)
			return
		self.geminiModelChoice.Clear()
		self.geminiModelChoice.AppendItems(models)
		self.geminiModelChoice.SetSelection(0)
		self._gemini_fetched_list = models
		gui.messageBox(
			_("Successfully fetched {count} Gemini models!").format(count=len(models)),
			_("Success"),
			style=wx.OK | wx.ICON_INFORMATION
		)

	def onGeminiFetchFail(self, err_msg):
		self.geminiFetchBtn.Enable()
		self.geminiFetchBtn.SetLabel(_("Fetch Gemini Models"))
		gui.messageBox(
			_("Failed to fetch Gemini models: {error}").format(error=err_msg),
			_("Error"),
			style=wx.OK | wx.ICON_ERROR
		)

	def onOpenRouterFetch(self, evt):
		api_key = self.openrouterApiKey.GetValue().strip()
		if not api_key:
			gui.messageBox(
				_("Please enter an OpenRouter API key first."),
				_("Error"),
				style=wx.OK | wx.ICON_ERROR
			)
			return
		self.openrouterFetchBtn.Disable()
		self.openrouterFetchBtn.SetLabel(_("Fetching..."))
		
		def run():
			try:
				models = openrouter_api.fetch_models(api_key)
				wx.CallAfter(self.onOpenRouterFetchSuccess, models)
			except Exception as e:
				wx.CallAfter(self.onOpenRouterFetchFail, str(e))
				
		threading.Thread(target=run, daemon=True).start()

	def onOpenRouterFetchSuccess(self, models):
		self.openrouterFetchBtn.Enable()
		self.openrouterFetchBtn.SetLabel(_("Fetch OpenRouter Models"))
		if not models:
			gui.messageBox(
				_("No compatible OpenRouter models found."),
				_("Info"),
				style=wx.OK | wx.ICON_INFORMATION
			)
			return
		self.openrouterModelChoice.Clear()
		self.openrouterModelChoice.AppendItems(models)
		self.openrouterModelChoice.SetSelection(0)
		self._openrouter_fetched_list = models
		gui.messageBox(
			_("Successfully fetched {count} OpenRouter models!").format(count=len(models)),
			_("Success"),
			style=wx.OK | wx.ICON_INFORMATION
		)

	def onOpenRouterFetchFail(self, err_msg):
		self.openrouterFetchBtn.Enable()
		self.openrouterFetchBtn.SetLabel(_("Fetch OpenRouter Models"))
		gui.messageBox(
			_("Failed to fetch OpenRouter models: {error}").format(error=err_msg),
			_("Error"),
			style=wx.OK | wx.ICON_ERROR
		)

	def onSave(self):
		engineId = self._ENGINE_CHOICES[self.engineChoice.GetSelection()][0]
		config.conf["translate"]["engine"] = engineId
		config.conf["translate"]["lingvaUrl"] = self.lingvaUrl.GetValue()
		config.conf["translate"]["libretranslateUrl"] = self.libreTranslateUrl.GetValue()
		config.conf["translate"]["libretranslateApiKey"] = self.libreTranslateApiKey.GetValue()
		
		if hasattr(self, "deeplApiKey"):
			config.conf["translate"]["deeplApiKey"] = self.deeplApiKey.GetValue()
		if hasattr(self, "openaiApiKey"):
			config.conf["translate"]["openaiApiKey"] = self.openaiApiKey.GetValue()
			sel_op = self.openaiModelChoice.GetSelection()
			if sel_op != wx.NOT_FOUND:
				config.conf["translate"]["openaiModel"] = self.openaiModelChoice.GetString(sel_op)
			if hasattr(self, "_openai_fetched_list"):
				config.conf["translate"]["openaiModelsList"] = ",".join(self._openai_fetched_list)
				
		if hasattr(self, "geminiApiKey"):
			config.conf["translate"]["geminiApiKey"] = self.geminiApiKey.GetValue()
			sel_gem = self.geminiModelChoice.GetSelection()
			if sel_gem != wx.NOT_FOUND:
				config.conf["translate"]["geminiModel"] = self.geminiModelChoice.GetString(sel_gem)
			if hasattr(self, "_gemini_fetched_list"):
				config.conf["translate"]["geminiModelsList"] = ",".join(self._gemini_fetched_list)
				
		if hasattr(self, "bingApiKey"):
			config.conf["translate"]["bingApiKey"] = self.bingApiKey.GetValue()
		if hasattr(self, "bingRegion"):
			config.conf["translate"]["bingRegion"] = self.bingRegion.GetValue()
		if hasattr(self, "openrouterApiKey"):
			config.conf["translate"]["openrouterApiKey"] = self.openrouterApiKey.GetValue()
			sel_or = self.openrouterModelChoice.GetSelection()
			if sel_or != wx.NOT_FOUND:
				config.conf["translate"]["openrouterModel"] = self.openrouterModelChoice.GetString(sel_or)
			if hasattr(self, "_openrouter_fetched_list"):
				config.conf["translate"]["openrouterModelsList"] = ",".join(self._openrouter_fetched_list)

		sel = self.targetLangChoice.GetSelection()
		config.conf["translate"]["localTargetLang"] = self._lang_codes[sel] if sel > 0 else ""


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
        scriptCategory = _("Translate")
        language = None

        def __init__(self):
                super(globalPluginHandler.GlobalPlugin, self).__init__()
                global _gpObject
                
                if globalVars.appArgs.secure: return
                _gpObject = self
                try:
                        self.language = config.conf["general"]["language"]
                except:
                        self.language = None
                        pass
                if self.language is not None and self.language != 'Windows':
                        self.language = self.language.split("_")[0]
                else:
                        try:
                                self.language = languageHandler.getWindowsLanguage()[:2]
                        except:
                                self.language = 'en'
                import addonHandler
                version = None
                for addon in addonHandler.getAvailableAddons():
                        if addon.name == "translate":
                                version = addon.version
                if version is None:
                        version = 'unknown'
                logHandler.log.info("Translate (%s) initialized, translating to %s" %(version, self.language))
                global _nvdaSpeak
                try:
                        import speech.speech as speech_module
                except ImportError:
                        import speech as speech_module

                _nvdaSpeak = speech_module.speak
                speech_module.speak = speak
                speech.speak = speak

                # Patch sayAll to support translation during continuous reading
                try:
                        import speech.sayAll as speech_sayAll
                        if speech_sayAll.SayAllHandler is not None:
                                speech_sayAll.SayAllHandler.speechWithoutPausesInstance.speak = speak
                except Exception as e:
                        logHandler.log.error("Translate: Failed to patch sayAll speak: %s" % e)

                self.loadLocalCache()
                self._autoSaveRunning = True
                self._autoSaveThread = threading.Thread(target=self._autoSaveLoop, daemon=True)
                self._autoSaveThread.start()
                gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(TranslateSettingsPanel)

        def _autoSaveLoop(self):
                global _cacheModified
                import time
                while getattr(self, "_autoSaveRunning", False):
                        time.sleep(15)
                        if _cacheModified:
                                try:
                                        self.saveLocalCache()
                                        _cacheModified = False
                                except Exception as e:
                                        logHandler.log.error("Failed to auto-save translation cache: %s" % e)

        def terminate(self):
                global _nvdaSpeak
                try:
                        import speech.speech as speech_module
                except ImportError:
                        import speech as speech_module

                if _nvdaSpeak is not None:
                        speech_module.speak = _nvdaSpeak
                        speech.speak = _nvdaSpeak
                        try:
                                import speech.sayAll as speech_sayAll
                                if speech_sayAll.SayAllHandler is not None:
                                        speech_sayAll.SayAllHandler.speechWithoutPausesInstance.speak = _nvdaSpeak
                        except Exception:
                                pass
                self._autoSaveRunning = False
                self.saveLocalCache()
                gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(TranslateSettingsPanel)
        def loadLocalCache(self):
                global _translationCache

                path = os.path.join(globalVars.appArgs.configPath, "translation-cache")
                if os.path.exists(path) is False:
                        try:
                                os.mkdir(path)
                        except Exception as e:
                                logHandler.log.error("Failed to create storage path: {path} ({error})".format(path=path, error=e))
                                return
                                                                                                
                for entry in os.listdir(path):
                        m = re.match("(.*).json$", entry)
                        if m is not None:
                                appName = m.group(1)
                                try:
                                        cacheFile = codecs.open(os.path.join(path, entry), "r", "utf-8")
                                except:
                                        continue
                                try:
                                        values = json.load(cacheFile)
                                        cacheFile.close()
                                except Exception as e:
                                        logHandler.log.error("Cannot read or decode data from {path}: {e}".format(path=path, e=e))
                                        cacheFile.close()
                                        continue
                                _translationCache[appName] = values
                                cacheFile.close()
        def saveLocalCache(self):
                global _translationCache, _cacheLock

                with _cacheLock:
                        cache_copy = {appName: dict(table) for appName, table in _translationCache.items()}

                path = os.path.join(globalVars.appArgs.configPath, "translation-cache")
                for appName, table in cache_copy.items():
                        file = os.path.join(path, "%s.json" % appName)
                        try:
                                # Filter out any identity translations (temporary failures) to prevent them from persisting
                                cleaned_table = {k: v for k, v in table.items() if k.strip() != v.strip()}
                                if not cleaned_table:
                                        # If table is empty after cleaning, remove the file if it exists
                                        if os.path.exists(file):
                                                try:
                                                        os.unlink(file)
                                                except Exception:
                                                        pass
                                        continue

                                cacheFile = codecs.open(file, "w", "utf-8")
                                json.dump(cleaned_table, cacheFile)
                                cacheFile.close()
                        except Exception as e:
                                logHandler.log.error("Failed to save translation cache for {app} to {file}: {error}".format(app=appName, file=file, error=e))
                                continue

        def script_toggleTranslate(self, gesture):
                global _enableTranslation, _localTranslateWarningShown
                
                _enableTranslation = not _enableTranslation
                _localTranslateWarningShown = False
                if _enableTranslation:
                        ui.message(_("Translation enabled."))
                else:
                        ui.message(_("Translation disabled."))

        script_toggleTranslate.__doc__ = _("Enables translation to the desired language.")

        def script_copyLastTranslation(self, gesture):
                global _lastTranslatedText

                if _lastTranslatedText is not None and len(_lastTranslatedText) > 0:
                        api.copyToClip(_lastTranslatedText)
                        ui.message(_("translation {text} ¨copied to clipboard").format(text=_lastTranslatedText))
                else:
                        ui.message(_("No translation to copy"))
        script_copyLastTranslation.__doc__ = _("Copy the latest translated text to the clipboard.")
                                                                 
        def script_flushAllCache(self, gesture):
                if scriptHandler.getLastScriptRepeatCount() == 0:
                        ui.message(_("Press twice to delete all cached translations for all applications."))
                        return
                global _translationCache
                _translationCache = {}
                path = os.path.join(globalVars.appArgs.configPath, "translation-cache")
                error = False
                for entry in os.listdir(path):
                        try:
                                os.unlink(os.path.join(path, entry))
                        except Exception as e:
                                logHandler.log.error("Failed to remove {entry}".format(entry=entry))
                                error = True
                if not error:
                        ui.message(_("All translations have been deleted."))
                else:
                        ui.message(_("Some caches failed to be removed."))
        script_flushAllCache.__doc__ = _("Remove all cached translations for all applications.")

        def script_flushCurrentAppCache(self, gesture):
                try:
                        appName = globalVars.focusObject.appModule.appName
                except:
                        ui.message(_("No focused application"))
                        return
                if scriptHandler.getLastScriptRepeatCount() == 0:
                        ui.message(_("Press twice to delete all translations for {app}").format(app=appName))
                        return
                
                global _translationCache
                        
                _translationCache[appName] = {}
                fullPath = os.path.join(globalVars.appArgs.configPath, "translation-cache", "{app}.json".format(app=appName))
                if os.path.exists(fullPath):
                        try:
                                os.unlink(fullPath)
                        except Exception as e:
                                logHandler.log.error("Failed to remove cache for {appName}: {e}".format(appName=appName, e=e))
                                ui.message(_("Error while deleting application's translation cache."))
                                return
                        ui.message(_("Translation cache for {app} has been deleted.").format(app=appName))
                else:
                        ui.message(_("No saved translations for {app}").format(app=appName))
                        
        script_flushCurrentAppCache.__doc__ = _("Remove translation cache for the currently focused application")
                                                                                                                                
                                                                                                                                 

        __gestures = {
                "kb:nvda+shift+control+t": "toggleTranslate",
                "kb:nvda+shift+c": "copyLastTranslation",
                "kb:nvda+shift+control+f": "flushAllCache",
                "kb:nvda+shift+f": "flushCurrentAppCache",
        }
