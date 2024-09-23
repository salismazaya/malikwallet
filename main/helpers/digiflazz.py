from django.conf import settings
from datetime import timedelta
from django.utils import timezone
import hashlib, requests


_LAST_REFRESH_DIGI_PRODUCT = timezone.now()
_DIGI_PRODUCTS = None

def getBaseBody(arg: str) -> dict:
    rv = {
        'username': settings.DIGIFLAZZ_USERNAME,
        'sign': hashlib.md5((settings.DIGIFLAZZ_USERNAME + settings.DIGIFLAZZ_API_KEY + str(arg)).encode()).hexdigest()
    }

    if settings.SANDBOX:
        rv['testing'] = True

    return rv


def getBalance() -> float:
    data = getBaseBody('depo')
    data['cmd'] = 'deposit'
    
    raw_result = requests.post('https://api.digiflazz.com/v1/cek-saldo', json = data)
    result = raw_result.json()
    if raw_result.status_code != 200:
        raise Exception(result['data']['message'])

    return result['data']['deposit']


def getProducts() -> list:
    global _DIGI_PRODUCTS, _LAST_REFRESH_DIGI_PRODUCT
    if _DIGI_PRODUCTS and _LAST_REFRESH_DIGI_PRODUCT and (timezone.now() - _LAST_REFRESH_DIGI_PRODUCT) < timedelta(minutes = 8):
        return _DIGI_PRODUCTS

    data = getBaseBody('pricelist')
    raw_result = requests.post('https://api.digiflazz.com/v1/price-list', json = data)
    result = raw_result.json()
    if raw_result.status_code != 200:
        raise Exception(result['data']['message'])
    
    _DIGI_PRODUCTS = result['data']
    _LAST_REFRESH_DIGI_PRODUCT = timezone.now()

    return _DIGI_PRODUCTS

def getProduct(product_code: str, products = None):
    if not products:
        products = getProducts()

    for product in products:
        if product['buyer_sku_code'] == product_code:
            return product


def buyProduct(id_, user_id, product_code):
    data = getBaseBody(id_)

    data['ref_id'] = id_
    data['customer_no'] = user_id
    data['buyer_sku_code'] = product_code

    raw_result = requests.post('https://api.digiflazz.com/v1/transaction', json = data)
    result = raw_result.json()
    if raw_result.status_code != 200:
        raise Exception(result['data']['message'])

    return result['data']



