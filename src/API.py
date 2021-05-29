import json
import logging
import re

from logging import Logger
from requests import codes, Response, Session
from time import sleep
from traceback import format_exc
from typing import Any, Callable, Dict, Optional

from selenium.webdriver.chrome.webdriver import WebDriver

from config import Config


def get_base_required_cookies(
    webdriver: WebDriver,
    logger: Logger = logging
) -> Dict[str, Optional[str]]:
    logger.debug("-> Getting the base required cookies (involves waiting 10 seconds)…")
    webdriver.delete_all_cookies()
    webdriver.get("https://www.currys.co.uk/gbuk/s/authentication.html")
    sleep(10)
    logger.debug("-> Finished waiting for the base required cookies.")
    cookies = webdriver.get_cookies()
    if cookies is None:
        logger.warning("-> No base required cookies found.")
        return {}
    cookies = {x["name"]: x["value"] for x in cookies}
    logger.debug(f"-> Base required cookies = '{cookies}'.")
    return cookies


def get_store_currys(
    session: Session,
    user_info: Config.UserInfo,
    logger: Logger = logging
) -> Optional[str]:
    logger.debug("-> Getting the 'store-currys' cookie…")
    response = session.get(
        "https://www.currys.co.uk/gbuk/s/authentication.html",
        allow_redirects=False,
        timeout=5
    )
    if not response.ok:
        response.raise_for_status()
    matches = re.search(
        r'data-login-token-name="(?P<name>\S+)"\s*data-login-token-value="(?P<value>\S+)"',
        response.text
    )
    if matches is None:
        return None
    data = {
        "subaction": "authentication",
        "validate_authentication": True,
        "sFormName": "header-login",
        matches["name"]: matches["value"],
        "sEmail": user_info.email,
        "login": "",
        "sPassword": user_info.password,
        "sRememberMe": "1"
    }
    response = session.post(
        "https://www.currys.co.uk/gbuk/s/authentication.html",
        data=data,
        allow_redirects=False,
        timeout=5
    )
    if response.status_code != codes.found:
        response.raise_for_status()
    if "store-currys" not in response.cookies:
        logger.error("-> No 'store-currys' cookie found.")
        return None
    logger.debug(f"-> 'store-currys' cookie = '{response.cookies['store-currys']}'.")
    return response.cookies["store-currys"]


def get_basket_id(
    session: Session,
    logger: Logger = logging
) -> str:
    logger.debug("-> Getting the basket ID…")
    response = session.get(
        "https://www.currys.co.uk/api/user/token",
        data={},
        allow_redirects=False,
        timeout=5
    )
    if response.status_code != codes.ok:
        response.raise_for_status()
    basket_id = response.json()["bid"]
    logger.debug(f"-> 'basket_id = '{basket_id}'.")
    return basket_id


def get_basket(
    session: Session,
    basket_id: str,
    logger: Logger = logging
) -> Response:
    logger.debug(f"-> Getting basket '{basket_id}'…")
    response = session.get(
        f"https://api.currys.co.uk/store/api/baskets/{basket_id}",
        allow_redirects=False,
        timeout=5
    )
    return response


def add_product(
    session: Session,
    product_info: Config.ProductInfo,
    logger: Logger = logging
) -> Response:
    logger.debug(
        f"-> Adding product '{product_info.name}' ({product_info.pid})"
        " to the basket…"
    )
    data = {
        "fupid": product_info.pid,
        "quantity": 1
    }
    response = session.post(
        "https://www.currys.co.uk/api/cart/addProduct",
        data=json.dumps(data),
        allow_redirects=False,
        timeout=5
    )
    return response


def delete_product(
    session: Session,
    product_info: Config.ProductInfo,
    basket_id: str,
    logger: Logger = logging
) -> Response:
    logger.debug(
        f"-> Deleting product '{product_info.name}' ({product_info.pid})"
        f" from basket '{basket_id}'…"
    )
    response = session.delete(
        f"https://api.currys.co.uk/store/api/baskets/{basket_id}/products/{product_info.pid}",
        allow_redirects=False,
        timeout=5
    )
    return response


