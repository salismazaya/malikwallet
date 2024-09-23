from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.http import HttpRequest, Http404, HttpResponse
from django.utils import timezone
from datetime import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from django.contrib.auth.models import User as AuthUser
from main.models import Transaction, Customer, PPOBTransaction, ParrentTransaction, TransactionIn, TransferUser, Deposit, MerchantToken, RequestDeposit, PPOBProduct, PPOBProductWrapper
from django.db.models import Q, Subquery, OuterRef, Count
from django.db.models.functions import Coalesce
from main.bot import bot
from django.db import transaction
from django.core import management
from io import BytesIO
import traceback, json, hashlib, hmac, json
from pusher_push_notifications import PushNotifications
from encrypted_model_fields.fields import encrypt_str
from django.utils.crypto import get_random_string
from main.helpers import digiflazz
from io import StringIO

beams_client = PushNotifications(
    instance_id = settings.BEAMS_PUSHER_INSTANCE_ID,
    secret_key = settings.BEAMS_PUSHER_SECRET_KEY,
)

@login_required
def index(request: HttpRequest):
    customer = Customer.objects.filter(user__pk = request.user.pk).first()
    
    # datetime_filter = Q(time__gte = timezone.now() - timedelta(days = 1))
    datetime_filter = Q(enable = True)
    
    if request.method == 'GET':        
        if customer.type == Customer.TypeChoices.WALI:
            wali_customer = customer
            customer = Customer.objects.get(pk = customer.santri.pk)
            transactions = ParrentTransaction.objects.filter(customer__pk = wali_customer.santri.pk).order_by('-time')
        else:
            wali_customer = None
            transactions = ParrentTransaction.objects.filter(customer__user__pk = request.user.pk).order_by('-time')
        
        extra_limit = 0

        try:
            data_limit = None
            if request.GET.get('action') == 'filter':
                if request.session.get('dont_use_filter') == True:
                    return redirect('index')
                
                request.session['dont_use_filter'] = True
                start = request.GET.get('start')
                end = request.GET.get('end')
                if start:
                    month, day, year = start.split('/')
                    datetime_filter &= Q(time__gte = timezone.datetime(int(year), int(month), int(day)))
                
                if end:
                    month, day, year = end.split('/')
                    datetime_filter &= Q(time__lte = timezone.datetime(int(year), int(month), int(day), 23, 59))

                if not start and not end:
                    data_limit = 30
            else:
                request.session['dont_use_filter'] = False
                data_limit = 30

            transactions = transactions.filter(datetime_filter)[:data_limit]
        except:
            transactions = []
            messages.error(request, "Gagal mendapatkan data")

        context = {
            'transactions': transactions,
            'is_merchant': customer.type == Customer.TypeChoices.MERCHANT,
            'is_user': customer.type == Customer.TypeChoices.USER,
            'is_wali': wali_customer is not None,
            'customer': customer,
            'wali_customer': wali_customer,
            'debug': settings.DEBUG,
            'extra_limit': extra_limit
        }
        return render(request, 'main/index.html', context)

    if customer.type == Customer.TypeChoices.WALI:
        action = request.POST.get('action')
        if action == 'change_limit':
            limit = request.POST.get('limit', '0')
            if limit.isdigit():
                limit = int(limit)
                if limit < 0:
                    messages.error(request, 'Limit tidak valid')
                else:
                    customer.santri.limit_per_day = limit
                    customer.santri.save()
                    messages.success(request, "Sukses")
                    if not settings.DEBUG:
                        beams_client.publish_to_users(
                            user_ids = [str(customer.santri.user.pk)],
                            publish_body = {
                                'Falseweb': {
                                    'notification': {
                                        'title': 'PEMBERITAHUAN',
                                        'body': f'Limit berubah menjadi Rp. {limit}',
                                    },
                                },
                            }
                        )

        elif action == 'give_withdraw':
            amount = request.POST.get('amount', '0')
            santri = Customer.objects.filter(type = Customer.TypeChoices.USER).get(pk = customer.santri_id)
            
            if amount.isdigit():
                amount = int(amount)
                if amount <= 0:
                    messages.error(request, 'Jumlah tidak valid')
                elif santri.balance < amount:
                    messages.error(request, 'Saldo tidak cukup')
                else:
                    ParrentTransaction.objects.create(
                        customer = santri,
                        amount = -amount,
                        caption = "Penarikan yang diizinkan wali",
                        type = ParrentTransaction.TypeChoices.BURN_TRANSACTION,
                    )
                    messages.success(request, 'Berhasil memberi izin uang cash.')
                    if not settings.DEBUG:
                        beams_client.publish_to_users(
                            user_ids = [str(santri.user.pk)],
                            publish_body = {
                                'web': {
                                    'notification': {
                                        'title': 'PEMBERITAHUAN',
                                        'body': f'Permintaan penarikan disetujui',
                                    },
                                },
                            }
                        )

                        admins = Customer.objects.filter(user__is_superuser = True)
                        users_ids = []
                        for admin in admins:
                            users_ids.append(str(admin.user.pk))

                        beams_client.publish_to_users(
                            user_ids = users_ids,
                            publish_body = {
                                'web': {
                                    'notification': {
                                        'title': f'{customer.santri.user.first_name} {customer.santri.user.last_name}',
                                        'body': f'Mendapatkan persetujuan penarikan Rp. {amount}',
                                    },
                                },
                            }
                        )

        elif action == 'add_fund':
            obj = RequestDeposit.objects.create(
                customer = customer.santri
            )
            file = BytesIO()
            for chunk in request.FILES['image'].chunks():
                file.write(chunk)

            file.seek(0)

            text = f'''
[ PERMINTAAN DEPOSIT ]
ID: {obj.pk}
Santri: {obj.customer.user.first_name} {obj.customer.user.last_name}
'''.strip()
            bot.send_photo(settings.TELEGRAM_CHAT_ID, photo = file, caption = text)
            messages.success(request, "Permintaan terkirim. saldo akan segera masuk")

    return redirect('index')

