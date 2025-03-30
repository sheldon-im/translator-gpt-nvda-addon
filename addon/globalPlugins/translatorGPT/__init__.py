import os
import threading
import json
import wx
import gui
import globalPluginHandler
import ui
import speech
import config
import addonHandler
import globalVars
import speechViewer
import api
import textInfos
import tones
import time
import urllib.request
import urllib.parse
import ssl
from logHandler import log
from scriptHandler import script

addonHandler.initTranslation()

# Constants
ADDON_SUMMARY = "Translator GPT"
ADDON_DESCRIPTION = "Translates NVDA speech using GPT-4o-mini"
ADDON_VERSION = "1.01"
ADDON_AUTHOR = "Sheldon-Im"

# Configuration
CONFIG_SECTION = "translatorGPT"
CONFIG_KEY_API_KEY = "apiKey"
CONFIG_KEY_TARGET_LANGUAGE = "targetLanguage"
CONFIG_KEY_ENABLED = "enabled"

# Test configuration - REMOVE IN PRODUCTION
# Set this to your API key for testing purposes
TEST_API_KEY = ""  # e.g. "sk-abcdefghijklmnopqrstuvwxyz123456789"
# Set to True to use the test API key instead of the one from config
USE_TEST_API_KEY = False

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self):
        super(GlobalPlugin, self).__init__()
        self.original_speak = speech.speech.speak
        self.is_translating = False
        self.translation_queue = []
        self.translation_thread = None
        self.load_config()
        
        # Replace the speak function with our custom one
        speech.speech.speak = self.translate_and_speak
        
        # Create menu
        self.create_menu()
    
    def load_config(self):
        config.conf.spec[CONFIG_SECTION] = {
            CONFIG_KEY_API_KEY: "string(default='')",
            CONFIG_KEY_TARGET_LANGUAGE: "string(default='Korean')",
            CONFIG_KEY_ENABLED: "boolean(default=False)",
        }
        
        self.api_key = config.conf[CONFIG_SECTION][CONFIG_KEY_API_KEY]
        self.target_language = config.conf[CONFIG_SECTION][CONFIG_KEY_TARGET_LANGUAGE]
        self.enabled = config.conf[CONFIG_SECTION][CONFIG_KEY_ENABLED]
    
    def create_menu(self):
        # Create NVDA menu item
        try:
            # Get the preferences menu from NVDA's system tray icon
            preferencesMenu = gui.mainFrame.sysTrayIcon.preferencesMenu
            # Add our menu item to the preferences menu
            self.translatorSettingsItem = preferencesMenu.Append(
                wx.ID_ANY, 
                # Translators: The label for the menu item to open Translator GPT settings dialog.
                "Translator GPT Settings...",
                # Translators: The description for the menu item to open Translator GPT settings dialog.
                "Configure Translator GPT settings"
            )
            # Bind the menu item to our settings dialog
            gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.on_settings, self.translatorSettingsItem)
        except Exception as e:
            log.error(f"Could not add menu item: {e}")
    
    def on_settings(self, evt):
        wx.CallAfter(self.show_settings_dialog)
    
    def show_settings_dialog(self):
        dialog = TranslatorSettingsDialog(gui.mainFrame)
        dialog.ShowModal()
        dialog.Destroy()
    
    def translate_and_speak(self, speechSequence, *args, **kwargs):
        # Check if translation is enabled and API key is available
        # Use test API key if enabled, otherwise use the one from config
        api_key = TEST_API_KEY if USE_TEST_API_KEY else self.api_key
        
        if not self.enabled or not api_key:
            return self.original_speak(speechSequence, *args, **kwargs)
        
        # Extract text from speech sequence
        text = ""
        for item in speechSequence:
            if isinstance(item, str):
                text += item
        
        if not text.strip():
            return self.original_speak(speechSequence, *args, **kwargs)
        
        # Instead of speaking the original text, just queue it for translation
        # and block the original speech
        self.queue_translation(text)
        
        # Return None to prevent the original speech from being spoken
        return None
        # Check if the text is a single character (for both Korean and English)
        # Korean characters are composed of multiple bytes but are still single characters
        if len(text.strip()) == 1:
        # If it's a single character, speak the original text without translation
            return self.original_speak(speechSequence, *args, **kwargs)

