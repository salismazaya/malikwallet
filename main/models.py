from django.db import models
from django.conf import settings
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedCharField
from django.core.validators import RegexValidator
from django.utils.crypto import get_random_string
from main.helpers import digiflazz

class ChildTransactionManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        q = super().get_queryset().annotate(
            time = models.Subquery(
                ParrentTransaction.objects.filter(type = self.model.get_child_alias()).filter(child_transaction_id = models.functions.Cast(models.OuterRef('pk'), output_field = models.CharField())).values('time')[:1]
            )
        )
        return q

    def today(self):
        tz = settings.TIME_ZONE_OBJ
        now = timezone.now().astimezone(tz)
        day_now = timezone.datetime(now.year, now.month, now.day, tzinfo = tz)
        return self.filter(time__gte = day_now)
    

class ChildTransactionQuerySet(models.QuerySet):
    def today(self):
        return ChildTransactionManager.today(self)



class ChildTransactionModel(models.Model):
    class Meta:
        abstract = True

    @staticmethod
    def get_child_alias():
        raise NotImplementedError(f"get_child_alias from model {__class__} not implemented")

    objects = ChildTransactionManager.from_queryset(ChildTransactionQuerySet)()
    original_objects = models.Manager()


class CustomerManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        tz = settings.TIME_ZONE_OBJ
        now = timezone.now().astimezone(tz)
        day_now = timezone.datetime(now.year, now.month, now.day, tzinfo = tz)
        # yesterday = day_now - timedelta(days = 1)
        q =  super().get_queryset().annotate(
            balance = models.functions.Coalesce(
                models.Subquery(
                    ParrentTransaction.objects
                    .filter(customer__pk = models.OuterRef('pk'))
                    .filter(enable = True)
                    .values('customer')
                    .annotate(total_amount = models.Sum('amount'))
                    .values('total_amount'),
                    output_field = models.DecimalField()
                ),
                0,
                output_field = models.DecimalField()
            )
        ).annotate(
            buy_amount_today = models.functions.Coalesce(
                models.Subquery(
                    ParrentTransaction.objects
                    .filter(customer = models.OuterRef('pk'))
                    .exclude(type = ParrentTransaction.TypeChoices.BURN_TRANSACTION)
                    .exclude(type = ParrentTransaction.TypeChoices.PPOB_TRANSACTION)
                    .annotate(
                        is_transfer_to_salism3 = models.Exists(
                            TransferUser.objects
                            .annotate(
                                transaction_type = models.ExpressionWrapper(models.OuterRef('type'), output_field = models.SmallIntegerField())
                            )
                            .annotate(
                                pk_string = models.functions.Cast(
                                    models.F('pk'),
                                    output_field = models.CharField()
                                )
                            )
                            .filter(pk_string = models.OuterRef('child_transaction_id'))
                            .filter(transaction_type = ParrentTransaction.TypeChoices.TRANSFER_TRANSACTION)
                            .filter(to_customer__user__username = 'salism3')[:1]
                        )
                    )
                    .exclude(
                        is_transfer_to_salism3 = True
                    )
                    .filter(amount__lt = 0)
                    .annotate(kasep = models.functions.Abs('amount'))
                    .filter(time__gte = day_now)
                    .values('customer')
                    .annotate(total_amount = models.Sum('kasep'))
                    .values('total_amount'),
                    output_field = models.DecimalField()
                ),
                0,
                output_field = models.DecimalField()
            )
        ).annotate(
            limit_with_extra_limit = models.F('limit_per_day') + models.functions.Coalesce(
                models.Subquery(
                    TransferUser.objects
                    .filter(to_customer = models.OuterRef('pk'))
                    .today()
                    .values('to_customer')
                    .annotate(kasep = models.Sum('amount'))
                    .values("kasep")
                ),
                0
            )
        ).annotate(
            nfc_id_lower = models.functions.Lower("nfc_id")
        )
        return q

class Customer(models.Model):
    class Meta:
        verbose_name = verbose_name_plural = "Customer"
        constraints = [models.CheckConstraint(
            check = models.Q(santri__isnull = True) | models.Q(santri__isnull = False) & models.Q(type = 3),
            name = 'check_wali'
        )]

    objects = CustomerManager()
    original_objects = models.Manager()

    class TypeChoices(models.IntegerChoices):
        USER = 1, 'User'
        MERCHANT = 2, 'Merchant'
        WALI = 3, 'Wali Santri'

    user = models.OneToOneField('auth.User', on_delete = models.PROTECT)
    santri = models.OneToOneField('main.Customer', on_delete = models.PROTECT, null = True, blank = True)
    limit_per_day = models.PositiveBigIntegerField(default = 20000, verbose_name = 'Limit Per Hari')
    type = models.PositiveSmallIntegerField(choices = TypeChoices.choices, default = TypeChoices.USER)
    pay_daily = models.BooleanField(default = True, verbose_name = 'Bayar Listrik?')
    nfc_id = models.CharField(max_length = 50, validators = [
        RegexValidator(regex = r'^[a-fA-F0-9]+$', message = 'Format nfc id tidak valid')
    ], null = True, blank = True)
    pin = EncryptedCharField(max_length = 255, null = True, blank = True, validators = [
        RegexValidator(regex = r'^\d{4,10}$', message = "Format pin tidak valid")
    ])

    def __str__(self):
        return self.user.username