from zoneinfo import ZoneInfo

@transaction.atomic
def cron(request: HttpRequest):
    MAX_COUNT_MOUNTLY = 20

    now = timezone.now()
    this_month = datetime(now.year, now.month, 1, 0, 0, 0, 0, tzinfo = ZoneInfo(settings.TIME_ZONE))

    customers = Customer.objects.annotate(
        count_this_amount = Coalesce(
            Subquery(
                ParrentTransaction.objects
                    .filter(
                        customer__pk = OuterRef("pk")
                    ).filter(
                        type = ParrentTransaction.TypeChoices.BURN_TRANSACTION
                    ).filter(
                        time__gte = this_month
                    ).filter(
                        caption = "Iuran Listrik"
                    ).values(
                        'customer'
                    ).annotate(
                        count = Count('pk')
                    ).values('count')[:1]
            ),
            0
        )
    ).filter(type = Customer.TypeChoices.USER).filter(pay_daily = True).filter(count_this_amount__lt = 20)

    with transaction.atomic():
        for customer in customers:
            ParrentTransaction.objects.create(
                customer = customer,
                amount = -1000,
                caption = "Iuran Listrik",
                type = ParrentTransaction.TypeChoices.BURN_TRANSACTION
            )
            TransactionIn.objects.create(
                amount = 1000,
                caption = f"Iuran listrik {customer.user.first_name} {customer.user.last_name}"
            )
               

    return HttpResponse('!')


def login(request: HttpRequest):
    if request.method == 'GET':
        return render(request, 'main/login.html')
    
    user = AuthUser.objects.filter(username = request.POST['username'].lower()).first()
    if not user:
        return redirect('login')
    
    if not user.check_password(request.POST['password']):
        return redirect('login')
    
    auth_login(request, user)
    return redirect('index')

@login_required
def pay(request: HttpRequest, merchant_id: int):
    merchant = Customer.objects.filter(pk = merchant_id).filter(type = Customer.TypeChoices.MERCHANT).first()
    if not merchant:
        raise Http404

    context = {
        'merchant': merchant
    }

    if request.method == 'GET':
        return render(request, 'main/pay.html', context)
    
    amount = int(request.POST['amount2'])

    rv = redirect('pay', merchant_id = merchant_id)

    customer = Customer.objects.get(user__pk = request.user.pk)

    if customer.type != Customer.TypeChoices.USER:
        messages.error(request, 'Tidak bisa melakukan pembelian')    
        return rv

    if customer.balance < amount:
        messages.error(request, 'Saldo tidak cukup')    
        return rv
    
    limit = customer.limit_with_extra_limit
    if customer.buy_amount_today + amount > limit:
        messages.error(request, 'Limit terlebihi!')    
        return rv 
    
    try:
        messages.success(request, f"Sukses membayar. Rp {amount}")
        Transaction.objects.create(
            from_customer = Customer.objects.get(user__pk = request.user.pk),
            to_customer = merchant,
            amount = amount
        )

        if not settings.DEBUG:
            beams_client.publish_to_users(
                user_ids = [str(merchant.user.pk)],
                publish_body = {
                    'web': {
                        'notification': {
                            'title': customer.user.first_name,
                            'body': f'Membayar Rp. {amount}',
                        },
                    },
                }
            )
    except:
        traceback.print_exc()
        messages.error(request, 'Kesalahan tidak terduga')    
    
    return redirect('index')

