import json

from functools import cached_property
from typing import Optional


class Config:
    class Scalper:
        def __init__(
            self,
            chromedriver_location: str,
            delivery_sort_method: str,
            dry_run: bool,
            ssl_verify: bool
        ):
            self.chromedriver_location = chromedriver_location
            self.delivery_sort_method = delivery_sort_method
            self.dry_run = dry_run
            self.ssl_verify = ssl_verify

    class IFTTT:
        def __init__(
            self,
            key: str,
            webhook_event_names: [str]
        ):
            self.key = key
            self.webhook_event_names = webhook_event_names

    class PaymentInfo:
        def __init__(
            self,
            card_number: str,
            cardholder_name: str,
            expiry_month: str,
            expiry_year: str,
            security_code: str
        ):
            self.card_number = card_number
            self.cardholder_name = cardholder_name
            self.expiry_month = expiry_month
            self.expiry_year = expiry_year
            self.security_code = security_code

    class ProductInfo:
        def __init__(
            self,
            name: str,
            pid: str,
            quantity: int,
            offer_code: str = ""
        ):
            self.name = name
            self.pid = pid
            self.quantity = quantity
            self.offer_code = offer_code

    class UserInfo:
        def __init__(
            self,
            email: str,
            password: str,
            post_code: str,
            latitude: float,
            longitude: float
        ):
            self.email = email,
            self.password = password,
            self.post_code = post_code,
            self.latitude = latitude
            self.longitude = longitude

    def __init__(self, json_dict: Optional[str] = None):
        if json_dict is not None:
            self.config_dict = json.loads(json_dict)

    @staticmethod
    def from_file_path(path: str):
        config = Config()
        with open(path, "r") as file:
            config.config_dict = json.load(file)
        return config

    @cached_property
    def chromedriver_location(self) -> str:
        return self.config_dict["chromedriver_location"]

    @cached_property
    def delivery_sort_method(self) -> str:
        return self.config_dict["delivery_sort_method"]

    @cached_property
    def dry_run(self) -> bool:
        return self.config_dict["dry_run"]

    @cached_property
    def scalper_config(self) -> Scalper:
        scalper_config = self.config_dict["scalper"]
        return Config.Scalper(
            chromedriver_location=scalper_config["chromedriver_location"],
            delivery_sort_method=scalper_config["delivery_sort_method"],
            dry_run=scalper_config["dry_run"],
            ssl_verify=scalper_config["ssl_verify"],
        )

    @cached_property
    def ifttt_config(self) -> IFTTT:
        ifttt_config = self.config_dict["ifttt"]
        return Config.IFTTT(
            key=ifttt_config["key"],
            webhook_event_names=ifttt_config["webhook_event_names"]
        )

    @cached_property
    def payment_info(self) -> PaymentInfo:
        payment_info = self.config_dict["payment_info"]
        return Config.PaymentInfo(
            card_number=payment_info["card_number"],
            cardholder_name=payment_info["cardholder_name"],
            expiry_month=payment_info["expiry_month"],
            expiry_year=payment_info["expiry_year"],
            security_code=payment_info["security_code"]
        )

    @cached_property
    def product_infos(self) -> [ProductInfo]:
        return [
            Config.ProductInfo(x["name"], x["pid"], x["quantity"], x["offer_code"])
            for x in self.config_dict["product_infos"]
        ]

    @cached_property
    def user_info(self) -> UserInfo:
        user_info = self.config_dict["user_info"]
        return Config.UserInfo(
            email=user_info["email"],
            password=user_info["password"],
            post_code=user_info["post_code"],
            latitude=user_info["latitude"],
            longitude=user_info["longitude"]
        )