class Transaction(ChildTransactionModel):
    class Meta:
        verbose_name = verbose_name_plural = "Transaksi Warung"

    from_customer = models.ForeignKey(Customer, on_delete = models.PROTECT, verbose_name = 'Dari', related_name = 'skeren')
    to_customer = models.ForeignKey(Customer, on_delete = models.PROTECT, verbose_name = 'Ke', related_name = 'smantap')
    amount = models.PositiveBigIntegerField(verbose_name = 'Total')

    @staticmethod
    def get_child_alias():
        return ParrentTransaction.TypeChoices.MERCHANT_TRANSACTION

    def get_from_name(self):
        rv = self.from_customer.user.first_name
        if self.from_customer.user.last_name:
            rv += " "
            rv += self.from_customer.user.last_name

        return rv
    
    def get_to_name(self):
        rv = self.to_customer.user.first_name
        if self.to_customer.user.last_name:
            rv += " "
            rv += self.to_customer.user.last_name

        return rv
    
    def get_from_user_id(self):
        return self.from_customer.user.pk
    
    def __str__(self):
        return f"{self.pk}:{self.from_customer}:{self.to_customer}:{self.amount}"


class PPOBTransaction(ChildTransactionModel):
    class Meta:
        verbose_name = verbose_name_plural = "Transaksi PPOB"

    class StatusChoices(models.IntegerChoices):
        PENDING = 1, "PENDING"
        FAILED = 2, "GAGAL"
        SUCCESS = 3, "SUKSES"

    @staticmethod
    def get_child_alias():
        return ParrentTransaction.TypeChoices.PPOB_TRANSACTION

    id = models.CharField(max_length = 12, primary_key = True, default = get_random_string)
    unique = models.CharField(max_length = 12, unique = True, editable = False)
    customer = models.ForeignKey(Customer, on_delete = models.PROTECT)
    product = models.ForeignKey('main.PPOBProduct', verbose_name = "Produk", on_delete = models.CASCADE, null = True, blank = True)
    target = EncryptedCharField(max_length = 255)
    status = models.PositiveSmallIntegerField(choices = StatusChoices.choices, default = StatusChoices.PENDING)
    sn = EncryptedCharField(max_length = 255, null = True, blank = True)

    def __str__(self):
        return f"{self.pk}:{self.customer}:{self.product}"


class ParrentTransaction(models.Model):
    class Meta:
        verbose_name = verbose_name_plural = "Transaksi"
        constraints = [
            models.CheckConstraint(
                check=(
                    (models.Q(type = 5) & models.Q(amount__lt=0)) |
                    (models.Q(type = 6) & models.Q(amount__lt=0)) |
                    ~(models.Q(type = 5) | models.Q(type = 6))
                ), 
                name='check_amount_must_negative',
            ),
            models.CheckConstraint(
                check = (
                    (models.Q(type = 5) & models.Q(child_transaction_id__isnull = True)) |
                    (models.Q(type = 6) & models.Q(child_transaction_id__isnull = True)) |
                    ~(models.Q(type = 5) | models.Q(type = 6))
                ),
                name = 'check_child_transaction_id_must_null'
            )
        ]
    
    
    class TypeChoices(models.IntegerChoices):
        MERCHANT_TRANSACTION = 1, "Transaksi Warung"
        PPOB_TRANSACTION = 2, "Transaksi PPOB"
        TRANSFER_TRANSACTION = 3, "Transaksi Transfer"
        DEPOSIT_TRANSACTION = 4, "Transaksi Deposit"
        BURN_TRANSACTION = 5, "Transaksi Dibakar"
        WITHDRAW_TRANSACTION = 6, "Transkasi Ditarik"

    customer = models.ForeignKey(Customer, on_delete = models.PROTECT)
    child_transaction_id = models.CharField(max_length = 12, editable = True, null = True, blank = True)
    amount = models.BigIntegerField(verbose_name = 'Jumlah')
    caption = models.TextField(null = True, blank = True)
    type = models.PositiveSmallIntegerField(choices = TypeChoices.choices)
    time = models.DateTimeField(default = timezone.now, verbose_name = 'Waktu')
    enable = models.BooleanField(default = True, editable = False, verbose_name = 'Aktif?')

    def __str__(self):
        return f"{self.pk}:{self.customer}:{self.amount}:{self.caption[:5]}..."
    
    def get_child_model(self):
        if self.type == ParrentTransaction.TypeChoices.MERCHANT_TRANSACTION:
            return Transaction
        elif self.type == ParrentTransaction.TypeChoices.PPOB_TRANSACTION:
            return PPOBTransaction
        elif self.type == ParrentTransaction.TypeChoices.TRANSFER_TRANSACTION:
            return TransferUser
        elif self.type == ParrentTransaction.TypeChoices.DEPOSIT_TRANSACTION:
            return Deposit

