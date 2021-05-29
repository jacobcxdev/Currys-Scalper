import logging
import urllib3

from functools import cached_property
from json.decoder import JSONDecodeError
from requests import Session
from requests.exceptions import Timeout
from requests.utils import add_dict_to_cookiejar
from threading import Thread
from time import sleep
from traceback import format_exc
from typing import Any, Dict, List, Optional

import coloredlogs

from pyifttt.webhook import send_notification
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options

import API

from config import Config


class Scalper(Thread):
    class AbortAttemptException(Exception):
        pass

    attempt_count = 0
    clear_cache_count = 0
    failure_counts = {}
    session = Session()

    @cached_property
    def basket_id(self) -> str:
        basket_id = API.get_basket_id(
            session=self.session,
            logger=self.logger
        )
        self.logger.info("-> Got the basket ID.")
        return basket_id

    @cached_property
    def store_currys(self) -> str:
        add_dict_to_cookiejar(self.session.cookies, self.base_required_cookies)
        store_currys = API.get_store_currys(
            session=self.session,
            user_info=self.user_info,
            logger=self.logger
        )
        if store_currys is None:
            self.clear_cache(clear_all_cookies=True)
            raise Scalper.AbortAttemptException
        self.logger.info("-> Got the 'store-currys' cookie.")
        return store_currys

    @cached_property
    def base_required_cookies(self) -> Dict[str, Optional[str]]:
        base_required_cookies = API.get_base_required_cookies(
            webdriver=self.webdriver,
            logger=self.logger
        )
        self.logger.info("-> Got the base required cookies.")
        return base_required_cookies

    @cached_property
    def required_cookies(self) -> Dict[str, Optional[str]]:
        return self.base_required_cookies | {"store-currys": self.store_currys}

    def __init__(
        self,
        config: Config.Scalper,
        ifttt_config: Config.IFTTT,
        payment_info: Config.PaymentInfo,
        product_info: Config.ProductInfo,
        user_info: Config.UserInfo,
        max_product_name_length: int,
    ):
        super().__init__()
        self.config = config
        self.ifttt_config = ifttt_config
        self.payment_info = payment_info
        self.product_info = product_info
        self.user_info = user_info

        self.webdriver = None
        self.init_chrome_webdriver()

        if not self.config.ssl_verify:
            self.session.verify = False
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        empty_space = max_product_name_length - len(product_info.name)
        self.logger = logging.getLogger(f"{product_info.name}{empty_space * ' '} — {product_info.pid}")
        coloredlogs.install(
            fmt=f"[%(name)-{empty_space + 11}s] : [%(levelname)-8s] : %(message)s",
            field_styles={
                "levelname": {
                    "bold": True,
                    "color": "black"
                },
                "name": {
                    "bright": True,
                    "color": "blue"
                },
            },
            level=logging.DEBUG,
            logger=self.logger)
        logging.addLevelName(35, "SUCCESS")

    def clear_cache(self, clear_all_cookies: bool = False) -> None:
        self.logger.debug(f"-> Clearing cache (clear_all_cookies={clear_all_cookies})…")
        self.clear_cache_count += 1
        if "basket_id" in self.__dict__:
            del self.__dict__["basket_id"]
        if "store_currys" in self.__dict__:
            del self.__dict__["store_currys"]
        if "auth_required_cookies" in self.__dict__:
            del self.__dict__["auth_required_cookies"]
        if "required_cookies" in self.__dict__:
            del self.__dict__["required_cookies"]
        should_clear_all_cookies = clear_all_cookies or self.clear_cache_count % 100 == 0
        if should_clear_all_cookies and "base_required_cookies" in self.__dict__:
            del self.__dict__["base_required_cookies"]
            self.webdriver.delete_all_cookies()
        self.failure_counts = {}
        self.session.cookies.clear()

    def init_chrome_webdriver(self) -> None:
        if self.webdriver is not None:
            self.webdriver.quit()
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        self.webdriver = Chrome(self.config.chromedriver_location, options=options)

    def notify(self) -> None:
        if self.ifttt_config.key:
            for event_name in self.ifttt_config.webhook_event_names:
                send_notification(event_name, dict(value1=self.product_info.name), self.ifttt_config.key)

    def sorted_delivery_slots(
        self,
        delivery_slots: List[Dict[str, Any]],
        delivery_sort_method: Optional[str] = "price_low_high"
    ) -> List[Dict[str, Any]]:
        def sorted_by_price_low_high(slots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            return sorted(slots, key=lambda x: x["price"]["amountWithVat"])

        def sorted_chronologically(slots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            return sorted(slots, key=lambda x: x["date"])

        self.logger.debug(f"-> Sorting delivery slots by method '{delivery_sort_method}'…")
        if delivery_sort_method == "price_low_high":
            return sorted_by_price_low_high(delivery_slots)
        elif delivery_sort_method == "price_high_low":
            return sorted_chronologically(list(reversed(sorted_by_price_low_high(delivery_slots))))
        elif delivery_sort_method == "chronological":
            return sorted_chronologically(list(filter(
                lambda x: "premium" in x["provider"],
                sorted_by_price_low_high(delivery_slots)
            )))
        else:
            self.logger.error(f"-> Unknown delivery method '{delivery_sort_method}'.")

    def scalp(self) -> None:
        self.attempt_count += 1
        self.logger.info(f"Attempt #{self.attempt_count}…")

        if self.attempt_count % 10000 == 0:
            self.init_chrome_webdriver()

        response = None
        try:
            # Add the required cookies to the current requests session.
            self.session.cookies.clear()
            add_dict_to_cookiejar(self.session.cookies, self.required_cookies)

            # Add the product to the basket.
            response = API.add_product(
                session=self.session,
                product_info=self.product_info,
                logger=self.logger
            )
            if not response.ok:
                failure_count = self.failure_counts.get("add_to_basket", 0) + 1
                self.failure_counts["add_to_basket"] = failure_count
                self.logger.error(
                    "-> Failed to add the product to the basket"
                    f" {failure_count} time{'' if failure_count == 1 else 's'}"
                    f" [{response.status_code}]."
                )
                if failure_count >= 10:
                    self.clear_cache()
                return
            self.logger.info("-> Added the product to the basket.")

            # Set the quantity of the product in the basket.
            response = API.set_quantity(
                session=self.session,
                product_info=self.product_info,
                basket_id=self.basket_id,
                logger=self.logger
            )
            if not response.ok:
                failure_count = self.failure_counts.get("set_quantity", 0) + 1
                self.failure_counts["set_quantity"] = failure_count
                self.logger.error(
                    "-> Failed to set the quantity of the product"
                    f" {failure_count} in the basket time{'' if failure_count == 1 else 's'}"
                    f" [{response.status_code}]."
                )
                if failure_count >= 10:
                    self.clear_cache()
                return
            self.logger.info(f"-> Set the quantity of the product in the basket to {self.product_info.quantity}.")

            # Delete any other products from the basket, getting the current one in the process.
            current_product = None
            products = response.json()["payload"]["products"]
            different_products = len(products)
            self.logger.info(
                f"-> The basket contains {different_products}"
                f" {'type of product' if different_products == 1 else 'types of products'}."
            )
            for product in products:
                if product["id"] == self.product_info.pid:
                    self.logger.info(
                        f"-> The product costs {float(product['price']['amountWithVat']) / 100:.2f}"
                        f" {product['price']['currency']}."
                    )
                    current_product = product
                else:
                    self.logger.debug(f"-> Attempting to delete product '{product['title']}' ({product['id']})…")
                    response = API.delete_product(
                        session=self.session,
                        product_info=Config.ProductInfo(product["title"], product["id"], 1),
                        basket_id=self.basket_id,
                        logger=self.logger
                    )
                    if not response.ok:
                        self.logger.error(
                            f"-> Failed to delete product '{product['title']}' ({product['id']})"
                            f" [{response.status_code}]."
                        )
                        return
                    self.logger.info(
                        f"-> Deleted product '{product['title']}' ({product['id']})"
                        " from the basket."
                    )
            if current_product is None:
                self.logger.error("-> Failed to locate the product in the basket.")
                return

            # Set the delivery method of the basket.
            home_delivery_set = current_product["fulfilmentChannel"] == "home-delivery"
            if not home_delivery_set:
                response = API.set_home_delivery(
                    session=self.session,
                    product_info=self.product_info,
                    basket_id=self.basket_id,
                    logger=self.logger
                )
                if not response.ok:
                    self.logger.error(
                        "-> Failed to set delivery method for the product"
                        f" [{response.status_code}]."
                    )
                    return
                self.logger.info("-> Selected home delivery for the product.")
            else:
                self.logger.info(
                    "-> The product already has delivery method set;"
                    " selected home delivery for the product."
                )

            # Get any consignments for the basket.
            response = API.get_consignments(
                session=self.session,
                user_info=self.user_info,
                basket_id=self.basket_id,
                logger=self.logger
            )
            if not response.ok:
                self.logger.error(
                    "-> Failed to get consignments for the basket"
                    f" [{response.status_code}]."
                )
                return
            consignments = response.json()["payload"]["consignments"]
            if len(consignments) < 1:
                self.logger.error("-> No consignments available for the basket.")
                return
            self.logger.info("-> Got consignments for the basket.")

            # Set the delivery slots for the consignments if needed.
            for consignment in consignments:
                consignment_type = consignment["id"]["type"]
                if not consignment["isReadyForDelivery"] or consignment["deliverySlot"] is None:
                    delivery_slots = consignment["availableDeliverySlots"]
                    if len(consignment["availableDeliverySlots"]) == 0:
                        self.logger.error(f"-> No delivery slots available for consignment '{consignment_type}'.")
                        return
                    self.logger.info(f"-> Got delivery slots for consignment '{consignment_type}'.")

                    sorted_delivery_slots = self.sorted_delivery_slots(
                        delivery_slots=delivery_slots,
                        delivery_sort_method=self.config.delivery_sort_method
                    )
                    if len(sorted_delivery_slots) == 0:
                        self.logger.error(
                            f"-> No delivery slots available for consignment '{consignment_type}'"
                            f" with delivery sort method {self.config.delivery_sort_method}."
                        )
                        sorted_delivery_slots = self.sorted_delivery_slots(
                            delivery_slots=delivery_slots,
                            delivery_sort_method="price_low_high"
                        )

                    delivery_slot = sorted_delivery_slots[0]
                    response = API.set_delivery_slot(
                        session=self.session,
                        consignment_type=consignment_type,
                        delivery_slot=delivery_slot,
                        basket_id=self.basket_id,
                        logger=self.logger
                    )
                    if not response.ok:
                        self.logger.error(
                            f"-> Failed to set delivery slot for consignment '{consignment_type}'"
                            f" [{response.status_code}]."
                        )
                        return
                    self.logger.info(
                        f"-> Selected delivery slot for consignment '{consignment_type}'"
                        f" on {delivery_slot['date']} @ {delivery_slot['timeSlot']}"
                        f" costs {float(delivery_slot['price']['amountWithVat']) / 100:.2f}"
                        f" {delivery_slot['price']['currency']}."
                    )
                else:
                    delivery_slot = consignment["deliverySlot"]
                    self.logger.info(
                        f"-> Consignment '{consignment_type}' is ready for delivery;"
                        f" selected delivery slot on {delivery_slot['date']} @ {delivery_slot['timeSlot']}"
                        f" costs {float(delivery_slot['price']['amountWithVat']) / 100:.2f}"
                        f" {delivery_slot['price']['currency']}."
                    )

            # Apply an offer code to the basket if provided.
            if self.product_info.offer_code != "":
                _response = response
                response = API.apply_offer_code(
                    session=self.session,
                    product_info=self.product_info,
                    basket_id=self.basket_id,
                    logger=self.logger
                )
                if not response.ok:
                    self.logger.warning(
                        f"-> Failed to apply offer code '{self.product_info.offer_code}'"
                        " for the product to the basket"
                        f" [{response.status_code}]."
                    )
                    response = _response
                else:
                    discount = response.json()["payload"]["totalDiscountAmount"]
                    self.logger.info(
                        f"-> Applied offer code '{self.product_info.offer_code}'"
                        " for the product to the basket;"
                        f" {float(discount['amountWithVat']) / 100:.2f}"
                        f" {discount['currency']} discount applied."
                    )

            # Invalidate any existing payment requests for the basket.
            for payment_request in response.json()["payload"]["paymentRequests"]:
                if payment_request["status"] != "failed":
                    response = API.invalidate_payment_request(
                        session=self.session,
                        payment_request_id=payment_request["id"],
                        basket_id=self.basket_id,
                        logger=self.logger
                    )
                    if not response.ok:
                        self.logger.warning(
                            f"-> Failed to invalidate payment request '{payment_request['id']}'"
                            " for the basket"
                            f" [{response.status_code}]."
                        )
                    self.logger.info(
                        f"-> Invalidated payment request '{payment_request['id']}'"
                        " for the basket."
                    )

            # Create an order for the basket.
            response = API.create_order(
                session=self.session,
                basket_id=self.basket_id,
                logger=self.logger
            )
            if not response.ok:
                self.logger.error(
                    "-> Failed to create order for the basket"
                    f" [{response.status_code}]."
                )
                return
            self.logger.info("-> Created order for the basket.")

            # Create a payment request for the basket.
            response = API.create_payment_request(
                session=self.session,
                basket_id=self.basket_id,
                logger=self.logger
            )
            if not response.ok:
                self.logger.error(
                    "-> Failed to create payment request for the basket"
                    f" [{response.status_code}]."
                )
                return
            self.logger.info("-> Created payment request for the basket.")

            # Submit the payment requests for the basket.
            for payment_request in response.json()["payload"]["paymentRequests"]:
                if payment_request["status"] == "new":
                    response = API.submit_payment(
                        session=self.session,
                        payment_info=self.payment_info,
                        payment_url=payment_request["paymentMethodRequestData"]["payment_url"],
                        webdriver=self.webdriver,
                        notify=self.notify,
                        dry_run=self.config.dry_run,
                        logger=self.logger
                    )
                    self.logger.info("-> Submitted payment for the basket.")
                    if response is None:
                        self.logger.log(
                            35,
                            "-> SUCCESS?"
                            " Please check for any 3D Secure authentication prompts from your payment method;"
                            " waiting for 60 seconds…"
                        )
                        sleep(60)
                        return
                    else:
                        self.logger.error(
                            "-> Failed to submit payment due to an invalid response from {response.url}"
                            f" [{response.status_code}]."
                        )
        except Timeout:
            failure_count = self.failure_counts.get("request_timeout", 0) + 1
            self.failure_counts["request_timeout"] = failure_count
            self.logger.critical(
                "-> Request timed out"
                f" {failure_count} time{'' if failure_count == 1 else 's'}."
            )
            if failure_count >= 10:
                self.clear_cache(clear_all_cookies=True)
            return
        except JSONDecodeError:
            failure_count = self.failure_counts.get("json_decode_error", 0) + 1
            self.failure_counts["json_decode_error"] = failure_count
            self.logger.critical(
                "-> Failed to decode JSON"
                f" {failure_count} time{'' if failure_count == 1 else 's'}"
                f" [{response.status_code}]."
                f" Response from {response.url} has content: {response.content}."
            )
            if failure_count >= 10:
                self.clear_cache(clear_all_cookies=True)
            return

    # noinspection PyBroadException
    def run(self) -> None:
        while True:
            try:
                self.scalp()
            except Scalper.AbortAttemptException:
                self.logger.critical(f"Aborted attempt #{self.attempt_count}.")
            except KeyboardInterrupt:
                exit(0)
            except:
                failure_count = self.failure_counts.get("unknown", 0) + 1
                self.failure_counts["unknown"] = failure_count
                self.logger.critical(format_exc())
                if failure_count >= 10:
                    self.clear_cache(clear_all_cookies=True)
            sleep(1)