def set_quantity(
    session: Session,
    product_info: Config.ProductInfo,
    basket_id: str,
    logger: Logger = logging
) -> Response:
    logger.debug(
        f"-> Setting the quantity of product '{product_info.name}' ({product_info.pid})"
        f" in basket '{basket_id}'…"
    )
    data = {"quantity": product_info.quantity}
    response = session.put(
        f"https://api.currys.co.uk/store/api/baskets/{basket_id}/products/{product_info.pid}/quantity",
        data=data,
        allow_redirects=False,
        timeout=5
    )
    return response


def set_home_delivery(
    session: Session,
    product_info: Config.ProductInfo,
    basket_id: str,
    logger: Logger = logging
) -> Response:
    logger.debug(
        f"-> Setting the delivery method of product '{product_info.name}' ({product_info.pid})"
        f" in basket '{basket_id}' to home delivery…"
    )
    data = {"fulfilmentChannel": "home-delivery"}
    response = session.put(
        f"https://api.currys.co.uk/store/api/baskets/{basket_id}/products/{product_info.pid}/fulfilmentChannel",
        data=data,
        allow_redirects=False,
        timeout=5
    )
    return response


def get_consignments(
    session: Session,
    user_info: Config.UserInfo,
    basket_id: str,
    logger: Logger = logging
) -> Response:
    logger.debug(f"-> Getting consignments for basket '{basket_id}'…")
    data = {
        "location": user_info.post_code,
        "latitude": user_info.latitude,
        "longitude": user_info.longitude
    }
    response = session.put(
        f"https://api.currys.co.uk/store/api/baskets/{basket_id}/deliveryLocation",
        data=data,
        allow_redirects=False,
        timeout=5
    )
    return response


def set_delivery_slot(
    session: Session,
    consignment_type: str,
    delivery_slot: Dict[str, Any],
    basket_id: str,
    logger: Logger = logging
) -> Response:
    logger.debug(
        f"-> Setting delivery slot for consignment '{consignment_type}'"
        f" in basket '{basket_id}'"
        f" to {delivery_slot['date']} @ {delivery_slot['timeSlot']}"
        f" (costs {float(delivery_slot['price']['amountWithVat']) / 100:.2f}"
        f" {delivery_slot['price']['currency']})…"
    )
    data = {
        "provider": delivery_slot["provider"],
        "priceAmountWithVat": delivery_slot["price"]["amountWithVat"],
        "priceVatRate": delivery_slot["price"]["vatRate"],
        "priceCurrency": delivery_slot["price"]["currency"],
        "date": delivery_slot["date"],
        "timeSlot": delivery_slot["timeSlot"]
    }
    response = session.put(
        f"https://api.currys.co.uk/store/api/baskets/{basket_id}/consignments/{consignment_type}/deliverySlot",
        data=data,
        allow_redirects=False,
        timeout=5
    )
    return response


def apply_offer_code(
    session: Session,
    product_info: Config.ProductInfo,
    basket_id: str,
    logger: Logger = logging
) -> Response:
    logger.debug(
        f"-> Applying offer code '{product_info.offer_code}'"
        f" for product '{product_info.name}' ({product_info.pid})"
        f" to basket '{basket_id}'…"
    )
    data = {"offerCode": product_info.offer_code}
    response = session.post(
        f"https://api.currys.co.uk/store/api/baskets/{basket_id}/offerRedemptions",
        data=data,
        allow_redirects=False,
        timeout=5
    )
    return response


def invalidate_payment_request(
    session: Session,
    payment_request_id: str,
    basket_id: str,
    logger: Logger = logging
) -> Response:
    logger.debug(
        f"-> Invalidating payment request '{payment_request_id}'"
        f" for basket '{basket_id}'…"
    )
    data = {
        "paymentRequestStatus": "failed",
        "paymentMethodResultData": []
    }
    response = session.put(
        f"https://api.currys.co.uk/store/api/baskets/{basket_id}/payments/{payment_request_id}",
        data=json.dumps(data),
        allow_redirects=False,
        timeout=20
    )
    return response