def pk(request: HttpRequest):
    pk = request.user.pk
    return HttpResponse(str(pk), content_type = "application/json")

@login_required
def transfer(request: HttpRequest):
    if request.method == 'GET':
        return render(request, 'main/transfer.html')
    
    rv = redirect('transfer')
    recipient = Customer.objects.filter(user__username = request.POST['username2']).first()
    if not recipient:
        messages.error(request, 'Username tidak ditemukan')    
        return rv

    context = {
        'recipient': recipient
    }

    if request.method == 'GET':
        return render(request, 'main/pay.html', context)
    
    amount = int(request.POST['amount2'])

    customer = Customer.objects.get(user__pk = request.user.pk)
    if customer.balance < amount:
        messages.error(request, 'Saldo tidak cukup')    
        return rv
    
    if not recipient.special_recipient:
        limit = customer.limit_with_extra_limit
        if customer.buy_amount_today + amount > limit:
            messages.error(request, 'Limit terlebihi!')    
            return rv 
    
    try:
        TransferUser.objects.create(
            from_customer = customer,
            to_customer = recipient,
            amount = amount
        )
    except:
        messages.error(request, 'Terjadi error!')    
        return rv
    
    messages.success(request, f"Sukses mengirim Rp {amount}")
    
    if not settings.DEBUG:
        beams_client.publish_to_users(
            user_ids = [str(recipient.user.pk)],
            publish_body = {
                'web': {
                    'notification': {
                        'title': customer.user.first_name,
                        'body': f'Mengirim Rp. {amount}',
                    },
                },
            }
        )
    return redirect('index')


def service_worker(request: HttpRequest):
    return HttpResponse(open(settings.BASE_DIR / 'main/static/js/serviceworker.js').read(), content_type = 'application/javascript')


def beams_auth(request: HttpRequest):
    user_id = str(request.user.pk)
    token = beams_client.generate_token(user_id)
    return HttpResponse(json.dumps(token), content_type = 'application/json')

@require_POST
@csrf_exempt
@transaction.atomic
def pulsa_webhook(request: HttpRequest):
    body = request.body

    expected_signature = request.headers.get('X-Hub-Signature')
    signature = hmac.new(settings.DIGIFLAZZ_SECRET_KEY.encode(), body, hashlib.sha1).hexdigest()

    if expected_signature == 'sha1=' + signature:
        data = json.loads(body)['data']
        id_ = data['ref_id']
        ppobtransaction = PPOBTransaction.objects.filter(unique = id_).filter(status = PPOBTransaction.StatusChoices.PENDING).first()
        if ppobtransaction:
            if data['rc'] == '00':
                ppobtransaction.status == PPOBTransaction.StatusChoices.SUCCESS
                ppobtransaction.sn = data['sn']
                if not settings.DEBUG:
                    beams_client.publish_to_users(
                        user_ids = [str(ppobtransaction.customer.user.pk)],
                        publish_body = {
                            'web': {
                                'notification': {
                                    'title': f"TRANSKASI BERHASIL",
                                    'body': f'Sukses membeli pulsa',
                                },
                            },
                        }
                    )
            elif data['rc'] == '03' or data['rc'] == '':
                pass
            else:
                ppobtransaction.status = PPOBTransaction.StatusChoices.FAILED
                if not settings.DEBUG:
                    beams_client.publish_to_users(
                        user_ids = [str(ppobtransaction.customer.user.pk)],
                        publish_body = {
                            'web': {
                                'notification': {
                                    'title': f"TRANSKASI GAGAL",
                                    'body': f'Waduh! gagal membeli pulsa, saldo sudah dikembalikan',
                                },
                            },
                        }
                    )

        ppobtransaction.save()

    return HttpResponse('!')

@login_required
def pulsa(request: HttpRequest):
    if request.method == 'GET':
        products = {}
        wrappers = PPOBProductWrapper.objects.all()
        for wrapper in wrappers:
            keren = []
            for x in PPOBProduct.objects.filter(wrapper__pk = wrapper.pk).filter(safe_enable = True):
                keren.append({
                    'name': x.full_name,
                    'id': x.id,
                    'price': x.price
                })

            products[wrapper.name] = keren

        context = {
            'products': json.dumps(products),
            'unique': get_random_string()
        }
        return render(request, 'main/pulsa.html', context)
    
    rv = redirect('index')
    unique = request.POST['unique']
    product_id = request.POST['product']
    target = request.POST['target']

    customer = Customer.objects.exclude(type = Customer.TypeChoices.WALI).filter(user__pk = request.user.pk).first()
    if customer is None:
        messages.error(request, 'Tidak bisa melakukan pembelian')
        return rv
    
    product = PPOBProduct.objects.get(pk = product_id)
    
    with transaction.atomic():
        if customer.balance < product.price:
            messages.error(request, 'Saldo tidak cukup')
            return rv

        ppobtransaction, _ = PPOBTransaction.objects.get_or_create(
            defaults = {'unique': unique},
            unique = unique,
            customer = customer,
            product_id = product_id
        )

        try:
            result = digiflazz.buyProduct(unique, target, product_id)
            if result['rc'] == '00':
                ppobtransaction.status == PPOBTransaction.StatusChoices.SUCCESS
                messages.success(request, 'Pembelian sukses')
            elif result['rc'] == '03' or result['rc'] == '':
                messages.success(request, 'Pembelian sukses')
            elif not result['rc'] in ['00', '03']:
                ppobtransaction.status = PPOBTransaction.StatusChoices.FAILED
                messages.error(request, 'Pembelian gagal')
            
        except:
            ppobtransaction.status = PPOBTransaction.StatusChoices.FAILED
            messages.error(request, 'Pembelian gagal')

        ppobtransaction.save()

    return rv

