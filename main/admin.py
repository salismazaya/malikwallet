from collections.abc import Sequence
from typing import Any
from django.contrib import admin
from django.db.models import Subquery, OuterRef, CharField
from django.db.models.functions import Cast
from django.contrib.auth.models import Group as AuthGroup, User as AuthUser
from django.db.models.query import QuerySet
# from django.contrib import messages
from django.http import HttpRequest
from main.models import Transaction, Customer, ParrentTransaction, PPOBTransaction, TransferUser, Deposit, TransactionIn, MerchantToken, RequestDeposit, PPOBProduct, PPOBProductWrapper
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin, GroupAdmin as AuthGroupAdmin
from main.forms import ParrentTransactionAdminForm, TransferUserAdminForm, TransactionMerchantAdminForm
from django.utils import timezone
from datetime import timedelta

class AdminSite(admin.AdminSite):
    pass


class AuthUserAdmin(AuthUserAdmin):
    readonly_fields = ('is_superuser',)


class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'balance', 'buy_amount_today', 'limit', 'type')
    list_filter = ('type',)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).order_by('-balance')

    def balance(self, obj):
        return obj.balance
    
    balance.admin_order_field = 'balance'
    balance.short_description = 'Saldo'
    
    def buy_amount_today(self, obj):
        return obj.buy_amount_today
    
    buy_amount_today.admin_order_field = 'buy_amount_today'
    buy_amount_today.short_description = 'Uang Keluar Hari Ini'
    
    def limit(self, obj):
        return obj.limit_with_extra_limit
    
    limit.admin_order_field = 'limit_with_extra_limit'
    
    def has_delete_permission(self, request: HttpRequest, obj: Any | None = ...) -> bool:
        return False
    
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False


class ParrentTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'amount', 'type', 'caption', 'time', 'enable')
    list_filter = ('time', 'enable')
    ordering = ('-time',)
    form = ParrentTransactionAdminForm
    # readonly_fields = ('customer', 'child_transaction_id', 'amount', 'caption', 'type', 'time')
    search_fields = ('customer__user__first_name', 'customer__user__last_name', 'customer__user__username', 'caption')


    def has_change_permission(self, request: HttpRequest, obj: Any | None = ...) -> bool:
        return False
    
    
    # def has_delete_permission(self, request: HttpRequest, obj: Any | None = ...) -> bool:
    #     return False
    
    # @transaction.atomic
    # def save_model(self, request: HttpRequest, obj: ParrentTransaction, form, change):
    #     try:
    #         return super().save_model(request, obj, form, change)
    #     except Exception as e:
    #         messages.error(request, str(e))
    #         messages.set_level(request, messages.ERROR)

    def get_deleted_objects(self, objs: QuerySet[Any], request: HttpRequest) -> tuple[list[Any], dict[Any, Any], set[Any], list[Any]]:
        deleted_objects, model_count, perms_needed, protected = super().get_deleted_objects(objs, request)
        for obj in objs:
            if not obj.child_transaction_id is None:
                child_model = obj.get_child_model()
                if not child_model is None:
                    objs2 = child_model.objects.filter(pk = obj.child_transaction_id)
                    for obj2 in objs2:
                        deleted_objects.append(f"{child_model._meta.object_name}: {obj2}")
                        if model_count.get(child_model._meta.model_name) is None:
                            model_count[child_model._meta.model_name] = 0
                        
                        model_count[child_model._meta.model_name] += 1

                objs3 = ParrentTransaction.objects.filter(child_transaction_id = obj.child_transaction_id).exclude(pk = obj.pk).filter(type = obj.type)
                for obj3 in objs3:
                    deleted_objects.append(f"{ParrentTransaction._meta.object_name}: {obj3}")
                    if model_count.get(ParrentTransaction._meta.model_name) is None:
                        model_count[ParrentTransaction._meta.model_name] = 0
                        
                    model_count[ParrentTransaction._meta.model_name] += 1

        return deleted_objects, model_count, perms_needed, protected

class BaseChildTransactionDateTimeFilter(admin.SimpleListFilter):
    title = "Waktu"
    parameter_name = "time__gte"

    def lookups(self, request: HttpRequest, model_admin: Any):
        now = timezone.now()
        seven_day_ago = now - timedelta(days = 7)

        return [
            (timezone.datetime(now.year, now.month, now.day, 23, 59), 'Hari ini'),
            (timezone.datetime(seven_day_ago.year, seven_day_ago.month, seven_day_ago.day, 23, 59), 'Tujuh hari dari sekarang'),
            (timezone.datetime(now.year, now.month, 1, 23, 59), 'Bulan ini'),
            (timezone.datetime(now.year, 1, 1, 23, 59), 'Tahun ini'),
        ]
    
    def queryset(self, request: HttpRequest, queryset: QuerySet[Any]):
        if self.value() is None:
            return queryset
        
        return queryset.filter(time__gte = self.value())
    