def queue_translation(self, text):
        self.translation_queue.append(text)
        
        if not self.is_translating:
            self.is_translating = True
            self.translation_thread = threading.Thread(target=self.process_translation_queue)
            self.translation_thread.daemon = True
            self.translation_thread.start()
    
    def process_translation_queue(self):
        while self.translation_queue:
            text = self.translation_queue.pop(0)
            translated_text = self.translate_text(text)
            
            if translated_text:
                wx.CallAfter(self.speak_translation, translated_text)
            
            # Small delay to prevent rapid translations
            time.sleep(0.5)
        
        self.is_translating = False
    
    def speak_translation(self, text):
        # Speak the translated text directly without playing a sound
        self.original_speak([text], priority=speech.priorities.Spri.NORMAL)
    
    def translate_text(self, text):
        try:
            # Create a context that ignores SSL certificate verification
            context = ssl._create_unverified_context()
            
            # Prepare the request to OpenAI API
            url = "https://api.openai.com/v1/chat/completions"
            
            # Use test API key if enabled, otherwise use the one from config
            api_key = TEST_API_KEY if USE_TEST_API_KEY else self.api_key
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            # Prepare the data with improved system message
            data = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system", 
                        "content": f"""You are a professional translator specialized in converting text to {self.target_language}.
Your translations should be natural, fluent, and maintain the original meaning and nuance.
For Korean translations, ensure proper use of honorifics, particles, and natural sentence structure.
Focus on how a native speaker would express the same idea rather than literal translations.
Only respond with the translation itself, no explanations or additional text."""
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                "temperature": 0.7
            }
            
            # Convert data to JSON
            json_data = json.dumps(data).encode("utf-8")
            
            # Create the request
            req = urllib.request.Request(url, data=json_data, headers=headers, method="POST")
            
            # Send the request
            with urllib.request.urlopen(req, context=context) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                
                # Extract the translation from the response
                translation = response_data["choices"][0]["message"]["content"].strip()
                return translation
                
        except Exception as e:
            log.error(f"Translation error: {e}")
            return None
    
    def terminate(self):
        # Restore the original speak function
        speech.speech.speak = self.original_speak
        # Remove menu item
        try:
            if hasattr(self, 'translatorSettingsItem') and self.translatorSettingsItem:
                # Get the preferences menu from NVDA's system tray icon
                preferencesMenu = gui.mainFrame.sysTrayIcon.preferencesMenu
                # Remove our menu item from the preferences menu
                preferencesMenu.Remove(self.translatorSettingsItem)
        except Exception as e:
            log.error(f"Error removing menu item: {e}")
        super(GlobalPlugin, self).terminate()
    
    @script(
        description="Toggle Translator GPT",
        gesture="kb:NVDA+control+shift+t"
    )
    def script_toggleTranslator(self, gesture):
        self.enabled = not self.enabled
        config.conf[CONFIG_SECTION][CONFIG_KEY_ENABLED] = self.enabled
        
        if self.enabled:
            ui.message("Translator GPT enabled")
        else:
            ui.message("Translator GPT disabled")


class TranslatorSettingsDialog(wx.Dialog):
    def __init__(self, parent):
        super(TranslatorSettingsDialog, self).__init__(
            parent,
            title="Translator GPT Settings",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        
        # Load current settings
        self.api_key = config.conf[CONFIG_SECTION][CONFIG_KEY_API_KEY]
        self.target_language = config.conf[CONFIG_SECTION][CONFIG_KEY_TARGET_LANGUAGE]
        self.enabled = config.conf[CONFIG_SECTION][CONFIG_KEY_ENABLED]
        
        # Create controls
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # API Key
        api_key_sizer = wx.BoxSizer(wx.HORIZONTAL)
        api_key_label = wx.StaticText(self, label="OpenAI API Key:")
        self.api_key_ctrl = wx.TextCtrl(self, value=self.api_key, style=wx.TE_PASSWORD)
        api_key_sizer.Add(api_key_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        api_key_sizer.Add(self.api_key_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(api_key_sizer, 0, wx.EXPAND)
        
        # Target Language
        language_sizer = wx.BoxSizer(wx.HORIZONTAL)
        language_label = wx.StaticText(self, label="Target Language:")
        self.language_ctrl = wx.ComboBox(
            self,
            value=self.target_language,
            choices=["Korean", "English", "Japanese", "Chinese", "Spanish", "French", "German", "Russian", "Arabic"],
            style=wx.CB_DROPDOWN
        )
        language_sizer.Add(language_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        language_sizer.Add(self.language_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(language_sizer, 0, wx.EXPAND)
        
        # Enable checkbox
        self.enable_checkbox = wx.CheckBox(self, label="Enable Translator GPT")
        self.enable_checkbox.SetValue(self.enabled)
        main_sizer.Add(self.enable_checkbox, 0, wx.ALL | wx.EXPAND, 5)
        
        # Buttons
        buttons_sizer = wx.StdDialogButtonSizer()
        self.ok_button = wx.Button(self, wx.ID_OK)
        self.ok_button.SetDefault()
        self.cancel_button = wx.Button(self, wx.ID_CANCEL)
        buttons_sizer.AddButton(self.ok_button)
        buttons_sizer.AddButton(self.cancel_button)
        buttons_sizer.Realize()
        main_sizer.Add(buttons_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        self.SetSizer(main_sizer)
        main_sizer.Fit(self)
        
        # Bind events
        self.ok_button.Bind(wx.EVT_BUTTON, self.on_ok)
        
    def on_ok(self, evt):
        # Save settings
        config.conf[CONFIG_SECTION][CONFIG_KEY_API_KEY] = self.api_key_ctrl.GetValue()
        config.conf[CONFIG_SECTION][CONFIG_KEY_TARGET_LANGUAGE] = self.language_ctrl.GetValue()
        config.conf[CONFIG_SECTION][CONFIG_KEY_ENABLED] = self.enable_checkbox.GetValue()
        
        # Update global plugin settings
        # Find our plugin instance in the running plugins set
        for plugin in globalPluginHandler.runningPlugins:
            if isinstance(plugin, GlobalPlugin):
                plugin.load_config()
                break
        
        self.EndModal(wx.ID_OK) 
