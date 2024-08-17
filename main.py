from kivymd.app import MDApp
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen
from login_screen import LoginScreen
from trading_screen import TradingScreen
from strategy_screen import StrategyScreen
from trade_book_screen import TradeBookScreen

from kotak_api import KotakAPI
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from kivy.core.text import LabelBase
import os
from kivy.utils import platform
from kivy.clock import Clock

if platform == 'android':
    from android.permissions import request_permissions, Permission
    
    def check_permissions(self, *args):
        request_permissions([
            Permission.INTERNET,
            Permission.WRITE_EXTERNAL_STORAGE,
            Permission.READ_EXTERNAL_STORAGE
        ])


class MainScreen(Screen):
    pass

class DevKotakTradingApp(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "DeepOrange"

        try:
            self.kotak_api = KotakAPI()
            # Rest of your initialization code
        except Exception as e:
            print(f"Error initializing app: {e}")
            # Handle initialization errors

        # Register custom fonts
        self.register_fonts()
        
        Builder.load_file('main.kv')
        
        # Create the screen manager
        self.sm = ScreenManager()
        
        # Create and add Login screen
        login_screen = LoginScreen(name='login')
        login_screen.api = self.kotak_api
        self.sm.add_widget(login_screen)

        # Create main screen
        main_screen = MainScreen(name='main')
        self.sm.add_widget(main_screen)
        
        return self.sm

    def register_fonts(self):
        fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
        font_files = {
            'Roboto-Regular.ttf': 'Roboto',
            'Roboto-Bold.ttf': 'Roboto',
            # Add other font files here if you have more
        }
        
        for font_file, font_name in font_files.items():
            font_path = os.path.join(fonts_dir, font_file)
            if os.path.exists(font_path):
                print(f"Registering font: {font_path}")
                LabelBase.register(name=font_name, fn_regular=font_path)
            else:
                print(f"Warning: Font file not found: {font_path}")

    def on_start(self):
        if platform == 'android':
            Clock.schedule_once(self.check_permissions, 0)
        # Simulate login
#        self.kotak_api = KotakAPI()
#        self.kotak_api.simulate_login()
        pass

if __name__ == '__main__':
    Window.size = (400, 700)  # Simulate mobile device size for desktop testing
    DevKotakTradingApp().run()