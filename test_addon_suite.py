# -*- coding: utf-8 -*-
import sys
import os
import unittest
import builtins
builtins.__dict__['_'] = lambda x: x
from unittest.mock import MagicMock, patch




# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Define dummy modules to mock NVDA environment
class DummyLogger:
    def __init__(self):
        self.logs = []
    def info(self, msg, *args):
        self.logs.append(("INFO", msg % args if args else msg))
    def warning(self, msg, *args):
        self.logs.append(("WARNING", msg % args if args else msg))
    def error(self, msg, *args):
        self.logs.append(("ERROR", msg % args if args else msg))

class DummyLogHandler:
    def __init__(self):
        self.log = DummyLogger()

dummy_log_handler = DummyLogHandler()

# Insert dummy modules into sys.modules
sys.modules['globalVars'] = MagicMock()
sys.modules['globalPluginHandler'] = MagicMock()
sys.modules['logHandler'] = dummy_log_handler
sys.modules['scriptHandler'] = MagicMock()
sys.modules['api'] = MagicMock()
sys.modules['ui'] = MagicMock()
sys.modules['wx'] = MagicMock()
sys.modules['gui'] = MagicMock()
sys.modules['speech'] = MagicMock()
sys.modules['speech.types'] = MagicMock()
sys.modules['speech.priorities'] = MagicMock()
sys.modules['addonHandler'] = MagicMock()
sys.modules['languageHandler'] = MagicMock()

# Mock config.conf
class DummyConf:
    def __init__(self):
        self.spec = {}
        self.data = {
            "translate": {
                "engine": "google",
                "localTargetLang": "ar",
                "lingvaUrl": "https://lingva.ml",
                "libretranslateUrl": "https://libretranslate.com",
                "libretranslateApiKey": "",
                "localModelId": "",
                "localDevice": "auto",
                "modelsDrive": "",
                "localIdleTimeout": 5,
                "localBeamSize": "quality"
            }
        }
    def __getitem__(self, key):
        return self.data[key]

class DummyConfigModule:
    def __init__(self):
        self.conf = DummyConf()

dummy_config_module = DummyConfigModule()
sys.modules['config'] = dummy_config_module


from globalPlugins.translate import (
    normalize_placeholders,
    safe_format,
    translate,
    _translationCache,
    _execute_engine_translation
)
import globalPlugins.translate as translate_module

