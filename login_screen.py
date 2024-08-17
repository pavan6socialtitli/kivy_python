from kivymd.uix.screen import MDScreen
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.storage.jsonstore import JsonStore
from kivy.properties import ObjectProperty
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivy.metrics import dp
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from trading_screen import TradingScreen
from strategy_screen import StrategyScreen
from trade_book_screen import TradeBookScreen
from kivy.clock import Clock
from kivy.utils import platform
import os

class OTPDialogContent(MDBoxLayout):
    def __init__(self, **kwargs):
        print("Initializing LoginScreen")  # Debug statement
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.spacing = dp(10)
        self.padding = dp(20)
        self.size_hint_y = None
        self.height = dp(150)
        
        self.otp_input = MDTextField(
            hint_text="Enter 4-digit OTP",
            input_filter="int",
            max_text_length=4,
            size_hint_y=None,
            height=dp(48)
        )
        self.add_widget(self.otp_input)
        self.mpin_input = MDTextField(
            hint_text="Enter MPIN (if available)",
            input_filter="int",
            password=True,
            size_hint_y=None,
            height=dp(48)
        )
        self.add_widget(self.mpin_input)


class LoginScreen(MDScreen):
    status_label = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
#        self.store = JsonStore('login_credentials.json')
        self.api = None  # This will be set from the main app
        self.otp_dialog = None
        self.otp_content = None
        # Ensure status_label is created if it's not defined in the kv file
        if self.status_label is None:
            self.status_label = MDLabel(text="", halign="center")
            self.add_widget(self.status_label)
        

    def on_enter(self):
        # Check if credentials are already saved
        storage_path = self.get_storage_path()
        self.store = JsonStore(f'{storage_path}/login_credentials.json')
        if self.store.exists('login_credentials'):
            login_credentials = self.store.get('login_credentials')
            self.ids.consumer_key.text = login_credentials.get('consumer_key', '')
            self.ids.secret_key.text = login_credentials.get('secret_key', '')
            mobile_number = login_credentials.get('mobile_number', '')
            if mobile_number.startswith('+91'):
                mobile_number = mobile_number[3:]
            self.ids.mobile_number.text = mobile_number
            self.ids.login_password.text = login_credentials.get('login_password', '')
            self.ids.mpin.text = login_credentials.get('mpin', '')

            # Don't pre-fill the password for security reasons

            # Check for an active session
            active_session = self.api.get_active_session(login_credentials.get('consumer_key'))
            if active_session:
                self.login_success(login_credentials.get('consumer_key'))
                return

    def get_storage_path():
        if platform == 'android':
            try:
                from android.storage import app_storage_path
                return app_storage_path()
            except ImportError:
                # Fallback if running in desktop environment
                return os.path.dirname(os.path.abspath(__file__))
        else:
            return os.path.dirname(os.path.abspath(__file__))

    def initiate_login(self):
        consumer_key = self.ids.consumer_key.text
        secret_key = self.ids.secret_key.text
        mobile_number = '+91' + self.ids.mobile_number.text.lstrip('0')
        login_password = self.ids.login_password.text
        mpin = self.ids.mpin.text

        if not all([consumer_key, secret_key, mobile_number, login_password]):
            self.show_error_dialog("Please fill in all fields")
            return

        # Check for an active session first
        active_session = self.api.get_active_session(consumer_key)
        if active_session:
            self.login_success(consumer_key)
            return

        # Attempt to initiate login using the Kotak API
        try:
            response = self.api.initiate_login(consumer_key, secret_key, mobile_number, login_password)
            if response:
                self.show_otp_dialog()
            else:
                self.show_error_dialog("Failed to send OTP / MPIN. Please check your credentials and try again.")
        except ValueError as ve:
            self.show_error_dialog(f"Login error: {str(ve)}")
        except Exception as e:
            self.show_error_dialog(f"Login initiation failed: {str(e)}")

    def show_otp_dialog(self):
        if not self.otp_dialog:
            self.otp_content = OTPDialogContent()
            # Check if MPIN is available and pre-fill it
            if self.store.exists('login_credentials'):
                login_credentials = self.store.get('login_credentials')
                mpin = login_credentials.get('mpin', '')
                if mpin:
                    self.otp_content.mpin_input.text = mpin

            self.otp_dialog = MDDialog(
                title="Enter OTP or MPIN",
                type="custom",
                content_cls=self.otp_content,
                buttons=[
                    MDFlatButton(
                        text="CANCEL",
                        on_release=self.dismiss_otp_dialog
                    ),
                    MDFlatButton(
                        text="VERIFY",
                        on_release=self.verify_otp_or_mpin
                    ),
                ],
                size_hint=(0.8, None),
                height=dp(300)
            )
        self.otp_dialog.open()


    def verify_otp_or_mpin(self, *args):
        if not self.otp_content:
            self.show_error_dialog("OTP/MPIN dialog not properly initialized")
            return
        otp = self.otp_content.otp_input.text
        mpin = self.otp_content.mpin_input.text
        print(f'OTP entered value is - {otp} and MPIN is - {mpin}')
        if mpin and len(mpin) == 6:
            final_otp = mpin
        elif otp and len(otp) == 4:
            final_otp = otp
        else:
            self.show_error_dialog("Please enter a valid 4-digit OTP or 6 digit MPIN")
            return
        try:
            login_successful = self.api.complete_login(final_otp)
            if login_successful:
                self.dismiss_otp_dialog()
                self.save_credentials()
                self.login_success(self.ids.consumer_key.text)
            else:
                self.show_error_dialog("Invalid OTP. Please try again.")
        except Exception as e:
            self.show_error_dialog(f"Login failed: {str(e)}")
            print(f"Login error details: {e}") 

    def login_success(self, consumer_key):
        print("Entering login_success method")
        self.status_label.text = "Login successful!"
        
        print("Attempting to get main screen")
        main_screen = self.manager.get_screen('main')
        if main_screen is None:
            print("Error: Unable to find main screen")
            self.show_error_dialog("Unable to access main screen")
            return
        
        print("Setting up Trading Screen")
        bottom_nav = main_screen.ids.bottom_nav
        
        # Create and add TradingScreen
        trading_screen = TradingScreen(name='trading')
        trading_screen.kotakapi = self.api
        trading_screen.set_api_instance(consumer_key)
        trading_item = MDBottomNavigationItem(
            name='trading',
            text='Trading',
            icon='chart-line'
        )
        trading_item.add_widget(trading_screen)
        bottom_nav.add_widget(trading_item)

        strategy_screen = StrategyScreen(name='strategy')
        strategy_screen.subscribe_new_symbol = trading_screen.subscribe_new_symbol
        strategy_screen.get_token_from_option_data = trading_screen.get_token_from_option_data
        strategy_screen.subscribed_symbols = trading_screen.subscribed_symbols 
        strategy_screen.option_data = trading_screen.option_data
        strategy_screen.current_prices = trading_screen.current_prices        # Share current_prices between screens
        strategy_screen.load_positions = trading_screen.load_positions
