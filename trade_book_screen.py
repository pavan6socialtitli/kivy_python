from kivymd.uix.screen import MDScreen
from kivymd.uix.list import TwoLineListItem
from kivy.clock import Clock
from kivy.animation import Animation
from kivymd.uix.datatables import MDDataTable
from kivy.metrics import dp
from datetime import datetime
from kivy.core.window import Window

class TradeBookScreen(MDScreen):
    def __init__(self, **kwargs):
#        super().__init__(**kwargs)
        super(TradeBookScreen, self).__init__(**kwargs)
        self.api_instance = None
#        self.kotakapi = None
#        self.consumer_key = None
        self.trade_table = None

    def set_api_instance(self, consumer_key):
        print("Setting API instance in TradeBookScreen")
        self.consumer_key = consumer_key
#        self.api_instance  = self.kotakapi.get_active_session(consumer_key)
        if hasattr(self.kotakapi, 'get_active_session'):
            self.api_instance = self.kotakapi.get_active_session(consumer_key)
        else:
            print("Warning: kotakapi does not have get_active_session method")
            self.api_instance = self.kotakapi  # Fallback to using kotakapi directly
        self.fetch_trade_book()

    def on_enter(self):
        print("Entering TradeBookScreen")
        if self.api_instance:
            print("Loading TradeBook data")
            self.fetch_trade_book()

    def refresh_data(self):
        self.fetch_trade_book()  # Manual refresh

    def fetch_trade_book(self):
#        self.ids.loading_spinner.active = True
        Clock.schedule_once(self.load_trade_book, 0.5)  # Simulate network delay

    def load_trade_book(self, dt):
        trades = self.kotakapi.get_tradebook_data(self.consumer_key)
        self.update_trade_book_display(trades)
#        self.ids.loading_spinner.active = False

    def update_trade_book_display(self, trades):
        # Sort trades by ordDtTm in descending order (most recent first)
        sorted_trades = sorted(trades, key=lambda x: datetime.strptime(x['ordDtTm'], '%d-%b-%Y %H:%M:%S'), reverse=True)

        if self.trade_table:
            self.ids.tradebook_container.remove_widget(self.trade_table)
        # Calculate the table height to fit the available space
        screen_height = Window.height
        table_height = screen_height - dp(150)  # Adjust this value as needed

        self.trade_table = MDDataTable(
            size_hint=(None, None),
            width=Window.width - dp(20),  # Full width minus padding
            height=table_height,
            use_pagination=True,
            rows_num=20,
            column_data=[
                ("Time", dp(20)),
                ("Symbol", dp(30)),
                ("Quantity", dp(20)),
                ("Price", dp(25)),
                ("Status", dp(20)),
                ("Order No.", dp(30))
            ],
            row_data=[
                (
                    datetime.strptime(trade['ordDtTm'], '%d-%b-%Y %H:%M:%S').strftime('%H:%M:%S'),
                    trade['symbol'],
                    str(trade['quantity']),
                    f"₹{float(trade['avgPrc']):,.2f}",
                    trade['ordSt'],
                    trade['OrdNo']
                ) for trade in sorted_trades
            ]
        )

        self.ids.tradebook_container.add_widget(self.trade_table)
    