def create_order(
    session: Session,
    basket_id: str,
    logger: Logger = logging
) -> Response:
    logger.debug(f"-> Creating order for basket '{basket_id}'…")
    response = session.post(
        f"https://api.currys.co.uk/store/api/baskets/{basket_id}/orders",
        allow_redirects=False,
        timeout=20
    )
    return response


def create_payment_request(
    session: Session,
    basket_id: str,
    logger: Logger = logging
) -> Response:
    logger.debug(f"-> Creating payment request for basket '{basket_id}'…")
    data = {"paymentMethodType": "card"}
    response = session.post(
        f"https://api.currys.co.uk/store/api/baskets/{basket_id}/payments",
        data=json.dumps(data),
        allow_redirects=False,
        timeout=20
    )
    return response


# noinspection PyBroadException
def submit_payment(
    session: Session,
    payment_info: Config.PaymentInfo,
    payment_url: str,
    webdriver: WebDriver,
    notify: Optional[Callable] = None,
    dry_run=False,
    logger: Logger = logging
) -> Optional[Response]:
    logger.debug(f"-> Submitting payment @ '{payment_url}'…")
    response = session.get(
        payment_url,
        allow_redirects=False,
        timeout=20
    )
    if not response.ok:
        return response
    csrf_matches = re.search(r'name="_csrf" value="(?P<csrf>\S+)"', response.text)
    api_matches = re.search(r'action="/(?P<api_path>\S+)/(?P<api_version>[\d\-]+)/\S+"', response.text)
    base_url = next(filter(lambda x: "worldpay.com" in x, payment_url.split("/")), "payments.worldpay.com")
    worldpay_api_url = f"https://{base_url}/{api_matches['api_path']}/{api_matches['api_version']}"
    cookies = {"JSESSIONID": response.cookies["JSESSIONID"]}
    data = {"cardNumber": payment_info.card_number}
    response = session.post(
        f"{worldpay_api_url}/rest/cardtypes",
        cookies=cookies,
        data=data,
        allow_redirects=False,
        timeout=20
    )
    if not response.ok or not response.text:
        return response
    card_type = response.json()["cardType"]["type"]
    data = {
        "selectedPaymentMethodName": card_type,
        "cardNumber": payment_info.card_number,
        "cardholderName": payment_info.cardholder_name,
        "expiryDate.expiryMonth": payment_info.expiry_month,
        "expiryDate.expiryYear": payment_info.expiry_year,
        "securityCodeVisibilityType": "MANDATORY",
        "mandatoryForUnknown": True,
        "securityCode": payment_info.security_code,
        "dfReferenceId": "",
        "tmxSessionId": "",
        "_csrf": csrf_matches["csrf"],
        "ajax": True
    }
    response = session.post(
        f"{worldpay_api_url}/payment/multicard/process",
        cookies=cookies,
        data=data,
        timeout=20
    )
    if not response.ok or not response.text:
        return response
    if dry_run:
        if notify is not None:
            try:
                notify()
            except:
                logger.error("-> Error in notification callback.")
                logger.error(format_exc())
        return None
    iframe_matches = re.search(r'src="\S+/payment/auth/(?P<iframe_keypath>\S+)/iframe"', response.text)
    logger.debug("-> Continuing in webdriver…")
    webdriver.delete_all_cookies()
    webdriver.get(f"{worldpay_api_url}/payment/auth/{iframe_matches['iframe_keypath']}/iframe")
    for name, value in cookies.items():
        webdriver.add_cookie({"name": name, "value": value})
    webdriver.get(f"{worldpay_api_url}/payment/auth/{iframe_matches['iframe_keypath']}/iframe")
    if notify is not None:
        try:
            notify()
        except:
            logger.error("-> Error in notification callback.")
            logger.error(format_exc())