#        strategy_screen.load_account_info = trading_screen.load_account_info

        strategy_screen.kotakapi = self.api
        strategy_screen.set_api_instance(consumer_key)
        strategy_item = MDBottomNavigationItem(
            name='strategy',
            text='Strategy',
            icon='strategy'
        )
        strategy_item.add_widget(strategy_screen)
        bottom_nav.add_widget(strategy_item)


        # Create and add TradeBookScreen
        trade_book_screen = TradeBookScreen(name='trade_book')
        trade_book_screen.kotakapi = self.api
        trade_book_screen.set_api_instance(consumer_key)
        trade_book_item = MDBottomNavigationItem(
            name='trade_book',
            text='Trade_Book',
            icon='book-open-variant'
        )
        trade_book_item.add_widget(trade_book_screen)
        bottom_nav.add_widget(trade_book_item)
        
        print("Changing screen to main")
        self.manager.current = 'main'
        print("Login success method completed")


    def dismiss_otp_dialog(self, *args):
        if self.otp_dialog:
            self.otp_dialog.dismiss()

    def save_credentials(self):
        if not hasattr(self, 'api') or not self.api.is_logged_in():
            print("Attempted to save credentials without successful login")
            return
        mobile_number = self.ids.mobile_number.text.lstrip('0')  # Remove leading zeros
        if not mobile_number.startswith('+91'):
            mobile_number = '+91' + mobile_number

        credentials = {
            'consumer_key': self.ids.consumer_key.text,
            'secret_key': self.ids.secret_key.text,
            'mobile_number': mobile_number,
            'login_password': self.ids.login_password.text
        }

        # Check if MPIN is provided
        mpin = self.ids.mpin.text.strip()
        if mpin:
            credentials['mpin'] = mpin
        elif 'mpin' in self.store.get('login_credentials', {}):
            # If MPIN field is empty and there was a previously saved MPIN, remove it
            credentials['mpin'] = ''  # This will remove the MPIN from storage

        consumer_key = self.ids.consumer_key.text
        # Check if credentials with the same consumer_key already exist
        if self.store.exists('login_credentials') and self.store.get('login_credentials')['consumer_key'] == consumer_key:
            print("Credentials with the same consumer_key already exist")
            return
        self.store.put('login_credentials', **credentials)
#        self.store.put('login_credentials', 
#                       consumer_key=self.ids.consumer_key.text,
#                       secret_key=self.ids.secret_key.text,
#                       mobile_number=mobile_number,
#                       login_password=self.ids.login_password.text,
#                       mpin=self.ids.mpin.text)
        print("Credentials saved successfully")
        if 'mpin' in credentials:
            print("MPIN saved" if credentials['mpin'] else "MPIN removed")
        else:
            print("No MPIN provided")

    def show_error_dialog(self, message):
        dialog = MDDialog(
            title="Error",
            text=message,
            buttons=[
                MDFlatButton(
                    text="OK", on_release=lambda *args: dialog.dismiss()
                )
            ],
        )
        dialog.open()