class TransactionIn(models.Model):
    class Meta:
        verbose_name = verbose_name_plural = "Transaksi Masuk Kas"

    amount = models.PositiveBigIntegerField(verbose_name = 'Jumlah')
    caption = models.TextField()
    time = models.DateTimeField(default = timezone.now, verbose_name = 'Waktu')

    def __str__(self):
        return f"{self.pk}:{self.amount}{self.caption[:10]}..."


class TransferUser(ChildTransactionModel):
    class Meta:
        verbose_name = verbose_name_plural = "Transaksi User"

    @staticmethod
    def get_child_alias():
        return ParrentTransaction.TypeChoices.TRANSFER_TRANSACTION

    from_customer = models.ForeignKey(Customer, on_delete = models.PROTECT, related_name = 'skasep', verbose_name = 'Dari Customer')
    to_customer = models.ForeignKey(Customer, on_delete = models.PROTECT, related_name = 'sganteng', verbose_name = 'Ke Customer')
    amount = models.PositiveBigIntegerField(verbose_name = 'Jumlah')

    def __str__(self):
        return f"{self.pk}:{self.from_customer}:{self.to_customer}:{self.amount}"


class Deposit(ChildTransactionModel):
    class Meta:
        verbose_name = verbose_name_plural = "Deposit"

    @staticmethod
    def get_child_alias():
        return ParrentTransaction.TypeChoices.DEPOSIT_TRANSACTION

    customer = models.ForeignKey(Customer, on_delete = models.PROTECT) 
    amount = models.PositiveBigIntegerField(verbose_name = 'Jumlah')

    def __str__(self):
        return f"{self.pk}:{self.customer}:{self.amount}"


class RequestDeposit(models.Model):
    class Meta:
        verbose_name = verbose_name_plural = "Permintaan Deposit"

    customer = models.ForeignKey(Customer, on_delete = models.CASCADE)
    time = models.DateTimeField(default = timezone.now, verbose_name = 'Waktu')


class MerchantToken(models.Model):
    class Meta:
        verbose_name = verbose_name_plural = "Token Warung"

    id = models.OneToOneField(Customer, on_delete = models.CASCADE, primary_key = True)
    token = EncryptedCharField(max_length = 255, default = get_random_string, unique = True)
    token_hashed = models.CharField(max_length = 64, editable = False, null = True)

    def __str__(self):
        return f"Token: {self.id.user.username}"


class PPOBProductWrapper(models.Model):
    class Meta:
        verbose_name = verbose_name_plural = 'Pembungkus Produk PPOB'

    name = models.CharField(max_length = 100)
    enable = models.BooleanField(default = True, verbose_name = 'Aktif?')

    def __str__(self):
        return self.name

class PPOBProductManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().annotate(
            safe_enable = models.Exists(
                PPOBProductWrapper.objects
                .annotate(parrent_enable = models.ExpressionWrapper(models.OuterRef('enable'), output_field = models.BooleanField()))
                .filter(parrent_enable = True)
                .filter(enable = True)
                .filter(pk = models.OuterRef('wrapper'))[:1]
            ),
        ).annotate(
            full_name = models.functions.Concat(
                models.Subquery(
                    PPOBProductWrapper.objects.filter(pk = models.OuterRef('wrapper'))[:1].values('name')
                ),
                models.Value(' - '),
                'name'
            )
        )


class PPOBProduct(models.Model):
    objects = PPOBProductManager()
    original_objects = models.Manager()

    class Meta:
        verbose_name = verbose_name_plural = 'Produk PPOB'

    id = models.CharField(max_length = 10, primary_key = True)
    wrapper = models.ForeignKey(PPOBProductWrapper, on_delete = models.CASCADE)
    name = models.CharField(max_length = 100)
    profit = models.PositiveBigIntegerField(default = 1000)
    enable = models.BooleanField(default = True, verbose_name = 'Aktif?')

    @property
    def price(self):
        try:
            return digiflazz.getProduct(self.id)['price'] + self.profit
        except:
            return 0

    def __str__(self):
        return self.name
    