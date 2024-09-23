from django.db.models.signals import post_save, post_delete, pre_save
from django.db import transaction
from django.dispatch import receiver
from django.contrib.auth.models import User
from main.models import Customer, Transaction, PPOBTransaction, ParrentTransaction, TransferUser, Deposit, MerchantToken
import hashlib

@receiver(pre_save, sender = MerchantToken)
def merchant_token_handler(sender, **kwargs):
    instance: MerchantToken = kwargs['instance']
    instance.token_hashed = hashlib.sha256(instance.token.encode()).hexdigest()


@receiver(post_save, sender = User)
def user_handler(sender, **kwargs):
    instance = kwargs['instance']
    created = kwargs['created']

    if created:
        Customer.objects.create(user = instance)


@receiver(post_delete, sender = ParrentTransaction)
def parrent_transaction_delete_handler(sender, **kwargs):
    instance: ParrentTransaction = kwargs['instance']
    if instance.child_transaction_id is None:
        return

    ParrentTransaction.objects.filter(type = instance.type).filter(child_transaction_id = instance.child_transaction_id).filter(child_transaction_id__isnull = False).delete()
    
    if instance.type == ParrentTransaction.TypeChoices.DEPOSIT_TRANSACTION:
        Deposit.objects.filter(pk = instance.child_transaction_id).delete()
    
    elif instance.type == ParrentTransaction.TypeChoices.MERCHANT_TRANSACTION:
        Transaction.objects.filter(pk = instance.child_transaction_id).delete()
    
    elif instance.type == ParrentTransaction.TypeChoices.PPOB_TRANSACTION:
        PPOBTransaction.objects.filter(pk = instance.child_transaction_id).delete()
    
    elif instance.type == ParrentTransaction.TypeChoices.TRANSFER_TRANSACTION:
        TransferUser.objects.filter(pk = instance.child_transaction_id).delete()


@receiver(post_save, sender = Transaction)
def transaction_handler(sender, **kwargs):
    instance = kwargs['instance']
    created = kwargs['created']

    if created:
        with transaction.atomic():
            ParrentTransaction.objects.create(
                customer = instance.from_customer,
                child_transaction_id = instance.pk,
                amount = -instance.amount,
                caption = f"Bayar ke {instance.to_customer.user.first_name} {instance.to_customer.user.last_name}",
                type = ParrentTransaction.TypeChoices.MERCHANT_TRANSACTION
            )
            ParrentTransaction.objects.create(
                customer = instance.to_customer,
                child_transaction_id = instance.pk,
                amount = instance.amount,
                caption = f"Terima pembayaran dari {instance.from_customer.user.first_name} {instance.from_customer.user.last_name}",
                type = ParrentTransaction.TypeChoices.MERCHANT_TRANSACTION
            )

@receiver(post_delete, sender = Transaction)
def transaction_delete_handler(sender, **kwargs):
    instance: Transaction = kwargs['instance']
    ParrentTransaction.objects.filter(child_transaction_id = instance.pk).filter(
        type = ParrentTransaction.TypeChoices.MERCHANT_TRANSACTION
    ).delete()


@receiver(post_save, sender = PPOBTransaction)
def ppob_transaction_handler_post_save(sender, **kwargs):
    instance: PPOBTransaction = kwargs['instance']

    created = kwargs['created']
    
    if created:
        ParrentTransaction.objects.create(
            customer = instance.customer,
            child_transaction_id = instance.pk,
            amount = -instance.product.price,
            caption = "Beli pulsa",
            type = ParrentTransaction.TypeChoices.PPOB_TRANSACTION
        )


@receiver(pre_save, sender = PPOBTransaction)
def ppob_transaction_handler(sender, **kwargs):
    instance: PPOBTransaction = kwargs['instance']
    instance_before_save = PPOBTransaction.objects.filter(pk = instance.pk).first()

    if instance_before_save and instance.status == PPOBTransaction.StatusChoices.FAILED and instance_before_save.status == PPOBTransaction.StatusChoices.PENDING:
        ParrentTransaction.objects.filter(type = ParrentTransaction.TypeChoices.PPOB_TRANSACTION).filter(child_transaction_id__isnull = False).filter(child_transaction_id = instance_before_save.pk).update(enable = False)
        

@receiver(post_delete, sender = PPOBTransaction)
def ppob_transaction_delete_handler(sender, **kwargs):
    instance: PPOBTransaction = kwargs['instance']
    ParrentTransaction.objects.filter(child_transaction_id = instance.pk).filter(
        type = ParrentTransaction.TypeChoices.PPOB_TRANSACTION
    ).delete()

@receiver(post_save, sender = TransferUser)
def transfer_user_handler(sender, **kwargs):
    instance: TransferUser = kwargs['instance']
    created = kwargs['created']

    if created:
        with transaction.atomic():
            ParrentTransaction.objects.create(
                customer = instance.from_customer,
                child_transaction_id = instance.pk,
                amount = -instance.amount,
                caption = f"Transfer ke {instance.to_customer.user.first_name} {instance.to_customer.user.last_name}",
                type = ParrentTransaction.TypeChoices.TRANSFER_TRANSACTION
            )
            ParrentTransaction.objects.create(
                customer = instance.to_customer,
                child_transaction_id = instance.pk,
                amount = instance.amount,
                caption = f"Diterima dari {instance.from_customer.user.first_name} {instance.from_customer.user.last_name}",
                type = ParrentTransaction.TypeChoices.TRANSFER_TRANSACTION
            )

@receiver(post_delete, sender = TransferUser)
def transfer_user_delete_handler(sender, **kwargs):
    instance: TransferUser = kwargs['instance']
    ParrentTransaction.objects.filter(child_transaction_id = instance.pk).filter(
        type = ParrentTransaction.TypeChoices.TRANSFER_TRANSACTION
    ).delete()


@receiver(post_save, sender = Deposit)
def deposit_handler(sender, **kwargs):
    instance: Deposit = kwargs['instance']
    created = kwargs['created']

    if created:
        ParrentTransaction.objects.create(
            customer = instance.customer,
            amount = instance.amount,
            child_transaction_id = instance.pk,
            caption = "Tambah saldo",
            type = ParrentTransaction.TypeChoices.DEPOSIT_TRANSACTION,
        )

@receiver(post_delete, sender = Deposit)
def deposit_delete_handler(sender, **kwargs):
    instance: Deposit = kwargs['instance']
    ParrentTransaction.objects.filter(child_transaction_id = instance.pk).filter(
        type = ParrentTransaction.TypeChoices.DEPOSIT_TRANSACTION
    ).delete()