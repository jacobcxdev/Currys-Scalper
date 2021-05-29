from os import environ

from scalper import Scalper
from config import Config


if __name__ == "__main__":
    config = Config(environ["CONFIG"]) if "CONFIG" in environ else Config.from_file_path("config.json")
    max_product_name_length = max([len(x.name) for x in config.product_infos])
    scalpers = []
    for product_info in config.product_infos:
        scalper = Scalper(
            config=config.scalper_config,
            ifttt_config=config.ifttt_config,
            payment_info=config.payment_info,
            product_info=product_info,
            user_info=config.user_info,
            max_product_name_length=max_product_name_length
        )
        scalper.daemon = True
        scalper.start()
        scalpers.append(scalper)
    for scalper in scalpers:
        scalper.join()