class TestAddonSuite(unittest.TestCase):

    def setUp(self):
        # Clear translation cache before each test
        _translationCache.clear()
        dummy_log_handler.log.logs.clear()
        # Enable translation in the mocked module
        translate_module._enableTranslation = True
        translate_module._gpObject = MagicMock()
        translate_module._gpObject.language = "ar"
        translate_module.config.conf["translate"]["localTargetLang"] = "ar"

    def test_normalize_placeholders(self):
        """Test that placeholders corrupted by various translation engines are perfectly normalized."""
        self.assertEqual(normalize_placeholders("{0}"), "{0}")
        self.assertEqual(normalize_placeholders("{ 0 }"), "{0}")
        self.assertEqual(normalize_placeholders("{0 }"), "{0}")
        self.assertEqual(normalize_placeholders("{ 0}"), "{0}")
        
        # Test Eastern / Arabic-Indic digits
        self.assertEqual(normalize_placeholders("{٠}"), "{0}")
        self.assertEqual(normalize_placeholders("{ ١ }"), "{1}")
        self.assertEqual(normalize_placeholders("{٢}"), "{2}")
        
        # Test different bracket styles
        self.assertEqual(normalize_placeholders("[0]"), "{0}")
        self.assertEqual(normalize_placeholders("(1)"), "{1}")
        self.assertEqual(normalize_placeholders("[ ٢ ]"), "{2}")
        self.assertEqual(normalize_placeholders("( ٣ )"), "{3}")
        
        # Test mixed and multiple placeholders
        self.assertEqual(
            normalize_placeholders("المسافة [٠] كم والسرعة { ١ } كم/س"),
            "المسافة {0} كم والسرعة {1} كم/س"
        )

    def test_safe_format(self):
        """Test formatting numbers with robust fallback checks to avoid exceptions."""
        # Standard case
        self.assertEqual(safe_format("الحد {0}", ["80"]), "الحد 80")
        self.assertEqual(safe_format("المسافة {0} والسرعة {1}", ["100", "60"]), "المسافة 100 والسرعة 60")
        
        # Missing placeholder fallback (manual replacement or append)
        self.assertEqual(safe_format("الحد", ["80"]), "الحد (80)")
        
        # Broken/Out-of-bounds index placeholder fallback
        self.assertEqual(safe_format("المسافة {1}", ["100"]), "المسافة {1} (100)")
        
        # Empty numbers
        self.assertEqual(safe_format("الحد {0}", []), "الحد {0}")

    @patch('globalPlugins.translate._execute_engine_translation')
    def test_non_alphabetic_bypass(self, mock_engine):
        """Verify that lines containing no alphabetic characters bypass the engine and return immediately (0ms)."""
        # A purely numeric line
        res = translate("120")
        self.assertEqual(res, "120")
        mock_engine.assert_not_called()
        
        # Line with symbols and digits
        res = translate("120.5 / 80")
        self.assertEqual(res, "120.5 / 80")
        mock_engine.assert_not_called()
        
        # Line with punctuation only
        res = translate(":::")
        self.assertEqual(res, ":::")
        mock_engine.assert_not_called()

    @patch('globalPlugins.translate._execute_engine_translation')
    def test_isolated_latin_key_bypass(self, mock_engine):
        """Verify that single isolated Latin letters (or single letter with numbers/punctuation) bypass translation."""
        # Single isolated letter
        self.assertEqual(translate("g"), "g")
        # With spaces
        self.assertEqual(translate(" A "), " A ")
        # With punctuation/numbers
        self.assertEqual(translate("g: 120"), "g: 120")
        
        # Verify that non-ASCII single characters (like Japanese Kanji) STILL get translated!
        mock_engine.return_value = "محطة"
        self.assertEqual(translate("駅"), "محطة")
        mock_engine.assert_called_once_with("駅", source_lang="ja")
        
        # Verify engine was NOT called for ASCII keys
        self.assertEqual(mock_engine.call_count, 1)

    @patch('globalPlugins.translate._execute_engine_translation')
    def test_source_target_match_bypass(self, mock_engine):
        """Verify that if the source language matches the target language, translation is bypassed instantly (0ms)."""
        # Set target language to Arabic
        translate_module.config.conf["translate"]["localTargetLang"] = "ar"
        
        # Arabic text should be bypassed immediately
        self.assertEqual(translate("السلام عليكم"), "السلام عليكم")
        self.assertEqual(translate("مرحبا بك 120"), "مرحبا بك 120")
        mock_engine.assert_not_called()
        
        # Reset target language to English
        translate_module.config.conf["translate"]["localTargetLang"] = "en"
        self.assertEqual(translate("Hello World"), "Hello World")
        mock_engine.assert_not_called()

    @patch('globalPlugins.translate._execute_engine_translation')
    def test_full_context_translation(self, mock_engine):
        """Verify that sentences are translated in full to preserve maximum context."""
        translate_module.config.conf["translate"]["localTargetLang"] = "ar"
        mock_engine.return_value = "دردشة محلية من مستخدم{0}: مرحبا يا صديقي"
        
        res = translate("Local Chat from user123: Hello my friend")
        self.assertEqual(res, "دردشة محلية من مستخدم123: مرحبا يا صديقي")
        mock_engine.assert_called_once_with("Local Chat from user{0}: Hello my friend", source_lang="en")

    @patch('globalPlugins.translate._execute_engine_translation')
    def test_number_isolation_caching(self, mock_engine):
        """Test that digits are isolated, templates are translated and cached, and subsequent hits run locally (0ms)."""
        # Configure mock engine to translate the template
        mock_engine.return_value = "المسافة {0} متر"
        
        # First call: Should isolated-replace 100, hit engine for template, format, and return
        res1 = translate("距離 100メートル")
        self.assertEqual(res1, "المسافة 100 متر")
        mock_engine.assert_called_once_with("距離 {0}メートル", source_lang="ja")
        
        # Reset mock call history
        mock_engine.reset_mock()
        
        # Second call: Different number, same template. Should hit cache instantly, format locally, 0 engine calls!
        res2 = translate("距離 250メートル")
        self.assertEqual(res2, "المسافة 250 متر")
        mock_engine.assert_not_called()

    @patch('globalPlugins.translate._execute_engine_translation')
    def test_line_by_line_caching(self, mock_engine):
        """Test multi-line text where each line is translated and cached individually."""
        def mock_translate_proc(text, source_lang="auto"):
            if "Main Menu" in text:
                return "القائمة الرئيسية"
            elif "Dreamy Mode" in text:
                return "وضع الحلم"
            return text
            
        mock_engine.side_effect = mock_translate_proc
        
        # Multi-line string containing a number line, a translated line, and another translated line
        input_text = "Main Menu\n120\nDreamy Mode"
        
        res = translate(input_text)
        self.assertEqual(res, "القائمة الرئيسية\n120\nوضع الحلم")
        
        # The engine should only be called for "Main Menu" and "Dreamy Mode" (2 calls), and completely skip "120"
        self.assertEqual(mock_engine.call_count, 2)
        mock_engine.assert_any_call("Main Menu", source_lang="en")
        mock_engine.assert_any_call("Dreamy Mode", source_lang="en")

    @patch('globalPlugins.translate._execute_engine_translation')
    def test_identity_translation_caching(self, mock_engine):
        """Ensure that terms translating to themselves are stored in cache and do not hit network repeatedly."""
        mock_engine.return_value = "Main Menu"
        
        # First call
        res1 = translate("Main Menu")
        self.assertEqual(res1, "Main Menu")
        mock_engine.assert_called_once_with("Main Menu", source_lang="en")
        
        mock_engine.reset_mock()
        
        # Second call: Should read from cache, 0 engine calls
        res2 = translate("Main Menu")
        self.assertEqual(res2, "Main Menu")
        mock_engine.assert_not_called()



if __name__ == "__main__":
    print("\n" + "="*60)
    print("      RUNNING NVDA TRANSLATE ADDON DEBUG & TEST SUITE      ")
    print("="*60 + "\n")
    
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAddonSuite)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    if result.wasSuccessful():
        print("          ALL DEBUG AND PERFORMANCE TESTS PASSED SUCCESSFULLY!          ")
        print("          No hidden errors or latency bottlenecks detected.         ")
        sys.exit(0)
    else:
        print("          SOME TEST CASES FAILED! SPECIAL INVESTIGATION REQUIRED.       ")
        sys.exit(1)
    print("="*60 + "\n")