class BaseChildTranscationAdmin(admin.ModelAdmin):
    def get_list_filter(self, request: HttpRequest) -> Sequence[str]:
        rv = list(super().get_list_filter(request))
        rv.append(BaseChildTransactionDateTimeFilter)
        return rv

    def get_model_type(self):
        raise NotImplementedError

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).annotate(
            time = Subquery(
                ParrentTransaction.objects.filter(type = self.get_model_type()).filter(child_transaction_id = Cast(OuterRef('pk'), output_field = CharField())).values('time')[:1]
            )
        ).order_by('-time')

    def time(self, obj):
        return obj.time
    
    time.admin_order_field = 'time'

    def has_change_permission(self, request: HttpRequest, obj: Any | None = ...) -> bool:
        return False
    
    def get_deleted_objects(self, objs: QuerySet[Any], request: HttpRequest) -> tuple[list[Any], dict[Any, Any], set[Any], list[Any]]:
        deleted_objects, model_count, perms_needed, protected = super().get_deleted_objects(objs, request)
        for obj in objs:
            objs2 = ParrentTransaction.objects.filter(child_transaction_id = obj.pk).all()
            for obj2 in objs2:
                if model_count.get(ParrentTransaction._meta.model_name) is None:
                    model_count[ParrentTransaction._meta.model_name] = 0
                
                model_count[ParrentTransaction._meta.model_name] += 1
                deleted_objects.append(f"{ParrentTransaction._meta.object_name}: {obj2}")

        return deleted_objects, model_count, perms_needed, protected
    
    

class TransactionAdmin(BaseChildTranscationAdmin):
    def get_model_type(self):
        return ParrentTransaction.TypeChoices.MERCHANT_TRANSACTION

    form = TransactionMerchantAdminForm
    list_display = ('id', 'from_customer', 'to_customer', 'amount', 'time')
    search_fields = ('from_customer__user__first_name', 'from_customer__user__last_name', 'from_customer__user__username',
                     'to_customer__user__first_name', 'to_customer__user__last_name', 'to_customer__user__username')


class PPOBTransactionAdmin(BaseChildTranscationAdmin):
    list_display = ('id', 'customer', 'product', 'status', 'time')
    search_fields = ('customer__user__first__name', 'customer__user__last_name', 'customer__user__username', 'product__name', 'product__wrapper__name')
    list_filter = ('status',)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
    
    def get_model_type(self):
        return ParrentTransaction.TypeChoices.PPOB_TRANSACTION


class TransferUserAdmin(BaseChildTranscationAdmin):
    form = TransferUserAdminForm
    list_display = ('id', 'from_customer', 'to_customer', 'amount', 'time')
    search_fields = ('from_customer__user__first_name', 'from_customer__user__last_name', 'from_customer__user__username',
                     'to_customer__user__first_name', 'to_customer__user__last_name', 'to_customer__user__username')
    

    def get_model_type(self):
        return ParrentTransaction.TypeChoices.TRANSFER_TRANSACTION

    
class DepositAdmin(BaseChildTranscationAdmin):
    list_display = ('id', 'customer', 'amount', 'time')
    search_fields = ('customer__user__first_name', 'customer__user__last_name', 'customer__user__username',)

    def get_model_type(self):
        return ParrentTransaction.TypeChoices.DEPOSIT_TRANSACTION


class TransactionInAdmin(admin.ModelAdmin):
    list_display = ('id', 'amount', 'caption', 'time')
    list_filter = ('time',)
    search_fields = ('caption',)


class RequestDepositAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'time')


class PPOBProductWrapperAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    list_display = ('id', 'name', 'enable')


class PPOBProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name_', 'wrapper', 'safe_enable', 'price')
    search_fields = ('id', 'name', 'wrapper__name')
    list_filter = ('wrapper',)

    def safe_enable(self, obj: PPOBProduct):
        return obj.safe_enable
    
    def name_(self, obj: PPOBProduct):
        return obj.full_name
    
    safe_enable.short_description = 'Aktif?'
    safe_enable.boolean = True

    name_.short_description = 'Nama Produk'

    def price(self, obj: PPOBProduct):
        return obj.price

    price.short_description = 'Harga'

admin_site = AdminSite()
admin_site.register(AuthUser, AuthUserAdmin)
admin_site.register(AuthGroup, AuthGroupAdmin)
admin_site.register(Customer, CustomerAdmin)
admin_site.register(ParrentTransaction, ParrentTransactionAdmin)
admin_site.register(Transaction, TransactionAdmin)
admin_site.register(PPOBTransaction, PPOBTransactionAdmin)
admin_site.register(TransferUser, TransferUserAdmin)
admin_site.register(Deposit, DepositAdmin)
admin_site.register(TransactionIn, TransactionInAdmin)
admin_site.register(MerchantToken)
admin_site.register(RequestDeposit, RequestDepositAdmin)
admin_site.register(PPOBProduct, PPOBProductAdmin)
admin_site.register(PPOBProductWrapper, PPOBProductWrapperAdmin)