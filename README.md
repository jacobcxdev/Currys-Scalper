# Currys Scalper
A scalper bot for https://currys.co.uk/ — written in Python.

## Motivation
I ruined my sleeping schedule for the first few months of 2021 by staying awake for over 20 hours each day, trying to purchase a GPU I desperately needed for my business. Each time one restocked, it would be purchased by other people's bots faster than was humanely possible. I was left with only one option: to fight fire with fire.

## Usage Information
This bot can be run locally, or it can be deployed to [Heroku](http://heroku.com) with ease. The final stage of the purchase flow relies on [Selenium](http://selenium.dev), [Google Chrome](http://google.com/chrome/), and [chromedriver](http://chromedriver.chromium.org).

This bot creates a separate scalper thread for each product listed in https://github.com/jacobcxdev/Currys-Scalper/blob/main/config.json. Each thread executes the scalping logic in an infinite loop, meaning that it will automatically retry if anything goes wrong. While this allows the bot to be relatively low-maintenance, it does have the downside of continuing the loop even after a successful purchase. To mitigate this, I would recommend using a debit card loaded with just enough money to purchase what you need. I would also recommend making use of an [IFTTT webhook](https://ifttt.com/maker_webhooks) to notify you when the final stage of the purchase flow is started, so that you can complete any 3D secure authentication needed to complete the purchase and stop the bot if successful.

**You have 60 seconds to complete any 3D Secure authentication before the final purchase stage times out.**

### https://github.com/jacobcxdev/Currys-Scalper/blob/main/config.json Explained
```
{
    "scalper": {                       // Your scalper configuration data.
        "chromedriver_location": "",   // Location of the chromedriver executable.
        "delivery_sort_method": "",    // Determine how to select a delivery slot (see below for more information).
        "dry_run": true,               // Choose whether the bot should use dry run mode (see below for more information).
        "ssl_verify": true             // Choose whether to verify SSL certificates.
    },
    "ifttt": {                         // Your IFTTT configuration data.
        "key": "",                     // Your IFTTT webhook key (under 'Documentation' at https://ifttt.com/maker_webhooks).
        "webhook_event_names": []      // The names of any IFTTT webhook events to trigger.
    },
    "payment_info": {                  // Your payment info.
        "card_number": "",             // Your card number.
        "cardholder_name": "",         // Your cardholder name.
        "expiry_month": "",            // Your card's expiry month.
        "expiry_year": "",             // Your card's expiry year.
        "security_code": ""            // Your card's security code.
    },
    "product_infos": [                 // Array of information dictionaries about products to purchase.
        {
            "name": "",                // Name of product (for logging).
            "pid": "",                 // Product ID (in product page URL — see below for more information).
            "quantity": 1,             // Quantity of this product to purchase.
            "offer_code": ""           // Offer code to attempt to apply to the basket.
        }
    ],
    "user_info": {                     // Your https://currys.co.uk/ user account information.
        "email": "",                   // Your account email.
        "password": "",                // Your account password.
        "post_code": "",               // Your post code (used by the shipping API).
        "latitude": 0,                 // Your latitude (used by the shipping API).
        "longitude": 0                 // Your longitude (used by the shipping API).
    }
}
```

#### `delivery_sort_method`
This field is used to determine which method to use for sorting (and then selecting) available delivery slots. Possible values are listed below:
* `price_low_high`: Sorts available delivery slots by price from low to high, selecting the cheapest slot. This will usually be the standard delivery slot, which is free and takes 3–5 working days.
* `price_high_low`: Sorts available delivery slots by price from high to low, selecting the most expensive slot.
* `chronological`: Sorts available delivery slots chronologically, selecting the slot which is most soon. This sorting method excludes the standard delivery slot.

#### `dry_run`
This field is used to determine whether the bot should run in dry run mode. In dry run mode, the bot will skip the final stage of the purchase flow and trigger the IFTTT webhook early, allowing you to ensure the bot works as expected. I would recommend testing the bot with a cheap product which is currently in stock, then switching back to whichever product you would like to purchase after verifying that it works fine.

**Remember to set the `dry_run` field to `false` when running the bot for real.**

#### `pid`
This field is used to determine which product to purchase. Each product has a product ID in their store page URL, as seen in this example:
```
https://www.currys.co.uk/gbuk/computing-accessories/components-upgrades/graphics-cards/asus-geforce-rtx-3080-10-gb-tuf-gaming-oc-graphics-card-10214446-pdt.html
                                                                                                                                               ~~~~~~~~
                                                                                                                                               ^ here
```

### Running Locally
1. `git clone https://github.com/jacobcxdev/Currys-Scalper.git`
2. `cd currys-scalper`
3. Download and install [Pipenv](https://github.com/pypa/pipenv).
4. Download and install [Google Chrome](http://google.com/chrome/).
5. Download and install [chromedriver](http://chromedriver.chromium.org).
6. Fill in https://github.com/jacobcxdev/Currys-Scalper/blob/main/config.json with your details.
7. `pipenv run python3 src/main.py`

### Running on [Heroku](http://heroku.com)
1. `git clone https://github.com/jacobcxdev/Currys-Scalper.git`
2. `cd currys-scalper`
3. Follow Heroku's steps [here](https://devcenter.heroku.com/articles/git).
4. Add the following buildpacks:
    * https://github.com/heroku/heroku-buildpack-python
    * https://github.com/heroku/heroku-buildpack-google-chrome
    * https://github.com/heroku/heroku-buildpack-chromedriver
5. Fill in https://github.com/jacobcxdev/Currys-Scalper/blob/main/config.json with your details, then copy the contents to a config var named `CONFIG`. You may want to revert https://github.com/jacobcxdev/Currys-Scalper/blob/main/config.json for security purposes.
6. `heroku ps:scale worker=1`

I would recommend connecting a logging add-on to your Heroku application if it has a free trial available (for example: [Papertrail](https://elements.heroku.com/addons/papertrail)).

## Notice
I am not liable for any consequences of using this bot, nor will I be actively maintaining it. I have made it public solely for educational reasons, in hopes that https://currys.co.uk/ implements tougher measures to prevent such effortless automation.

## License
This bot is unlicensed — you may not copy, distribute, or modify this code without my express permission.