def get_name(request: HttpRequest):
    nfc = request.GET.get('nfc')
    if not nfc:
        return HttpResponse("E_KARTU", status = 403)

    nfc = nfc.lower()

    # h = hmac.new(settings.SECRET_KEY.encode(), pin.encode(), hashlib.sha256)
    # pin_hashed = h.hexdigest()
    
    customer = Customer.objects.filter(nfc_id_lower = nfc).first()
    if not customer:
        return HttpResponse("E_KARTU", status = 403)

    name = f"{customer.user.first_name} {customer.user.last_name}"[:14].upper()
    balance = customer.balance
    active_balance = customer.limit_with_extra_limit - customer.buy_amount_today
    if active_balance < 0:
        active_balance = 0
    
    if active_balance > balance:
        active_balance = balance
    
    return HttpResponse(f"{name}|{balance}|{active_balance}")

        
def get_balance(request: HttpRequest):
    nfc = request.GET.get('nfc')
    if not nfc:
        return HttpResponse("E_KARTU", status = 403)
    
    # h = hmac.new(settings.SECRET_KEY.encode(), pin.encode(), hashlib.sha256)
    # pin_hashed = h.hexdigest()
    
    customer = Customer.objects.filter(nfc_id_lower = nfc).first()
    if not customer:
        return HttpResponse("E_KARTU", status = 403)

    return HttpResponse(str(customer.balance))


def pay_2(request: HttpRequest):
    nfc = request.GET.get('nfc')
    pin = request.GET.get('pin')
    amount = request.GET.get('amount')
    merchant_token = request.GET.get('merchant')

    if not all([pin, amount, merchant_token, nfc]):
        return HttpResponse("E_003", status = 403)
    
    if not amount.isdigit():
        return HttpResponse("E_002", status = 403)
    
    amount = int(amount)

    # h = hmac.new(settings.SECRET_KEY.encode(), pin.encode(), hashlib.sha256)
    # pin_hashed = h.hexdigest()
    merchant_token_hashed = hashlib.sha256(merchant_token.encode()).hexdigest()
    
    customer = Customer.objects.filter(nfc_id_lower = nfc).first()
    merchant_token = MerchantToken.objects.filter(id__type = Customer.TypeChoices.MERCHANT).filter(token_hashed = merchant_token_hashed).first()

    if not merchant_token:
        return HttpResponse("E_MERCHANT", status = 403)
    
    merchant = merchant_token.id

    if not customer:
        return HttpResponse("E_KARTU", status = 403)
    
    if pin != customer.pin:
        return HttpResponse("E_PIN", status = 403)

    if customer.type != Customer.TypeChoices.USER:
        return HttpResponse("E_001", status = 403)

    if customer.balance < amount:
        return HttpResponse("E_SALDO", status = 403)
    
    limit = customer.limit_with_extra_limit
    if customer.buy_amount_today + amount > limit:
        return HttpResponse("E_LIMIT", status = 403) 
    
    try:
        Transaction.objects.create(
            from_customer = customer,
            to_customer = merchant,
            amount = amount
        )

        if not settings.DEBUG:
            beams_client.publish_to_users(
                user_ids = [str(merchant.user.pk)],
                publish_body = {
                    'web': {
                        'notification': {
                            'title': customer.user.first_name,
                            'body': f'Membayar Rp. {amount}',
                        },
                    },
                }
            )
        return HttpResponse("SUKSES")
    except:
        traceback.print_exc()
        return HttpResponse("E_000", status = 403)
 

def backup(request: HttpRequest):
    with StringIO() as f:
        management.call_command("dumpdata", stdout = f)
        f.seek(0)
        data_encrypted = encrypt_str(f.read()).decode('utf-8')

    return HttpResponse(json.dumps({
        'data': data_encrypted
    }), content_type = "application/json")