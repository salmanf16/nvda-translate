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
import addonHandler, languageHandler

addonHandler.initTranslation()

import threading

ENGINE_GOOGLE = "google"
ENGINE_LINGVA = "lingva"
ENGINE_LIBRETRANSLATE = "libretranslate"
ENGINE_LOCAL = "local"

config.conf.spec["translate"] = {
	"engine": 'string(default="google")',
	"lingvaUrl": 'string(default="https://lingva.ml")',
	"libretranslateUrl": 'string(default="https://libretranslate.com")',
	"libretranslateApiKey": 'string(default="")',
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
	if not text:
		return "auto"
	# Japanese Hiragana and Katakana
	if re.search(r'[\u3040-\u30ff]', text):
		return "ja"
	# Korean Hangul
	if re.search(r'[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]', text):
		return "ko"
	# CJK Unified Ideographs (Japanese Kanji / Chinese)
	if re.search(r'[\u4e00-\u9fff]', text):
		return "ja"
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

        if engine == ENGINE_LINGVA:
                url = config.conf["translate"]["lingvaUrl"]
                return lingva.translate(text, target_lang, source_language=source_lang, instance_url=url)
        elif engine == ENGINE_LIBRETRANSLATE:
                url = config.conf["translate"]["libretranslateUrl"]
                api_key = config.conf["translate"]["libretranslateApiKey"]
                return libretrans.translate(text, target_lang, source_language=source_lang, url=url, api_key=api_key)
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



GLOSSARY = {
        # Static server/status phrases
        "server down": "الخادم متوقف",
        "server is down": "الخادم متوقف",
        "connection lost": "فُقد الاتصال",
        "server restarting": "جاري إعادة تشغيل الخادم",
        "the server is restarting": "جاري إعادة تشغيل الخادم",
        "reconnecting... please wait": "جاري إعادة الاتصال... يرجى الانتظار",
        "reconnecting": "جاري إعادة الاتصال",
        "reconnected": "تم إعادة الاتصال",
        "server offline": "الخادم متوقف",
        "server is offline": "الخادم متوقف",
        "server online": "الخادم متصل",
        "server is online": "الخادم متصل",
        
        # Dynamic server/status templates (fully compatible with number isolation!)
        "the server will reboot within {0} seconds": "سيعاد تشغيل الخادم خلال {0} ثانية",
        "the server will reboot in {0} seconds": "سيعاد تشغيل الخادم خلال {0} ثانية",
        "reconnecting in {0} seconds": "إعادة الاتصال خلال {0} ثانية",
}


def translate_single_line_core(line, appTable, target_lang):
        stripped_line = line.strip()
        if not stripped_line:
                return line

        # Rule 0: Glossary Match (Static Arabic Status phrases with punctuation stripping)
        if target_lang[:2].lower() == "ar":
                import re
                punc_pattern = r'^([^\w\s{}]*)(.*?)([^\w\s{}]*)$'
                g_match = re.match(punc_pattern, stripped_line)
                if g_match:
                        prefix_punc = g_match.group(1)
                        core_text = g_match.group(2)
                        suffix_punc = g_match.group(3)
                        if core_text.lower() in GLOSSARY:
                                return prefix_punc + GLOSSARY[core_text.lower()] + suffix_punc



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

                        # Rule 0b: Glossary Match for Dynamic Templates with punctuation stripping
                        if target_lang[:2].lower() == "ar":
                                import re
                                punc_pattern = r'^([^\w\s{}]*)(.*?)([^\w\s{}]*)$'
                                g_match = re.match(punc_pattern, line_template)
                                if g_match:
                                        prefix_punc = g_match.group(1)
                                        core_template = g_match.group(2)
                                        suffix_punc = g_match.group(3)
                                        if core_template.lower() in GLOSSARY:
                                                formatted_core = safe_format(GLOSSARY[core_template.lower()], numbers)
                                                result = prefix_punc + formatted_core + suffix_punc
                                                update_cache(appTable, line, result)
                                                return result

                        # If template has no letters (e.g. "{0}"), format and return immediately
                        if not any(c.isalpha() for c in line_template):
                                return safe_format(line_template, numbers)

                        # Check template RAM cache hit
                        cached_template = appTable.get(line_template, None)
                        if cached_template is not None:
                                result = safe_format(cached_template, numbers)
                                update_cache(appTable, line, result)
                                return result

                        # Cache miss: translate the template
                        try:
                                translated_template = _execute_engine_translation(line_template, source_lang=detected_lang)
                                if translated_template and translated_template.strip():
                                        normalized = normalize_placeholders(translated_template)
                                        update_cache(appTable, line_template, normalized)
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

        # No digits: translate directly
        try:
                translated_val = _execute_engine_translation(stripped_line, source_lang=detected_lang)
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
		(ENGINE_GOOGLE, _("Google Translate")),
		(ENGINE_LINGVA, _("Lingva Translate")),
		(ENGINE_LIBRETRANSLATE, _("LibreTranslate")),
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
		self.targetLangChoice.Enable(True)

	def onSave(self):
		engineId = self._ENGINE_CHOICES[self.engineChoice.GetSelection()][0]
		config.conf["translate"]["engine"] = engineId
		config.conf["translate"]["lingvaUrl"] = self.lingvaUrl.GetValue()
		config.conf["translate"]["libretranslateUrl"] = self.libreTranslateUrl.GetValue()
		config.conf["translate"]["libretranslateApiKey"] = self.libreTranslateApiKey.GetValue()
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
